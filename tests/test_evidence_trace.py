"""Feature 1 — Evidence-First Compliance Trace (workstream E1).

Verifies that every violation carries a deterministic finding_id, the exact
matched span(s) from the input with sentence context, an honest
evidence_status ("insufficient_evidence" until retrieval actually backs the
finding), and provenance fields distinguishing the deterministic rule result
from any LLM explanation. Also verifies that the source-manifest join fills
title/version/URL only from a real manifest entry, and that the seeded
synthetic reports still produce the pre-Feature-1 statuses and rule_ids.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import src.rag_explainer as rag_explainer
from compliance_agent import run
from src.schemas import RetrievedRegulation
from tests.fixtures.synthetic_reports import PRIVACY_VIOLATION_REPORT

NO_INDEX = "no_such_index_dir"


def _privacy_violation(result):
    return next(v for v in result["violations"] if v["rule_id"] == "privacy")


def test_trace_fields_on_privacy_fixture(tmp_path):
    result = run(PRIVACY_VIOLATION_REPORT, use_llm=False, index_path=tmp_path / NO_INDEX)
    v = _privacy_violation(result)
    assert v["finding_id"].startswith("F-")
    assert len(v["finding_id"]) == 12  # "F-" + 10 hex chars
    assert v["matched_text"]
    assert v["matched_text"] in PRIVACY_VIOLATION_REPORT
    assert v["context"]
    assert v["matched_text"] in v["context"]
    assert v["matches"], "trace matches must be present"
    for m in v["matches"]:
        # Span integrity: the recorded offsets point at the recorded text.
        assert PRIVACY_VIOLATION_REPORT[m["start"]:m["end"]] == m["matched_text"]
        assert m["matched_text"] in m["context"]


def test_finding_ids_are_deterministic(tmp_path):
    kwargs = dict(use_llm=False, index_path=tmp_path / NO_INDEX)
    first = run(PRIVACY_VIOLATION_REPORT, **kwargs)
    second = run(PRIVACY_VIOLATION_REPORT, **kwargs)
    assert [v["finding_id"] for v in first["violations"]] == \
           [v["finding_id"] for v in second["violations"]]


def test_no_index_means_insufficient_evidence(tmp_path):
    result = run(PRIVACY_VIOLATION_REPORT, use_llm=False, index_path=tmp_path / NO_INDEX)
    assert result["violations"], "fixture must produce violations"
    for v in result["violations"]:
        assert v["evidence_status"] == "insufficient_evidence"
        assert v["origin"] == "deterministic_rule"
        assert v["explanation_origin"] == "none"
        assert v["source_title"] == ""
        assert v["retrieved_regulations"] == []


def test_manifest_join_marks_supported_and_populates_source(tmp_path, monkeypatch):
    stub_clause = RetrievedRegulation(
        source="FDA",
        text="Sponsors must report serious adverse events to the agency.",
        source_id="TEST_SRC",
        country="USA",
        category="Adverse events",
    )
    monkeypatch.setattr(
        rag_explainer, "retrieve", lambda query, index_path, top_k=3: [stub_clause]
    )
    monkeypatch.setattr(
        rag_explainer, "_manifest_map",
        lambda: {"TEST_SRC": {
            "name": "Test Guidance for Industry",
            "version_date": "2024-01",
            "official_url": "https://example.gov/test-guidance",
            "file": "TEST_SRC.pdf",
        }},
    )
    # tmp_path exists, so run() takes the enrichment path.
    result = run(PRIVACY_VIOLATION_REPORT, use_llm=False, index_path=tmp_path)
    v = _privacy_violation(result)
    assert v["evidence_status"] == "supported"
    assert v["source_title"] == "Test Guidance for Industry"
    assert v["source_version"] == "2024-01"
    assert v["source_url"] == "https://example.gov/test-guidance"
    assert v["explanation_origin"] == "none"  # use_llm=False: no LLM ran
    assert v["origin"] == "deterministic_rule"
    # Per-violation retrieved_regulations must be present in the JSON dict
    # (to_dict previously dropped them silently).
    regs = v["retrieved_regulations"]
    assert len(regs) == 1
    assert regs[0]["source_id"] == "TEST_SRC"
    assert regs[0]["title"] == "Test Guidance for Industry"
    assert regs[0]["official_url"] == "https://example.gov/test-guidance"
    # Trace fields survive the enrichment path too.
    assert v["finding_id"].startswith("F-")
    assert v["matched_text"] in PRIVACY_VIOLATION_REPORT


SEEDED_EXPECTED = {
    "01_clean.txt": ("PASS", []),
    "02_privacy_violation.txt": ("FAIL", ["privacy"]),
    "03_off_label.txt": ("FAIL", ["off_label_promotion"]),
    "04_ae_without_reporting.txt": ("FAIL", ["adverse_event"]),
    "05_comparative_claim.txt": ("NEEDS_REVIEW", ["comparative_claims"]),
    "06_ae_mandatory_reporting.txt": ("FAIL", ["mandatory_reporting_context"]),
}


def test_seeded_reports_parity(tmp_path):
    """Regression parity: Part 1 + Part 2 must not change the seeded
    reports' statuses or rule_ids."""
    reports_dir = PROJECT_ROOT / "synthetic_reports"
    for fname, (status, rule_ids) in SEEDED_EXPECTED.items():
        text = (reports_dir / fname).read_text(encoding="utf-8")
        result = run(text, use_llm=False, index_path=tmp_path / NO_INDEX)
        assert result["compliance_status"] == status, fname
        assert sorted(v["rule_id"] for v in result["violations"]) == rule_ids, fname
