"""Tests for scripts/source_diff.py (Feature F5 — regulatory change impact).

All source documents used here are SYNTHETIC fixtures written for these
tests. They imitate the *shape* of a regulator guidance document but are
entirely fictional: the "Exampleland Medicines Authority" does not exist
and none of the text is real regulatory content.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "source_diff.py"

spec = importlib.util.spec_from_file_location("source_diff", SCRIPT_PATH)
source_diff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_diff)

RULES_PATH = PROJECT_ROOT / "config" / "rules.yaml"
MANIFEST_PATH = PROJECT_ROOT / "data" / "raw_policies" / "sources_metadata.json"
TESTS_DIR = PROJECT_ROOT / "tests"

HEADER = (
    "SYNTHETIC GUIDANCE DOCUMENT — Exampleland Medicines Authority (fictional).\n"
    "This is a test fixture, not a real regulatory document."
)

BOILERPLATE_A = (
    "Section 1. Scope. This guidance applies to all holders of marketing "
    "authorisations granted in Exampleland and to their authorised representatives."
)

BOILERPLATE_C = (
    "Section 3. Record keeping. Holders must retain submission records for a "
    "minimum of ten years and make them available on request."
)

OLD_AE_PARAGRAPH = (
    "Section 2. Expedited reporting. Holders must report adverse reactions "
    "observed during monitoring within fifteen calendar days of first awareness."
)

NEW_AE_PARAGRAPH = (
    "Section 2. Expedited reporting. Holders must report adverse reactions, "
    "including anaphylaxis, observed during monitoring within fifteen "
    "calendar days of first awareness."
)

OLD_FORMAT_PARAGRAPH = (
    "Section 2. Submission format. Submissions must be transmitted "
    "electronically using the standard form before the deadline."
)

NEW_FORMAT_PARAGRAPH = (
    "Section 2. Submission format. Submissions must be sent through the "
    "online portal using the current form before the deadline."
)


def _doc(*paragraphs: str) -> str:
    return "\n\n".join(paragraphs) + "\n"


def _report(old: str, new: str, source_id: str = "FDA_AE_1") -> str:
    keywords = source_diff.load_rule_keywords(RULES_PATH)
    manifest, warning = source_diff.load_manifest(MANIFEST_PATH)
    return source_diff.build_report(
        old,
        new,
        source_id,
        old_label="old.txt",
        new_label="new.txt",
        keywords_by_family=keywords,
        manifest=manifest,
        manifest_warning=warning,
        tests_dir=TESTS_DIR,
    )


# ---------------------------------------------------------------------------
# Keyword-mapping behaviour
# ---------------------------------------------------------------------------

def test_introduced_ae_keyword_maps_to_adverse_event():
    old = _doc(HEADER, BOILERPLATE_A, OLD_AE_PARAGRAPH, BOILERPLATE_C)
    new = _doc(HEADER, BOILERPLATE_A, NEW_AE_PARAGRAPH, BOILERPLATE_C)
    report = _report(old, new)
    assert "changed 1" in report
    assert "anaphylaxis" in report
    assert "adverse_event" in report
    # The family must be listed in the affected-families section and have
    # at least one covering test file in this repository.
    affected_section = report.split("## Potentially affected rule families")[1]
    assert "adverse_event" in affected_section
    tests_section = report.split("## Test files covering affected families")[1]
    assert "adverse_event" in tests_section
    test_map = source_diff.find_test_files(TESTS_DIR, ["adverse_event"])
    assert test_map["adverse_event"], "expected at least one test file mentioning adverse_event"


def test_unrelated_wording_change_has_no_keyword_overlap():
    old = _doc(HEADER, BOILERPLATE_A, OLD_FORMAT_PARAGRAPH, BOILERPLATE_C)
    new = _doc(HEADER, BOILERPLATE_A, NEW_FORMAT_PARAGRAPH, BOILERPLATE_C)
    report = _report(old, new)
    assert "changed 1" in report
    assert "online portal" in report  # the changed passage itself is reported
    assert "Matched rule keywords: none" in report
    assert "no keyword overlap" in report.lower()


def test_identical_documents_report_zero_changes():
    doc = _doc(HEADER, BOILERPLATE_A, OLD_AE_PARAGRAPH, BOILERPLATE_C)
    report = _report(doc, doc)
    assert "changed 0" in report
    assert "No changed passages detected" in report


def test_unknown_source_id_warns_and_still_maps_keywords():
    old = _doc(HEADER, BOILERPLATE_A, OLD_AE_PARAGRAPH, BOILERPLATE_C)
    new = _doc(HEADER, BOILERPLATE_A, NEW_AE_PARAGRAPH, BOILERPLATE_C)
    report = _report(old, new, source_id="NO_SUCH_SOURCE_999")
    assert "WARNING" in report
    assert "not found in manifest" in report
    assert "adverse_event" in report  # keyword mapping still works
    assert source_diff.CLOSING_LINE in report


def test_long_paragraph_is_split_into_sentence_groups():
    long_para = " ".join(
        f"Sentence number {i} of a very long synthetic paragraph." for i in range(30)
    )
    assert len(long_para) > source_diff.MAX_PARAGRAPH_CHARS
    passages = source_diff.split_passages(long_para)
    assert len(passages) > 1


# ---------------------------------------------------------------------------
# CLI behaviour (subprocess: exit codes and clean error handling)
# ---------------------------------------------------------------------------

def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )


def test_cli_missing_file_exits_cleanly(tmp_path):
    result = _run_cli(
        "--old", str(tmp_path / "does_not_exist.txt"),
        "--new", str(tmp_path / "also_missing.txt"),
        "--source-id", "FDA_AE_1",
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "error" in result.stderr.lower()
    assert "not found" in result.stderr.lower()


def test_cli_empty_file_exits_cleanly(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    full = tmp_path / "full.txt"
    full.write_text(_doc(HEADER, OLD_AE_PARAGRAPH), encoding="utf-8")
    result = _run_cli(
        "--old", str(empty), "--new", str(full), "--source-id", "FDA_AE_1",
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "empty" in result.stderr.lower()


def test_cli_happy_path_prints_checklist(tmp_path):
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    old.write_text(_doc(HEADER, BOILERPLATE_A, OLD_AE_PARAGRAPH, BOILERPLATE_C), encoding="utf-8")
    new.write_text(_doc(HEADER, BOILERPLATE_A, NEW_AE_PARAGRAPH, BOILERPLATE_C), encoding="utf-8")
    result = _run_cli(
        "--old", str(old), "--new", str(new), "--source-id", "FDA_AE_1",
    )
    assert result.returncode == 0
    assert "anaphylaxis" in result.stdout
    assert "adverse_event" in result.stdout
    assert source_diff.CLOSING_LINE in result.stdout
