"""
Phase 2 — Rule-based compliance engine (deterministic).
Uses config/rules.yaml only. No LLM. Returns violation_type, severity, evidence_text, rule_id.

Fix round 2026-10-20 (audit findings 1-4 in ~/workspace/pharma-agent-research/AUDIT.md):
1. Privacy name detection requires genuinely capitalised names (no IGNORECASE
   match of "patient" + any word) and an SSN-format national-id pattern was added.
2. Negation awareness: a keyword/flag occurrence preceded or followed by a
   negation cue in its sentence ("No hospitalization was required") no longer
   counts as present.
3. Off-label: indication phrases are evaluated per sentence; a sentence that
   carries its own approval anchor ("approved for", "indicated for",
   "authorised for", ...) is compliant recitation, not promotion. Explicit
   off-label admissions ("not approved", "unapproved indication") flag anywhere.
4. All keyword/flag matching uses word boundaries (no "rash" inside "crash").

Remediation round 2026-10-20 (workstream E1; adversarial findings D1-D12):
- D1/D9: negation is CLAUSE-scoped. The preceder scan starts after the last
  clause boundary (comma, semicolon, but/however/yet/although) instead of the
  sentence start, so "No nausea was reported, but the patient required
  hospitalization" lets the affirmed flag count. The follower scan now runs
  to the end of the sentence instead of a fixed 40 characters.
- D7: off-label anchoring is clause-scoped on the same boundaries: an anchor
  exempts only its own clause, not unrelated clauses in the same sentence.
- D2: the comparative check is negation-aware like the other checks.
- D3: keyword matching tolerates a plural suffix (s/es) on the final token
  ("rashes", "side effects").
- D4: national-id pattern accepts spaces as well as dashes ("123 45 6789").
- D5: international phone formats ("+91 98765 43210") are detected.
- D6: ALL-CAPS patient names ("PATIENT JOHN SMITH") are detected via a
  dedicated branch; ALL-CAPS text is inherently ambiguous (headers, coded
  fields), so the branch requires the literal PATIENT label plus 2-3
  all-caps tokens.
- D11: emails obfuscated with spaces around "@" are detected.
- D12: multi-word terms accept underscores as joiners ("life_threatening").
D8 (keywords inside quoted titles) and D10 (first-name-only patient
references) are documented limitations, intentionally not fixed.

Feature 1 (evidence trace): every violation dict also carries "matches" —
up to 5 {"matched_text", "context", "start", "end"} spans into the input.
"""

import re
from pathlib import Path
from typing import Any

import yaml


# --- PII/PHI pattern-based detection (no NER, no real data) ---
PHONE_PATTERN = re.compile(
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b\d{10,11}\b"
)
# International format (D5): leading +, 1-3 digit country code, then 2-4
# groups of 2-5 digits separated by spaces/dashes. Candidates are additionally
# required to contain >= 9 digits in total (see _first_phone_match).
INTL_PHONE_PATTERN = re.compile(r"\+\d{1,3}(?:[-\s]\d{2,5}){2,4}")
# Optional spaces around "@" catch the common spaced obfuscation (D11).
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
NATIONAL_ID_PATTERN = re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b")  # SSN format (dashes or spaces, D4)
# A name is "Patient <First> <Last...>" or a titled name (Mr./Mrs./Ms./Dr. X).
# Capitalisation is REQUIRED (no IGNORECASE): "the patient experienced ..."
# must not match. Single-word names after "patient" are not flagged
# (documented recall trade-off, finding D10).
# The ALL-CAPS branch (D6) handles report headers ("PATIENT JOHN SMITH WAS
# ADMITTED"); caps text is inherently ambiguous, so it requires the literal
# PATIENT label followed by 2-3 all-caps tokens of length >= 2.
PATIENT_NAME_PATTERN = re.compile(
    r"\b[Pp]atient\s*[:\-]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"
    r"|\b(?:Mr|Mrs|Ms|Dr)\.\s+[A-Z][a-z]+\b"
    r"|\bPATIENT\s+[A-Z]{2,}(?:\s+[A-Z]{2,}){1,2}\b"
)

