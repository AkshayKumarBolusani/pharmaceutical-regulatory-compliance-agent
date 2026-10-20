"""
Phase 2 — Structured output types for auditable compliance decisions.
Matches the required JSON shape; used by rule_engine, rag_explainer, hybrid_decision.

Feature 1 (evidence trace, 2026-10-20): violations carry a deterministic
finding_id, the exact matched spans from the input ("matches", plus the
first span promoted to matched_text/context), an evidence_status
("supported" only when a retrieved regulatory clause backs the finding,
else "insufficient_evidence"), and origin fields distinguishing the
deterministic rule result from any optional LLM explanation. Retrieved
regulations carry source-manifest metadata (source_id, title,
version_date, official_url, country, category) when known — never invented.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Literal


Severity = Literal["low", "medium", "high", "critical"]
ComplianceStatus = Literal["PASS", "FAIL", "NEEDS_REVIEW"]


@dataclass
class RetrievedRegulation:
    """One retrieved regulatory clause (from RAG)."""
    source: str
    text: str
    source_id: str = ""
    title: str = ""
    version_date: str = ""
    official_url: str = ""
    country: str = ""
    category: str = ""


def regulation_to_dict(r: RetrievedRegulation) -> dict:
    return {
        "source": r.source,
        "text": r.text,
        "source_id": r.source_id,
        "title": r.title,
        "version_date": r.version_date,
        "official_url": r.official_url,
        "country": r.country,
        "category": r.category,
    }


def compute_finding_id(rule_id: str, matches: list, evidence_text: str = "") -> str:
    """Deterministic finding ID: same rule + same first match -> same ID
    across runs, so findings can be tracked in a review/audit history."""
    if matches:
        first = matches[0]
        basis = f"{rule_id}|{first.get('matched_text', '')}|{first.get('start', '')}"
    else:
        basis = f"{rule_id}|{evidence_text}"
    return "F-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:10]


def apply_trace(violation: "Violation", raw: dict) -> "Violation":
    """Populate the Feature-1 trace fields of a Violation from the raw
    rule-engine dict (its "matches" list). Mutates and returns violation."""
    matches = list(raw.get("matches") or [])[:5]
    violation.matches = matches
    if matches:
        violation.matched_text = matches[0].get("matched_text", "")
        violation.context = matches[0].get("context", "")
    violation.finding_id = compute_finding_id(
        violation.rule_id, matches, violation.evidence
    )
    return violation


@dataclass
class Violation:
    """Single violation: rule-based evidence + optional LLM-generated explanation."""
    type: str
    severity: Severity
    evidence: str
    rule_id: str
    regulatory_basis: str = ""
    explanation: str = ""
    suggested_fix: str = ""
    retrieved_regulations: list[RetrievedRegulation] = field(default_factory=list)
    # --- Feature 1: evidence trace ---
    finding_id: str = ""
    matched_text: str = ""
    context: str = ""
    matches: list = field(default_factory=list)
    evidence_status: str = "insufficient_evidence"
    origin: str = "deterministic_rule"
    explanation_origin: str = "none"
    source_title: str = ""
    source_version: str = ""
    source_url: str = ""


@dataclass
class ComplianceReport:
    """Full output for one submitted report (auditable)."""
    compliance_status: ComplianceStatus
    violations: list[Violation]
    retrieved_regulations: list[RetrievedRegulation]

    def to_dict(self) -> dict:
        """Serialize to the required JSON shape."""
        return {
            "compliance_status": self.compliance_status,
            "violations": [
                {
                    "type": v.type,
                    "severity": v.severity,
                    "evidence": v.evidence,
                    "rule_id": v.rule_id,
                    "regulatory_basis": v.regulatory_basis,
                    "explanation": v.explanation,
                    "suggested_fix": v.suggested_fix,
                    "finding_id": v.finding_id,
                    "matched_text": v.matched_text,
                    "context": v.context,
                    "matches": v.matches,
                    "evidence_status": v.evidence_status,
                    "origin": v.origin,
                    "explanation_origin": v.explanation_origin,
                    "source_title": v.source_title,
                    "source_version": v.source_version,
                    "source_url": v.source_url,
                    "retrieved_regulations": [
                        regulation_to_dict(r) for r in v.retrieved_regulations
                    ],
                }
                for v in self.violations
            ],
            "retrieved_regulations": [
                regulation_to_dict(r) for r in self.retrieved_regulations
            ],
        }
