#!/usr/bin/env python3
"""Regulatory source change impact analysis (Feature F5).

Compares two local plain-text versions of one regulatory source document,
identifies changed passages, and produces a HUMAN REVIEW CHECKLIST of
potentially affected rule families and tests.

This tool NEVER modifies rules, code, or the manifest. It only reports.

Method
------
1. Passage splitting: documents are split into paragraphs on blank lines.
   A paragraph longer than MAX_PARAGRAPH_CHARS is split further into
   sentence groups of at most MAX_SENTENCES_PER_GROUP sentences, so a
   change inside a very long paragraph is not reported as a whole-page
   replacement. Whitespace inside a passage is collapsed before
   comparison; comparison is otherwise exact (case-sensitive).
2. Change detection: difflib.SequenceMatcher over the passage lists.
   'replace' blocks pair old/new passages in order (unpaired leftovers
   become deletions/insertions); 'delete' and 'insert' blocks are
   reported as such.
3. Keyword overlap: for each changed passage (old and new sides — a
   *removed* keyword is as relevant as an added one), salient terms are
   the intersection of passage tokens with the union of all keyword /
   phrase / entity lists declared in config/rules.yaml, loaded at
   runtime with a minimal indentation parser (this tool is stdlib-only
   by design, so PyYAML is not used). Matching is phrase containment on
   normalised text (lowercased, underscores/punctuation -> spaces).
4. Affected families: if the source's manifest entry declares
   ``applicable_rules``, the affected set is those families narrowed to
   families whose keywords matched; if no keywords matched, the
   source's families are still listed as "review — no keyword overlap
   detected". If the manifest has no ``applicable_rules`` for the
   source, a clearly labelled category-based guess is used instead and
   a warning is emitted. For an unknown source-id the tool proceeds
   with keyword mapping only and warns.
5. Test mapping: tests/*.py files whose filename contains a family
   name, or whose contents mention the family name / rule id, are
   listed per affected family.

Limitations (also printed in every report): paragraph-level granularity,
keyword-overlap is a lexical heuristic with no semantic understanding,
and passage pairing inside a 'replace' block is positional.

Usage:
    python scripts/source_diff.py --old OLD.txt --new NEW.txt \
        --source-id FDA_AE_1 [--manifest PATH] [--rules PATH] [--out report.md]
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

MAX_PARAGRAPH_CHARS = 600
MAX_SENTENCES_PER_GROUP = 4
DISPLAY_TRUNCATE = 300

CLOSING_LINE = "Checklist for human review only — no rules were changed by this tool."

# Fallback used ONLY when a manifest entry lacks `applicable_rules`.
# Clearly labelled as a guess in the report.
CATEGORY_FAMILY_GUESS = {
    "privacy": ["privacy"],
    "promotion": ["off_label_promotion", "comparative_claims"],
    "adverse events": ["adverse_event", "mandatory_reporting_context"],
    "pharmacovigilance": ["adverse_event", "mandatory_reporting_context"],
    "safety": ["adverse_event", "mandatory_reporting_context"],
}

# Rule-id aliases that may appear in test files for a family.
FAMILY_ALIASES = {
    "mandatory_reporting_context": ["mandatory_reporting_context", "mandatory_reporting"],
}


class SourceDiffError(Exception):
    """Clean, user-facing error (no traceback)."""


# --------------------------------------------------------------------------
# Text handling
# --------------------------------------------------------------------------

def split_passages(text: str) -> list[str]:
    """Split text into passages: paragraphs, with sentence-group fallback
    for very long paragraphs (see module docstring)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    passages: list[str] = []
    for para in paragraphs:
        collapsed = re.sub(r"\s+", " ", para)
        if len(collapsed) <= MAX_PARAGRAPH_CHARS:
            passages.append(collapsed)
            continue
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", collapsed) if s]
        for i in range(0, len(sentences), MAX_SENTENCES_PER_GROUP):
            passages.append(" ".join(sentences[i:i + MAX_SENTENCES_PER_GROUP]))
    return passages


