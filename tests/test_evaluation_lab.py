"""Tests for the Evaluation and Error Analysis Lab (Feature 2).

Covers scripts/evaluate.py and evaluation/labeled_cases.json:
(a) metric arithmetic on a hand-checkable 3-case mini dataset,
(b) the shipped synthetic dataset loads, is complete, and evaluates
    end-to-end across all five rule families,
(c) the Markdown report carries the synthetic-benchmark caveat and a
    NEEDS_REVIEW count,
(d) a rule family with no positive cases reports n/a, never 0.

The mini-dataset labels in (a) are stipulated by this test to verify the
metric arithmetic; the engine's behaviour on those exact texts was
verified against the real engine (probe run, 2026-10-20). All shipped
dataset labels trace to project artifacts named in each case's origin.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location(
    "evaluate_lab", PROJECT_ROOT / "scripts" / "evaluate.py"
)
evaluate_lab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluate_lab)

FIVE_FAMILIES = {
    "privacy",
    "adverse_event",
    "off_label_promotion",
    "comparative_claims",
    "mandatory_reporting_context",
}

# (a) Mini dataset engineered so comparative_claims has exactly
# TP=1, FP=1, FN=1 (verified against the real engine):
# - TP: superiority phrase the engine detects, labelled as a claim.
# - FP: neutral methods language ("compared to the historical control
#   arm"); labelled [] by this test, the engine fires comparative_claims.
# - FN: a comparative claim phrased without any listed indicator
#   ("beats all rivals"); labelled as a claim, the engine fires nothing.
MINI_DATASET = {
    "dataset": "mini-test",
    "kind": "synthetic",
    "cases": [
        {
            "id": "mini-tp",
            "origin": "tests/test_evaluation_lab.py (stipulated label, engine-verified text)",
            "text": "The medicine is better than every competing product.",
            "expected_rule_ids": ["comparative_claims"],
            "expected_status": "NEEDS_REVIEW",
            "tags": ["mini"],
        },
        {
            "id": "mini-fp",
            "origin": "tests/test_evaluation_lab.py (stipulated label, engine-verified text)",
            "text": "In the analysis, response rates were compared to the historical control arm.",
            "expected_rule_ids": [],
            "expected_status": "PASS",
            "tags": ["mini"],
        },
        {
            "id": "mini-fn",
            "origin": "tests/test_evaluation_lab.py (stipulated label, engine-verified text)",
            "text": "Our product beats all rivals in efficacy.",
            "expected_rule_ids": ["comparative_claims"],
            "expected_status": "NEEDS_REVIEW",
            "tags": ["mini"],
        },
    ],
}


def test_mini_dataset_comparative_metrics_are_exactly_one_half():
    results = evaluate_lab.evaluate_dataset(MINI_DATASET)
    comp = results["per_rule"]["comparative_claims"]
    assert comp["tp"] == 1
    assert comp["fp"] == 1
    assert comp["fn"] == 1
    assert comp["precision"] == 0.5
    assert comp["recall"] == 0.5
    assert comp["f1"] == 0.5
    # The FP and FN examples are reported, not hidden.
    assert [e["case_id"] for e in results["false_positives"]] == ["mini-fp"]
    assert [e["case_id"] for e in results["false_negatives"]] == ["mini-fn"]
    assert results["kind"] == "synthetic_benchmark"


def test_rule_with_no_positive_cases_reports_na_not_zero():
    results = evaluate_lab.evaluate_dataset(MINI_DATASET)
    privacy = results["per_rule"]["privacy"]  # never expected, never fired
    assert privacy["tp"] == privacy["fp"] == privacy["fn"] == 0
    assert privacy["precision"] is None
    assert privacy["recall"] is None
    assert privacy["f1"] is None
    markdown = evaluate_lab.render_markdown(results)
    assert "n/a (no positive cases)" in markdown


def test_shipped_dataset_loads_and_is_complete():
    path = PROJECT_ROOT / "evaluation" / "labeled_cases.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))
    assert dataset["dataset"] == "pharma-compliance-synthetic-v1"
    assert dataset["kind"] == "synthetic"
    cases = dataset["cases"]
    assert len(cases) >= 20
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "case ids must be unique"
    for case in cases:
        assert case["origin"].strip(), f"{case['id']}: origin missing"
        assert isinstance(case["expected_rule_ids"], list)
        assert set(case["expected_rule_ids"]) <= FIVE_FAMILIES
        assert case["expected_status"] in ("PASS", "FAIL", "NEEDS_REVIEW")
        assert ("text" in case) != ("file" in case), f"{case['id']}: exactly one of text/file"


def test_shipped_dataset_evaluates_end_to_end_all_families():
    dataset = evaluate_lab.load_dataset(PROJECT_ROOT / "evaluation" / "labeled_cases.json")
    results = evaluate_lab.evaluate_dataset(dataset)
    assert results["cases_total"] == len(dataset["cases"])
    # All five rule families appear in the metrics table.
    assert set(results["per_rule"].keys()) == FIVE_FAMILIES
    for rule in FIVE_FAMILIES:
        counts = results["per_rule"][rule]
        total = counts["tp"] + counts["fp"] + counts["fn"] + counts["tn"]
        assert total == results["cases_total"], f"{rule}: unit-of-analysis accounting broken"
    acc = results["status_accuracy"]
    assert acc["total"] == results["cases_total"]
    assert 0 <= acc["correct"] <= acc["total"]


def test_markdown_carries_synthetic_caveat_and_needs_review_count():
    dataset = evaluate_lab.load_dataset(PROJECT_ROOT / "evaluation" / "labeled_cases.json")
    results = evaluate_lab.evaluate_dataset(dataset)
    markdown = evaluate_lab.render_markdown(results)
    assert "SYNTHETIC benchmark" in markdown
    assert "They are NOT real-world accuracy" in markdown
    assert "no labelled real-world documents exist in this project" in markdown
    assert "Predicted NEEDS_REVIEW documents:" in markdown
    assert f"Predicted NEEDS_REVIEW documents: {results['needs_review_predicted']}" in markdown


def test_cli_prints_report_and_writes_nothing_by_default(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "evaluate.py")],
        capture_output=True, text=True, cwd=tmp_path, timeout=120,
    )
    assert proc.returncode == 0
    assert "SYNTHETIC benchmark" in proc.stdout
    assert "Per-rule metrics" in proc.stdout
    # Nothing is written unless --out-prefix is given (cwd stays empty).
    assert list(tmp_path.iterdir()) == []


def test_cli_out_prefix_writes_md_and_json(tmp_path):
    prefix = tmp_path / "results" / "latest"
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "evaluate.py"),
         "--out-prefix", str(prefix)],
        capture_output=True, text=True, cwd=tmp_path, timeout=120,
    )
    assert proc.returncode == 0
    md = prefix.with_suffix(".md").read_text(encoding="utf-8")
    data = json.loads(prefix.with_suffix(".json").read_text(encoding="utf-8"))
    assert "SYNTHETIC benchmark" in md
    assert data["kind"] == "synthetic_benchmark"
    assert data["cases_total"] >= 20
