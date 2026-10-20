#!/usr/bin/env python3
"""
Evaluation and Error Analysis Lab (Feature 2).

Runs the deterministic compliance engine (rules only: use_llm=False, no
vector index) over a labelled SYNTHETIC case set and reports per-rule
TP/FP/FN/TN, precision, recall and F1, document-status accuracy, FP/FN
examples, and a predicted NEEDS_REVIEW count.

Usage:
    python scripts/evaluate.py [--cases evaluation/labeled_cases.json]
                               [--out-prefix evaluation/results/latest]

Without --out-prefix the Markdown report is printed to stdout and nothing
is written. With --out-prefix, <prefix>.md and <prefix>.json are written
(the Markdown is still printed to stdout).

The unit of analysis is one rule family on one case: every case contributes
exactly one TP, FP, FN or TN per rule family. Precision/recall/F1 are only
reported where their denominator is > 0; otherwise the metric is reported
as n/a ("no positive cases") rather than a misleading 0.

These scores measure regression consistency of the implementation against
its own specification cases. They are NOT real-world accuracy: the cases
are synthetic, authored alongside the rules, and no labelled real-world
documents exist in this project.
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# A path that never exists, so compliance_agent.run() takes the
# deterministic rules-only path (no ChromaDB index, no LLM).
NO_INDEX = PROJECT_ROOT / "outputs" / "__evaluation_no_index__"

DEFAULT_CASES = PROJECT_ROOT / "evaluation" / "labeled_cases.json"
RULES_PATH = PROJECT_ROOT / "config" / "rules.yaml"

CAVEAT = (
    "SYNTHETIC benchmark — cases authored alongside the rules (fixtures, "
    "seeded reports, regression tests). Scores measure regression consistency "
    "of the implementation against its own specification cases. They are NOT "
    "real-world accuracy; no labelled real-world documents exist in this project."
)

UNIT_OF_ANALYSIS = "one rule family on one case"


def rule_families() -> list[str]:
    """The rule families under evaluation, in config/rules.yaml order."""
    import yaml

    with open(RULES_PATH, encoding="utf-8") as f:
        return list(yaml.safe_load(f).keys())


def load_dataset(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def case_text(case: dict) -> str:
    """Resolve a case's document text (inline 'text' or repo-relative 'file')."""
    if "text" in case:
        return case["text"]
    return (PROJECT_ROOT / case["file"]).read_text(encoding="utf-8")


def _metric(numerator: int, denominator: int):
    """Return numerator/denominator, or None when the denominator is 0."""
    if denominator <= 0:
        return None
    return numerator / denominator


def evaluate_dataset(dataset: dict) -> dict:
    """Run the engine over every case and accumulate per-rule confusion counts.

    Returns a JSON-serialisable results dict with kind='synthetic_benchmark'.
    """
    from compliance_agent import run

    families = rule_families()
    per_rule = {r: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for r in families}
    case_results = []
    false_positives = []
    false_negatives = []
    status_correct = 0
    needs_review_predicted = 0

    for case in dataset["cases"]:
        result = run(case_text(case), use_llm=False, index_path=NO_INDEX)
        fired = sorted({v["rule_id"] for v in result["violations"]})
        predicted_status = result["compliance_status"]
        expected = sorted(case["expected_rule_ids"])

        if predicted_status == "NEEDS_REVIEW":
            needs_review_predicted += 1
        status_match = predicted_status == case["expected_status"]
        if status_match:
            status_correct += 1

        for rule in families:
            is_expected = rule in expected
            is_fired = rule in fired
            counts = per_rule[rule]
            if is_expected and is_fired:
                counts["tp"] += 1
            elif is_fired:
                counts["fp"] += 1
                false_positives.append({
                    "case_id": case["id"],
                    "rule": rule,
                    "expected_rule_ids": expected,
                    "fired_rule_ids": fired,
                })
            elif is_expected:
                counts["fn"] += 1
                false_negatives.append({
                    "case_id": case["id"],
                    "rule": rule,
                    "expected_rule_ids": expected,
                    "fired_rule_ids": fired,
                })
            else:
                counts["tn"] += 1

        case_results.append({
            "id": case["id"],
            "origin": case.get("origin", ""),
            "expected_rule_ids": expected,
            "fired_rule_ids": fired,
            "expected_status": case["expected_status"],
            "predicted_status": predicted_status,
            "status_match": status_match,
        })

    for counts in per_rule.values():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        counts["precision"] = _metric(tp, tp + fp)
        counts["recall"] = _metric(tp, tp + fn)
        counts["f1"] = _metric(2 * tp, 2 * tp + fp + fn)

    total = len(dataset["cases"])
    return {
        "kind": "synthetic_benchmark",
        "dataset": dataset.get("dataset", ""),
        "dataset_kind": dataset.get("kind", ""),
        "unit_of_analysis": UNIT_OF_ANALYSIS,
        "engine_mode": "deterministic rules only (use_llm=False, no vector index)",
        "cases_total": total,
        "status_accuracy": {
            "correct": status_correct,
            "total": total,
            "fraction": _metric(status_correct, total),
        },
        "needs_review_predicted": needs_review_predicted,
        "rule_families": families,
        "per_rule": per_rule,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "cases": case_results,
    }


