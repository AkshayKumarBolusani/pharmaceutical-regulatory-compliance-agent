"""
Phase 2 — Hybrid decision logic (deterministic).
Maps rule-engine violations to final compliance status. No LLM.
"""

from typing import Any

from .schemas import ComplianceStatus


def compute_status(violations: list[dict[str, Any]]) -> ComplianceStatus:
    """
    Deterministic status:
    - Any critical or high → FAIL
    - Else any medium → NEEDS_REVIEW
    - Else → PASS
    """
    if not violations:
        return "PASS"
    severities = {v.get("severity") for v in violations}
    if "critical" in severities or "high" in severities:
        return "FAIL"
    if "medium" in severities:
        return "NEEDS_REVIEW"
    return "PASS"