def find_changes(old_passages: list[str], new_passages: list[str]) -> list[dict]:
    """Return a list of changes: {kind, old: [..], new: [..]} using
    difflib.SequenceMatcher. 'replace' blocks are paired positionally."""
    matcher = difflib.SequenceMatcher(None, old_passages, new_passages, autojunk=False)
    changes: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        olds = old_passages[i1:i2]
        news = new_passages[j1:j2]
        if tag == "replace":
            paired = min(len(olds), len(news))
            for k in range(paired):
                changes.append({"kind": "replaced", "old": [olds[k]], "new": [news[k]]})
            for extra in olds[paired:]:
                changes.append({"kind": "deleted", "old": [extra], "new": []})
            for extra in news[paired:]:
                changes.append({"kind": "inserted", "old": [], "new": [extra]})
        elif tag == "delete":
            for p in olds:
                changes.append({"kind": "deleted", "old": [p], "new": []})
        elif tag == "insert":
            for p in news:
                changes.append({"kind": "inserted", "old": [], "new": [p]})
    return changes


# --------------------------------------------------------------------------
# Rule keyword loading (minimal parser — stdlib only by design)
# --------------------------------------------------------------------------

def load_rule_keywords(rules_path: Path) -> dict[str, list[str]]:
    """Collect every list-of-strings declared under each top-level family
    in rules.yaml (trigger_keywords, phrase_patterns, indicators,
    escalation_flags, forbidden_entities, ...)."""
    if not rules_path.exists():
        raise SourceDiffError(f"rules file not found: {rules_path}")
    families: dict[str, list[str]] = {}
    current: str | None = None
    for raw in rules_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        top = re.match(r"^([A-Za-z_][\w]*):\s*$", raw)
        if top:
            current = top.group(1)
            families.setdefault(current, [])
            continue
        item = re.match(r"^\s+-\s+(.+?)\s*$", raw)
        if item and current:
            value = item.group(1).strip().strip('"').strip("'")
            if value:
                families[current].append(value)
    return families