# --- negation handling -------------------------------------------------------
_NEGATION_PRECEDERS = (
    "no", "not", "never", "without", "denies", "denied", "none",
    "absence of", "free of", "ruled out", "negative for",
)
_NEGATION_FOLLOWERS = (
    "was not", "were not", "is not", "are not", "not required",
    "not needed", "did not occur", "not reported",
)
_SENTENCE_END = re.compile(r"[.!?\n]")
# Clause boundaries for negation scope (D1) and off-label anchoring (D7).
_CLAUSE_BOUNDARY = re.compile(r"[,;]|\b(?:but|however|yet|although)\b")


def _term_pattern(term: str) -> re.Pattern:
    """Word-boundary pattern for a keyword/phrase; YAML underscores and
    spaces in multi-word terms accept spaces, hyphens or underscores in
    text (D12). The final token tolerates a plural suffix (s/es) so common
    plural forms match (D3)."""
    parts = term.strip().lower().replace("_", " ").split()
    body = r"[\s\-_]+".join(re.escape(p) for p in parts)
    return re.compile(r"\b" + body + r"(?:s|es)?\b")


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """[start, end) bounds of the sentence containing [start:end]."""
    seg_start = 0
    for m in _SENTENCE_END.finditer(text, 0, start):
        seg_start = m.end()
    nxt = _SENTENCE_END.search(text, end)
    seg_end = nxt.start() if nxt else len(text)
    return seg_start, seg_end


def _is_negated(text_lower: str, start: int, end: int) -> bool:
    """True if the occurrence at [start:end] is negated within its clause.

    Preceder cues are searched only in the current clause (D1): the segment
    of the sentence before the match, starting after the last clause
    boundary. Follower cues are searched from the match end to the end of
    the sentence (D9)."""
    seg_start, seg_end = _sentence_bounds(text_lower, start, end)
    clause_start = seg_start
    for m in _CLAUSE_BOUNDARY.finditer(text_lower, seg_start, start):
        clause_start = m.end()
    before = text_lower[clause_start:start]
    if any(re.search(rf"\b{re.escape(cue)}\b", before) for cue in _NEGATION_PRECEDERS):
        return True
    after = text_lower[end:seg_end]
    return any(cue in after for cue in _NEGATION_FOLLOWERS)


def _find_term(text_lower: str, term: str) -> re.Match | None:
    """First non-negated word-boundary occurrence of term, or None."""
    for m in _term_pattern(term).finditer(text_lower):
        if not _is_negated(text_lower, m.start(), m.end()):
            return m
    return None


def _term_present(text_lower: str, term: str) -> bool:
    """True if the term occurs at least once with word boundaries and is
    not negated in its clause."""
    return _find_term(text_lower, term) is not None


# --- evidence trace (Feature 1) ----------------------------------------------
_MAX_MATCHES = 5
_CONTEXT_CHARS = 200


def _make_match(text: str, start: int, end: int) -> dict:
    """Build one trace span: the exact matched substring plus its containing
    sentence as context (trimmed to ~200 chars around the match if longer)."""
    seg_start, seg_end = _sentence_bounds(text, start, end)
    raw = text[seg_start:seg_end]
    context = raw.strip()
    if len(context) > _CONTEXT_CHARS:
        lead = len(raw) - len(raw.lstrip())
        rel = max(0, start - seg_start - lead)
        win = max(0, rel - 60)
        context = context[win:win + _CONTEXT_CHARS]
    return {
        "matched_text": text[start:end],
        "context": context,
        "start": start,
        "end": end,
    }