def _fmt_metric(value) -> str:
    if value is None:
        return "n/a (no positive cases)"
    return f"{value:.3f}"


def render_markdown(results: dict) -> str:
    lines = []
    lines.append(f"# Evaluation Lab — {results['dataset']}")
    lines.append("")
    lines.append(f"> {CAVEAT}")
    lines.append("")
    lines.append(f"- Dataset: `{results['dataset']}` (kind: {results['dataset_kind']}), "
                 f"{results['cases_total']} cases.")
    lines.append(f"- Unit of analysis: {results['unit_of_analysis']} "
                 f"(each case contributes one TP/FP/FN/TN per rule family).")
    lines.append(f"- Engine mode: {results['engine_mode']}.")
    lines.append(f"- Rule coverage: {len(results['rule_families'])} rule families "
                 f"({', '.join(results['rule_families'])}).")
    lines.append("")
    lines.append("## Document-status accuracy")
    acc = results["status_accuracy"]
    frac = acc["fraction"]
    frac_str = f"{frac:.3f}" if frac is not None else "n/a (no positive cases)"
    lines.append(f"- Exact status matches: {acc['correct']} / {acc['total']} ({frac_str})")
    lines.append(f"- Predicted NEEDS_REVIEW documents: {results['needs_review_predicted']}")
    lines.append("")
    lines.append("## Per-rule metrics (synthetic cases only)")
    lines.append("")
    lines.append("| Rule | TP | FP | FN | TN | Precision | Recall | F1 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for rule in results["rule_families"]:
        c = results["per_rule"][rule]
        lines.append(
            f"| {rule} | {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} | "
            f"{_fmt_metric(c['precision'])} | {_fmt_metric(c['recall'])} | {_fmt_metric(c['f1'])} |"
        )
    lines.append("")
    lines.append("## False positives (rule fired, not expected)")
    lines.append("")
    if results["false_positives"]:
        for fp in results["false_positives"]:
            lines.append(f"- Case `{fp['case_id']}`, rule `{fp['rule']}`: "
                         f"expected {fp['expected_rule_ids']}, fired {fp['fired_rule_ids']}")
    else:
        lines.append("- None on this dataset.")
    lines.append("")
    lines.append("## False negatives (rule expected, not fired)")
    lines.append("")
    if results["false_negatives"]:
        for fn in results["false_negatives"]:
            lines.append(f"- Case `{fn['case_id']}`, rule `{fn['rule']}`: "
                         f"expected {fn['expected_rule_ids']}, fired {fn['fired_rule_ids']}")
    else:
        lines.append("- None on this dataset.")
    lines.append("")
    lines.append("## Per-case results")
    lines.append("")
    lines.append("| Case | Expected status | Predicted status | Match | Expected rules | Fired rules |")
    lines.append("|---|---|---|---|---|---|")
    for c in results["cases"]:
        lines.append(
            f"| {c['id']} | {c['expected_status']} | {c['predicted_status']} | "
            f"{'yes' if c['status_match'] else 'NO'} | "
            f"{', '.join(c['expected_rule_ids']) or '—'} | {', '.join(c['fired_rule_ids']) or '—'} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "Unit-test pass rates, this synthetic benchmark, and real-world validation are "
        "three different kinds of evidence. This report is only the second kind: it shows "
        "the implementation behaves as specified on cases authored alongside the rules. "
        "It does not estimate performance on real pharmaceutical documents."
    )
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluation and Error Analysis Lab (synthetic benchmark).")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES,
                        help="Path to the labeled cases JSON (default: evaluation/labeled_cases.json).")
    parser.add_argument("--out-prefix", type=Path, default=None,
                        help="Write <prefix>.md and <prefix>.json in addition to printing the report.")
    args = parser.parse_args(argv)

    dataset = load_dataset(args.cases)
    results = evaluate_dataset(dataset)
    markdown = render_markdown(results)
    print(markdown)

    if args.out_prefix is not None:
        args.out_prefix.parent.mkdir(parents=True, exist_ok=True)
        md_path = args.out_prefix.with_suffix(".md")
        json_path = args.out_prefix.with_suffix(".json")
        md_path.write_text(markdown + "\n", encoding="utf-8")
        json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {md_path} and {json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
