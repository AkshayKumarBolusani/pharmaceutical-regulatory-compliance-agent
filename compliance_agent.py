#!/usr/bin/env python3
"""
Phase 2 — Compliance agent orchestrator (backend-only, no UI).
Runs: rule_engine → rag_explainer → hybrid_decision → structured JSON.
Reads Phase 1 artifacts only (config/rules.yaml, outputs/vector_index/).
Uses Groq if GROQ_API_KEY is set, else OpenAI if OPENAI_API_KEY is set.
"""

import json
import os
import sys
from pathlib import Path

# Load .env so GROQ_API_KEY / OPENAI_API_KEY are set (do not commit .env)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# Project root = parent of src/
PROJECT_ROOT = Path(__file__).resolve().parent
RULES_PATH = PROJECT_ROOT / "config" / "rules.yaml"
INDEX_PATH = PROJECT_ROOT / "outputs" / "vector_index"


def run(
    report_text: str,
    *,
    top_k: int = 3,
    use_llm: bool = True,
    rules_path: Path | None = None,
    index_path: Path | None = None,
) -> dict:
    """
    Run full compliance pipeline. Returns single JSON-serializable dict with
    compliance_status, violations, retrieved_regulations.
    """
    rules_path = rules_path or RULES_PATH
    index_path = index_path or INDEX_PATH

    from src.rule_engine import run_checks
    from src.rag_explainer import enrich_violations_with_rag
    from src.hybrid_decision import compute_status
    from src.schemas import ComplianceReport

    raw_violations = run_checks(report_text, rules_path)
    status = compute_status(raw_violations)

    if index_path.exists():
        violations, all_retrieved = enrich_violations_with_rag(
            raw_violations, index_path, top_k=top_k, use_llm=use_llm
        )
    else:
        violations = [
            __violation_from_raw(v) for v in raw_violations
        ]
        all_retrieved = []

    report = ComplianceReport(
        compliance_status=status,
        violations=violations,
        retrieved_regulations=all_retrieved,
    )
    return report.to_dict()


def __violation_from_raw(v: dict):
    from src.schemas import Violation
    return Violation(
        type=v["violation_type"],
        severity=v["severity"],
        evidence=v["evidence_text"],
        rule_id=v["rule_id"],
        regulatory_basis="",
        explanation="",
        suggested_fix="",
        retrieved_regulations=[],
    )


def main():
    """CLI: read report from file or stdin; print JSON to stdout."""
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(json.dumps({"error": f"File not found: {path}. Use a path to an existing .txt file."}), file=sys.stderr)
            sys.exit(1)
        report_text = path.read_text(encoding="utf-8")
    else:
        report_text = sys.stdin.read()
    use_llm = os.environ.get("COMPLIANCE_USE_LLM", "1").strip().lower() in ("1", "true", "yes")
    result = run(report_text, use_llm=use_llm)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
