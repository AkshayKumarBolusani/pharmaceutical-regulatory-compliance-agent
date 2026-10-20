"""
Workstream C — API / CLI / schema robustness tests.

Covers the orchestrator entry points (compliance_agent.run and the CLI in
compliance_agent.main) plus the FastAPI layer's request validation, using
synthetic inputs only. No network, no LLM keys, no vector index: run() is
pointed at a nonexistent index path so the rules-only degradation path is
what is exercised.

Semantics asserted here for empty input: run("") returns PASS with zero
violations, meaning "nothing to check" — it is NOT a claim that a document
is legally compliant. No implemented rule firing is all PASS ever means.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Add project root so "src" and "compliance_agent" are importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from compliance_agent import run

REPORT_KEYS = {"compliance_status", "violations", "retrieved_regulations"}
VIOLATION_KEYS = {
    "type", "severity", "evidence", "rule_id",
    "regulatory_basis", "explanation", "suggested_fix",
    # Feature 1 (Evidence-First Compliance Trace, 2026-10-20):
    "finding_id", "matched_text", "context", "matches",
    "evidence_status", "origin", "explanation_origin",
    "source_title", "source_version", "source_url",
    "retrieved_regulations",
}
STATUSES = {"PASS", "FAIL", "NEEDS_REVIEW"}


@pytest.fixture()
def missing_index(tmp_path):
    """A path that does not exist -> forces the rules-only degradation path."""
    return tmp_path / "no_vector_index_here"


def _run_rules_only(text, missing_index):
    return run(text, use_llm=False, index_path=missing_index)


def _assert_valid_report(report):
    assert set(report.keys()) == REPORT_KEYS
    assert report["compliance_status"] in STATUSES
    assert isinstance(report["violations"], list)
    assert isinstance(report["retrieved_regulations"], list)
    for v in report["violations"]:
        assert set(v.keys()) == VIOLATION_KEYS
    json.dumps(report)  # must be JSON-serializable


# ---------------------------------------------------------------------------
# run() edge cases
# ---------------------------------------------------------------------------

def test_run_empty_string(missing_index):
    """Empty input: PASS + zero violations = 'nothing to check', not
    a compliance certification."""
    report = _run_rules_only("", missing_index)
    _assert_valid_report(report)
    assert report["compliance_status"] == "PASS"
    assert report["violations"] == []
    assert report["retrieved_regulations"] == []


def test_run_whitespace_only(missing_index):
    report = _run_rules_only("   \n\t  \r\n ", missing_index)
    _assert_valid_report(report)
    assert report["compliance_status"] == "PASS"
    assert report["violations"] == []


def test_run_keywords_only_text(missing_index):
    """Text that is nothing but AE trigger keywords still produces a valid
    report (adverse_event fires: keywords present, no reporting context)."""
    report = _run_rules_only(
        "nausea dizziness headache vomiting diarrhea rash fatigue", missing_index
    )
    _assert_valid_report(report)
    assert report["compliance_status"] == "FAIL"
    assert any(v["rule_id"] == "adverse_event" for v in report["violations"])


def test_run_unicode_text(missing_index):
    """Unicode/emoji/CJK/Cyrillic text must not crash and must return a
    valid report."""
    text = "Patient reported Übelkeit 🤢, 吐き気 and головная боль after the dose."
    report = _run_rules_only(text, missing_index)
    _assert_valid_report(report)


def test_run_crlf_line_endings(missing_index):
    """CRLF text behaves like LF text, including negation handling:
    'No hospitalization was required' must not count as reporting context."""
    text = "The patient had nausea.\r\nNo hospitalization was required.\r\n"
    report = _run_rules_only(text, missing_index)
    _assert_valid_report(report)
    rule_ids = {v["rule_id"] for v in report["violations"]}
    assert "adverse_event" in rule_ids
    assert "mandatory_reporting_context" not in rule_ids


def test_run_no_trailing_newline(missing_index):
    report = _run_rules_only("The patient had nausea and dizziness", missing_index)
    _assert_valid_report(report)
    assert report["compliance_status"] == "FAIL"


def test_run_very_long_document(missing_index):
    """~200k characters: still a valid report, no crash."""
    text = "The patient reported mild nausea after the dose. " * 4200
    assert len(text) > 200_000
    report = _run_rules_only(text, missing_index)
    _assert_valid_report(report)
    assert report["compliance_status"] == "FAIL"
    assert any(v["rule_id"] == "adverse_event" for v in report["violations"])


def test_run_deterministic(missing_index):
    """Same input twice (LLM off) -> byte-identical JSON."""
    text = "Patient John Smith, 555-123-4567, had nausea."
    a = json.dumps(_run_rules_only(text, missing_index), indent=2, ensure_ascii=False)
    b = json.dumps(_run_rules_only(text, missing_index), indent=2, ensure_ascii=False)
    assert a == b


def test_run_missing_index_graceful_degradation(missing_index):
    """No vector index + LLM off: violations are still produced, with
    explanation fields explicitly EMPTY (rules-only), not an exception
    and not fabricated content."""
    report = _run_rules_only("Patient John Smith had nausea.", missing_index)
    _assert_valid_report(report)
    assert report["retrieved_regulations"] == []
    assert report["violations"], "expected at least one violation for this input"
    for v in report["violations"]:
        assert v["explanation"] == ""
        assert v["suggested_fix"] == ""
        assert v["regulatory_basis"] == ""


# ---------------------------------------------------------------------------
# CLI (subprocess) edge cases
# ---------------------------------------------------------------------------

def _cli(args, stdin_text=None):
    env = dict(os.environ, COMPLIANCE_USE_LLM="0")
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "compliance_agent.py"), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
        timeout=120,
    )


def test_cli_nonexistent_file_json_error(tmp_path):
    proc = _cli([str(tmp_path / "does_not_exist.txt")])
    assert proc.returncode != 0
    assert proc.stdout == ""
    err = json.loads(proc.stderr)  # error must be JSON, not a traceback
    assert "error" in err
    assert "Traceback" not in proc.stderr


def test_cli_directory_argument_json_error(tmp_path):
    """Passing a directory used to crash with an IsADirectoryError
    traceback; it must produce the same JSON error shape as a missing
    file. (Fixed in compliance_agent.main, 2026-10-20.)"""
    proc = _cli([str(tmp_path)])
    assert proc.returncode != 0
    assert proc.stdout == ""
    err = json.loads(proc.stderr)
    assert "error" in err
    assert "Traceback" not in proc.stderr


def test_cli_invalid_utf8_file_json_error(tmp_path):
    """A non-UTF-8 file used to crash with a UnicodeDecodeError traceback;
    it must produce a JSON error. (Fixed in compliance_agent.main,
    2026-10-20.)"""
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"Patient had nausea \xff\xfe binary")
    proc = _cli([str(bad)])
    assert proc.returncode != 0
    assert proc.stdout == ""
    err = json.loads(proc.stderr)
    assert "error" in err
    assert "Traceback" not in proc.stderr


def test_cli_valid_file(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("Patient John Smith had nausea.", encoding="utf-8")
    proc = _cli([str(f)])
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    _assert_valid_report(report)
    assert report["compliance_status"] == "FAIL"


def test_cli_file_without_trailing_newline(tmp_path):
    f = tmp_path / "report.txt"
    f.write_bytes(b"The patient had nausea and dizziness")  # no trailing \n
    proc = _cli([str(f)])
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    _assert_valid_report(report)
    assert report["compliance_status"] == "FAIL"


def test_cli_stdin_empty():
    proc = _cli([], stdin_text="")
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    _assert_valid_report(report)
    assert report["compliance_status"] == "PASS"
    assert report["violations"] == []


def test_cli_stdin_violation_text():
    proc = _cli([], stdin_text="The patient had nausea and dizziness.")
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    _assert_valid_report(report)
    assert report["compliance_status"] == "FAIL"


def test_cli_deterministic_stdout(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("Patient John Smith, 555-123-4567, had nausea.", encoding="utf-8")
    first = _cli([str(f)])
    second = _cli([str(f)])
    assert first.returncode == 0 and second.returncode == 0
    assert first.stdout == second.stdout  # byte-identical


# ---------------------------------------------------------------------------
# API layer (FastAPI TestClient) — request validation only.
# Tests using the client fixture skip automatically if fastapi/httpx are
# not installed; the run()/CLI tests above do not depend on them.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi", reason="fastapi not installed")
    pytest.importorskip("httpx", reason="httpx not installed")
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_api_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_valid_body_schema(client, monkeypatch):
    monkeypatch.setenv("COMPLIANCE_USE_LLM", "0")
    resp = client.post(
        "/check_compliance",
        json={"report_text": "Patient John Smith had nausea."},
    )
    assert resp.status_code == 200
    report = resp.json()
    _assert_valid_report(report)
    assert report["compliance_status"] == "FAIL"


def test_api_missing_report_text_422(client):
    resp = client.post("/check_compliance", json={})
    assert resp.status_code == 422


def test_api_wrong_type_report_text_422(client):
    resp = client.post("/check_compliance", json={"report_text": 12345})
    assert resp.status_code == 422


def test_api_null_report_text_422(client):
    resp = client.post("/check_compliance", json={"report_text": None})
    assert resp.status_code == 422


def test_api_empty_string_value(client, monkeypatch):
    """Empty string is a VALID body: the API returns the same empty
    report as run('') — PASS + zero violations ('nothing to check')."""
    monkeypatch.setenv("COMPLIANCE_USE_LLM", "0")
    resp = client.post("/check_compliance", json={"report_text": ""})
    assert resp.status_code == 200
    report = resp.json()
    _assert_valid_report(report)
    assert report["compliance_status"] == "PASS"
    assert report["violations"] == []