def _normalise(text: str) -> str:
    text = text.lower().replace("_", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_keyword_matches(text: str, keywords_by_family: dict[str, list[str]]) -> dict[str, list[str]]:
    """Phrase-containment match of rule keywords against normalised text.
    Returns {family: sorted matched keywords (original spelling)}."""
    norm = " " + _normalise(text) + " "
    matched: dict[str, list[str]] = {}
    for family, keywords in keywords_by_family.items():
        hits = []
        for kw in keywords:
            kw_norm = _normalise(kw)
            if kw_norm and f" {kw_norm} " in norm:
                hits.append(kw)
        if hits:
            matched[family] = sorted(set(hits))
    return matched


# --------------------------------------------------------------------------
# Manifest handling (defensive: applicable_rules may be absent)
# --------------------------------------------------------------------------

def load_manifest(manifest_path: Path | None) -> tuple[dict | None, str | None]:
    """Returns (manifest_data, warning). Never raises."""
    if manifest_path is None:
        return None, "no manifest supplied; keyword mapping only"
    if not manifest_path.exists():
        return None, f"manifest not found at {manifest_path}; keyword mapping only"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")), None
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"manifest could not be parsed ({exc}); keyword mapping only"


def source_entry(manifest: dict | None, source_id: str) -> dict | None:
    if not manifest:
        return None
    for entry in manifest.get("sources", []):
        if isinstance(entry, dict) and entry.get("id") == source_id:
            return entry
    return None


def source_families(entry: dict | None, source_id: str) -> tuple[list[str], str | None]:
    """Families associated with the source. Prefers an explicit
    `applicable_rules` list; falls back to a labelled category guess.
    Returns (families, warning_or_None)."""
    if entry is None:
        return [], f"source-id '{source_id}' not found in manifest; keyword mapping only"
    applicable = entry.get("applicable_rules")
    if isinstance(applicable, list) and applicable and all(isinstance(x, str) for x in applicable):
        return list(applicable), None
    category = str(entry.get("category", "")).strip().lower()
    guess = CATEGORY_FAMILY_GUESS.get(category, [])
    if guess:
        return guess, (
            f"manifest entry for '{source_id}' has no 'applicable_rules'; "
            f"using category-based guess from category '{entry.get('category')}' "
            "(heuristic — verify manually)"
        )
    return [], (
        f"manifest entry for '{source_id}' has no 'applicable_rules' and an "
        "unmapped category; keyword mapping only"
    )


# --------------------------------------------------------------------------
# Test-file mapping
# --------------------------------------------------------------------------

def find_test_files(tests_dir: Path, families: list[str]) -> dict[str, list[str]]:
    """For each family, list tests/*.py files whose filename contains the
    family name or whose contents mention the family name / rule id."""
    result: dict[str, list[str]] = {fam: [] for fam in families}
    if not tests_dir.is_dir():
        return result
    test_files = sorted(tests_dir.glob("*.py"))
    contents: dict[Path, str] = {}
    for path in test_files:
        try:
            contents[path] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            contents[path] = ""
    for fam in families:
        terms = FAMILY_ALIASES.get(fam, [fam])
        for path in test_files:
            if any(t in path.name for t in terms) or any(t in contents[path] for t in terms):
                result[fam].append(path.name)
    return result


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def _truncate(text: str, limit: int = DISPLAY_TRUNCATE) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + " […]"


def build_report(
    old_text: str,
    new_text: str,
    source_id: str,
    *,
    old_label: str,
    new_label: str,
    keywords_by_family: dict[str, list[str]],
    manifest: dict | None,
    manifest_warning: str | None,
    tests_dir: Path,
) -> str:
    warnings: list[str] = []
    if manifest_warning:
        warnings.append(manifest_warning)

    entry = source_entry(manifest, source_id)
    src_families, fam_warning = source_families(entry, source_id)
    if fam_warning:
        warnings.append(fam_warning)

    old_passages = split_passages(old_text)
    new_passages = split_passages(new_text)
    changes = find_changes(old_passages, new_passages)

    # Keyword overlap per change (old and new sides both scanned).
    per_change_matches: list[dict[str, list[str]]] = []
    all_matched: dict[str, set[str]] = {}
    for change in changes:
        combined = " ".join(change["old"] + change["new"])
        matches = find_keyword_matches(combined, keywords_by_family)
        per_change_matches.append(matches)
        for fam, kws in matches.items():
            all_matched.setdefault(fam, set()).update(kws)
    matched_families = sorted(all_matched)

    # Affected families.
    if src_families:
        narrowed = [f for f in src_families if f in matched_families]
        if narrowed:
            affected = narrowed
            affected_note = "Source families narrowed to those whose rule keywords appear in the changed passages."
        elif matched_families:
            affected = matched_families
            affected_note = (
                "No overlap between the source's families and keyword-matched families; "
                "listing the keyword-matched families instead."
            )
        else:
            affected = list(src_families)
            affected_note = "Review — no keyword overlap detected in the changed passages."
    else:
        affected = matched_families
        affected_note = (
            "Derived from keyword overlap only (no source family information available)."
            if matched_families
            else "No keyword overlap detected and no source family information available."
        )
    extra_matched = [f for f in matched_families if f not in affected and f not in src_families]

    test_map = find_test_files(tests_dir, affected)

    lines: list[str] = []
    lines.append(f"# Regulatory Source Change Impact — {source_id}")
    lines.append("")
    if entry:
        lines.append(f"- Source: {entry.get('name', '(unnamed)')} ({entry.get('authority', 'unknown authority')})")
    else:
        lines.append("- Source: not found in manifest")
    lines.append(f"- Old version: {old_label}")
    lines.append(f"- New version: {new_label}")
    lines.append(
        f"- Passages: old {len(old_passages)}, new {len(new_passages)}, changed {len(changes)}"
    )
    kinds = {}
    for c in changes:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    if changes:
        lines.append("- Change kinds: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- WARNING: {w}")
    lines.append("")
    lines.append("## Changed passages")
    if not changes:
        lines.append("")
        lines.append("No changed passages detected (documents are passage-identical after whitespace normalisation).")
    for idx, (change, matches) in enumerate(zip(changes, per_change_matches), start=1):
        lines.append("")
        lines.append(f"### Change {idx} ({change['kind']})")
        for p in change["old"]:
            lines.append(f"- Old: {_truncate(p)}")
        for p in change["new"]:
            lines.append(f"- New: {_truncate(p)}")
        if matches:
            rendered = "; ".join(
                f"{fam}: {', '.join(kws)}" for fam, kws in sorted(matches.items())
            )
            lines.append(f"- Matched rule keywords: {rendered}")
        else:
            lines.append("- Matched rule keywords: none")
    lines.append("")
    lines.append("## Potentially affected rule families")
    lines.append("")
    lines.append(affected_note)
    if affected:
        for fam in affected:
            kws = sorted(all_matched.get(fam, []))
            suffix = f" (matched keywords: {', '.join(kws)})" if kws else ""
            lines.append(f"- {fam}{suffix}")
    else:
        lines.append("- None identified.")
    if extra_matched:
        lines.append("")
        lines.append("Also keyword-matched but not in the source's family list (verify manually):")
        for fam in extra_matched:
            lines.append(f"- {fam} (matched keywords: {', '.join(sorted(all_matched[fam]))})")
    lines.append("")
    lines.append("## Test files covering affected families")
    lines.append("")
    if affected:
        for fam in affected:
            files = test_map.get(fam, [])
            lines.append(f"- {fam}: {', '.join(files) if files else 'no test files found'}")
    else:
        lines.append("- None (no affected families identified).")
    lines.append("")
    lines.append("## Limitations of this analysis")
    lines.append("")
    lines.append("- Passage granularity is the paragraph (or sentence group for very long paragraphs); edits within a passage are not localised further.")
    lines.append("- Keyword overlap is a lexical heuristic: it has no semantic understanding, misses paraphrases and synonyms, and can flag incidental mentions.")
    lines.append("- Passages inside a replaced block are paired positionally; heavily restructured documents may pair unrelated passages.")
    lines.append("")
    lines.append(CLOSING_LINE)
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _read_input(path_str: str, label: str) -> str:
    path = Path(path_str)
    if not path.exists():
        raise SourceDiffError(f"{label} file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceDiffError(f"could not read {label} file {path}: {exc}")
    if not text.strip():
        raise SourceDiffError(f"{label} file is empty: {path}")
    return text


def _default_path(repo_root: Path, cwd_relative: str) -> Path:
    candidate = Path(cwd_relative)
    if candidate.exists():
        return candidate
    return repo_root / cwd_relative


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Diff two versions of a regulatory source document and "
                    "produce a human-review checklist of potentially affected "
                    "rule families and tests. Never modifies rules."
    )
    parser.add_argument("--old", required=True, help="path to the old version (plain text)")
    parser.add_argument("--new", required=True, help="path to the new version (plain text)")
    parser.add_argument("--source-id", required=True, help="source id from the manifest, e.g. FDA_AE_1")
    parser.add_argument("--manifest", default="data/raw_policies/sources_metadata.json",
                        help="path to sources_metadata.json (default: %(default)s)")
    parser.add_argument("--rules", default="config/rules.yaml",
                        help="path to rules.yaml (default: %(default)s)")
    parser.add_argument("--out", default=None, help="write the Markdown report here instead of stdout")
    args = parser.parse_args(argv)

    try:
        old_text = _read_input(args.old, "old")
        new_text = _read_input(args.new, "new")
        rules_path = _default_path(repo_root, args.rules)
        keywords = load_rule_keywords(rules_path)
    except SourceDiffError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    manifest_path = _default_path(repo_root, args.manifest)
    manifest, manifest_warning = load_manifest(manifest_path)

    report = build_report(
        old_text,
        new_text,
        args.source_id,
        old_label=args.old,
        new_label=args.new,
        keywords_by_family=keywords,
        manifest=manifest,
        manifest_warning=manifest_warning,
        tests_dir=repo_root / "tests",
    )

    if args.out:
        try:
            Path(args.out).write_text(report, encoding="utf-8")
        except OSError as exc:
            print(f"error: could not write report to {args.out}: {exc}", file=sys.stderr)
            return 2
        print(f"Wrote change-impact report to {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