def load_rules(rules_path: Path) -> dict[str, Any]:
    """Load rules from config/rules.yaml (read-only)."""
    with open(rules_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _first_phone_match(text: str) -> re.Match | None:
    """Earliest phone-number match across the US and international patterns.
    International candidates must contain >= 9 digits in total, which keeps
    short '+'-prefixed codes from counting as phone numbers."""
    candidates = list(PHONE_PATTERN.finditer(text))
    for m in INTL_PHONE_PATTERN.finditer(text):
        if sum(ch.isdigit() for ch in m.group()) >= 9:
            candidates.append(m)
    if not candidates:
        return None
    return min(candidates, key=lambda m: m.start())


def _check_privacy(text: str, rules: dict) -> list[dict]:
    """Detect PII/PHI patterns. Severity: critical.
    Implemented detectors: phone, email, patient/person name, national id
    (SSN format). Other entity types declared in rules.yaml (address,
    beneficiary number, device/biometric identifiers) are NOT implemented —
    see the taxonomy note in config/rules.yaml."""
    found: list[tuple[str, re.Match]] = []
    m = _first_phone_match(text)
    if m:
        found.append(("phone number", m))
    m = EMAIL_PATTERN.search(text)
    if m:
        found.append(("email", m))
    m = PATIENT_NAME_PATTERN.search(text)
    if m:
        found.append(("patient/person name", m))
    m = NATIONAL_ID_PATTERN.search(text)
    if m:
        found.append(("national id", m))
    if not found:
        return []
    evidence_parts = [label for label, _ in found]
    return [{
        "violation_type": "Patient Privacy Violation",
        "severity": "critical",
        "evidence_text": "PII/PHI detected: " + ", ".join(evidence_parts),
        "rule_id": "privacy",
        "matches": [_make_match(text, m.start(), m.end()) for _, m in found[:_MAX_MATCHES]],
    }]


def _check_adverse_event(text: str, rules: dict) -> list[dict]:
    """AE trigger keywords present but no reporting context → high (non-compliance).
    Negated mentions ("no nausea reported") and negated escalation flags
    ("No hospitalization was required") do not count as present."""
    ae = rules.get("adverse_event") or {}
    keywords = [k.strip().lower() for k in ae.get("trigger_keywords", [])]
    text_lower = text.lower()
    found: list[tuple[str, re.Match]] = []
    for kw in keywords:
        m = _find_term(text_lower, kw)
        if m:
            found.append((kw, m))
    if not found:
        return []
    # Reporting context = presence of (non-negated) mandatory_reporting flags
    mrc = rules.get("mandatory_reporting_context") or {}
    flags = [f.strip().lower() for f in mrc.get("escalation_flags", [])]
    has_context = any(_term_present(text_lower, fl) for fl in flags)
    if has_context:
        return []  # Handled by mandatory_reporting_context check
    names = [kw for kw, _ in found]
    return [{
        "violation_type": "Adverse Event Without Reporting Context",
        "severity": "high",
        "evidence_text": f"AE trigger keywords found ({', '.join(names[:5])}{'...' if len(names) > 5 else ''}); no reporting context (e.g. serious, hospitalization) provided.",
        "rule_id": "adverse_event",
        "matches": [_make_match(text, m.start(), m.end()) for _, m in found[:_MAX_MATCHES]],
    }]


def _check_mandatory_reporting(text: str, rules: dict) -> list[dict]:
    """Non-negated escalation flags present → mandatory reporting required (high)."""
    mrc = rules.get("mandatory_reporting_context") or {}
    flags = [f.strip().lower() for f in mrc.get("escalation_flags", [])]
    text_lower = text.lower()
    found: list[tuple[str, re.Match]] = []
    for f in flags:
        m = _find_term(text_lower, f)
        if m:
            found.append((f, m))
    if not found:
        return []
    names = [f for f, _ in found]
    return [{
        "violation_type": "Mandatory Reporting Required",
        "severity": "high",
        "evidence_text": f"Mandatory/expedited reporting flags present: {', '.join(names)}. Escalation required.",
        "rule_id": "mandatory_reporting_context",
        "matches": [_make_match(text, m.start(), m.end()) for _, m in found[:_MAX_MATCHES]],
    }]


# Phrases that assert an approved indication inside a clause. A clause
# carrying one of these anchors is reciting the label, not promoting.
_APPROVAL_ANCHORS = (
    "approved for", "indicated for", "authorised for", "authorized for",
    "licensed for",
)
# Phrases that are admissions of off-label status; they flag in any clause.
_EXPLICIT_OFF_LABEL = ("not approved", "unapproved indication")


def _spans(text: str, start: int, end: int, boundary: re.Pattern) -> list[tuple[int, int]]:
    """Split text[start:end] on boundary matches into non-empty spans."""
    out = []
    pos = start
    for m in boundary.finditer(text, start, end):
        if text[pos:m.start()].strip():
            out.append((pos, m.start()))
        pos = m.end()
    if text[pos:end].strip():
        out.append((pos, end))
    return out


def _check_off_label(text: str, rules: dict) -> list[dict]:
    """Off-label promotion → high. Clause-scoped interpretation of the
    rules.yaml rule ("matched in promotional context without
    approved-indication anchor"): each clause containing an indication
    phrase is checked for its own approval anchor; anchored clauses are
    compliant recitation and are skipped. Explicit off-label admissions
    flag regardless of anchors. (Document-level 'promotional context' is
    not reliably observable from text alone; anchoring is the checkable
    half of the rule and is what is implemented.)"""
    ol = rules.get("off_label_promotion") or {}
    patterns = [p.strip().lower() for p in ol.get("phrase_patterns", [])]
    triggers = [p for p in patterns if p not in _APPROVAL_ANCHORS]
    flagged: dict[str, tuple[int, int]] = {}  # phrase -> first span (doc offsets)
    for s_start, s_end in _spans(text, 0, len(text), _SENTENCE_END):
        for c_start, c_end in _spans(text, s_start, s_end, _CLAUSE_BOUNDARY):
            c_lower = text[c_start:c_end].lower()
            explicit_hit = False
            for p in _EXPLICIT_OFF_LABEL:
                m = _find_term(c_lower, p)
                if m:
                    flagged.setdefault(p, (c_start + m.start(), c_start + m.end()))
                    explicit_hit = True
            if explicit_hit:
                continue
            if any(_term_present(c_lower, a) for a in _APPROVAL_ANCHORS):
                continue  # anchored recitation in this clause
            for p in triggers:
                m = _find_term(c_lower, p)
                if m:
                    flagged.setdefault(p, (c_start + m.start(), c_start + m.end()))
    if not flagged:
        return []
    ordered = sorted(flagged.items(), key=lambda kv: kv[1][0])
    return [{
        "violation_type": "Off-Label Promotion",
        "severity": "high",
        "evidence_text": f"Promotional phrasing suggesting indication: {', '.join(sorted(flagged))}. Verify against approved indication.",
        "rule_id": "off_label_promotion",
        "matches": [_make_match(text, s, e) for _, (s, e) in ordered[:_MAX_MATCHES]],
    }]


def _check_comparative(text: str, rules: dict) -> list[dict]:
    """Comparative/superiority indicators → medium. Negation-aware (D2):
    a denied superiority claim ("not better than placebo") does not flag."""
    cc = rules.get("comparative_claims") or {}
    indicators = [i.strip().lower() for i in cc.get("indicators", [])]
    text_lower = text.lower()
    found: list[tuple[str, re.Match]] = []
    for i in indicators:
        m = _find_term(text_lower, i)
        if m:
            found.append((i, m))
    if not found:
        return []
    names = [i for i, _ in found]
    return [{
        "violation_type": "Improper Comparative Claim",
        "severity": "medium",
        "evidence_text": f"Comparative/superiority language: {', '.join(names)}. Requires substantiation.",
        "rule_id": "comparative_claims",
        "matches": [_make_match(text, m.start(), m.end()) for _, m in found[:_MAX_MATCHES]],
    }]


def run_checks(text: str, rules_path: Path) -> list[dict]:
    """
    Run all deterministic checks. Returns list of dicts with:
    violation_type, severity, evidence_text, rule_id, matches.
    """
    rules = load_rules(rules_path)
    violations = []
    violations.extend(_check_privacy(text, rules))
    violations.extend(_check_adverse_event(text, rules))
    violations.extend(_check_mandatory_reporting(text, rules))
    violations.extend(_check_off_label(text, rules))
    violations.extend(_check_comparative(text, rules))
    return violations
