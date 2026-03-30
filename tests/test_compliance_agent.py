"""
Phase 2 — Test suite for compliance agent.
Uses synthetic reports only. Asserts violations and final decision.
"""

import json
import sys
from pathlib import Path

# Add project root so "src" and "compliance_agent" are importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from compliance_agent import run
from tests.fixtures.synthetic_reports import (
    CLEAN_REPORT,
    PRIVACY_VIOLATION_REPORT,
    OFF_LABEL_REPORT,
    AE_WITHOUT_REPORTING_REPORT,
    COMPARATIVE_CLAIM_REPORT,
    ALL_CASES,
)


def test_clean_report():
    """Clean report → PASS, no violations."""
    result = run(CLEAN_REPORT, use_llm=False)
    assert result["compliance_status"] == "PASS"
    assert len(result["violations"]) == 0


def test_privacy_violation():
    """PII present → FAIL, critical violation."""
    result = run(PRIVACY_VIOLATION_REPORT, use_llm=False)
    assert result["compliance_status"] == "FAIL"
    violations = result["violations"]
    assert any(v["rule_id"] == "privacy" and v["severity"] == "critical" for v in violations)


def test_off_label():
    """Off-label phrasing → FAIL (high)."""
    result = run(OFF_LABEL_REPORT, use_llm=False)
    assert result["compliance_status"] == "FAIL"
    assert any(v["rule_id"] == "off_label_promotion" for v in result["violations"])


def test_ae_without_reporting():
    """AE keywords, no escalation flags → FAIL (high)."""
    result = run(AE_WITHOUT_REPORTING_REPORT, use_llm=False)
    assert result["compliance_status"] == "FAIL"
    assert any(v["rule_id"] == "adverse_event" for v in result["violations"])


def test_comparative_claim():
    """Comparative language → NEEDS_REVIEW (medium)."""
    result = run(COMPARATIVE_CLAIM_REPORT, use_llm=False)
    assert result["compliance_status"] == "NEEDS_REVIEW"
    assert any(v["rule_id"] == "comparative_claims" for v in result["violations"])


def test_all_cases_deterministic():
    """All synthetic cases: status matches expected (without LLM)."""
    for name, text, expected_status in ALL_CASES:
        result = run(text, use_llm=False)
        assert result["compliance_status"] == expected_status, (
            f"Case {name}: expected {expected_status}, got {result['compliance_status']}"
        )


def test_output_structure():
    """Output has required keys and types."""
    result = run(CLEAN_REPORT, use_llm=False)
    assert "compliance_status" in result
    assert result["compliance_status"] in ("PASS", "FAIL", "NEEDS_REVIEW")
    assert "violations" in result
    assert isinstance(result["violations"], list)
    assert "retrieved_regulations" in result
    assert isinstance(result["retrieved_regulations"], list)
    # Round-trip JSON
    json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
