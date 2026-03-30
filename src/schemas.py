"""
Phase 2 — Structured output types for auditable compliance decisions.
Matches the required JSON shape; used by rule_engine, rag_explainer, hybrid_decision.
"""

from dataclasses import dataclass, field
from typing import Literal


Severity = Literal["low", "medium", "high", "critical"]
ComplianceStatus = Literal["PASS", "FAIL", "NEEDS_REVIEW"]


@dataclass
class RetrievedRegulation:
    """One retrieved regulatory clause (from RAG)."""
    source: str
    text: str


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
                }
                for v in self.violations
            ],
            "retrieved_regulations": [
                {"source": r.source, "text": r.text}
                for r in self.retrieved_regulations
            ],
        }
