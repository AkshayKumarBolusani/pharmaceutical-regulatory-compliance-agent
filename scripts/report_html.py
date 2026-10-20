#!/usr/bin/env python3
"""
Render a standalone, readable HTML report from an automated compliance
report JSON, optionally joined with human review decisions from the
append-only review log (scripts/review.py).

Usage:
    python scripts/report_html.py --report report.json \
        [--log reviews.jsonl] --out report.html

Properties:
- Single self-contained HTML file; inline CSS only; NO external assets.
- Every piece of report/log text is HTML-escaped before rendering —
  report text is untrusted input and must never become markup.
- The status banner always carries the standing disclaimer: these are
  automated preliminary flags for qualified human review, not a legal
  compliance determination.

Stdlib only.
"""

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review import read_records, report_sha256  # noqa: E402  (shared keying/hashing)

DISCLAIMER = (
    "Automated preliminary flags for qualified human review — "
    "not a legal compliance determination"
)

STYLE = """
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
       margin: 2rem auto; max-width: 960px; padding: 0 1rem; color: #1a1a1a; }
.banner { border: 2px solid #8a6d00; background: #fff8e1; padding: 1rem 1.25rem;
          border-radius: 6px; }
.banner .status { font-size: 1.4rem; font-weight: 700; }
.banner .disclaimer { margin-top: 0.35rem; font-weight: 600; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }
th, td { border: 1px solid #ccc; padding: 0.45rem 0.6rem; text-align: left;
         vertical-align: top; }
th { background: #f2f2f2; }
.sev-critical { color: #b71c1c; font-weight: 700; }
.sev-high { color: #e65100; font-weight: 700; }
.sev-medium { color: #8a6d00; font-weight: 700; }
code { background: #f5f5f5; padding: 0 0.25rem; border-radius: 3px; }
.reg { border-left: 4px solid #90a4ae; padding: 0.4rem 0.8rem; margin: 0.5rem 0;
       background: #fafafa; white-space: pre-wrap; }
.empty { color: #666; font-style: italic; }
footer { color: #666; font-size: 0.85rem; margin-top: 2rem; }
"""


def esc(value) -> str:
    """HTML-escape any value (None-safe). Untrusted text goes through here."""
    return html.escape("" if value is None else str(value), quote=True)


def render(report: dict, decisions: list[dict]) -> str:
    status = esc(report.get("compliance_status", "UNKNOWN"))
    violations = report.get("violations", []) or []
    regulations = report.get("retrieved_regulations", []) or []

    if violations:
        rows = []
        for v in violations:
            sev = str(v.get("severity", ""))
            rows.append(
                "<tr>"
                f"<td>{esc(v.get('type'))}</td>"
                f"<td class=\"sev-{esc(sev)}\">{esc(sev)}</td>"
                f"<td><code>{esc(v.get('rule_id'))}</code></td>"
                f"<td>{esc(v.get('evidence'))}</td>"
                f"<td>{esc(v.get('explanation'))}</td>"
                "</tr>"
            )
        violations_html = (
            "<table><thead><tr><th>Type</th><th>Severity</th><th>Rule</th>"
            "<th>Evidence</th><th>Explanation</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    else:
        violations_html = '<p class="empty">No violations were flagged by the automated checks.</p>'

    if regulations:
        regs_html = "".join(
            f'<div class="reg"><strong>{esc(r.get("source"))}</strong>\n'
            f"{esc(r.get('text'))}</div>"
            for r in regulations
        )
    else:
        regs_html = '<p class="empty">No regulations were retrieved for this report.</p>'

    if decisions:
        drows = []
        for d in decisions:
            drows.append(
                "<tr>"
                f"<td><code>{esc(d.get('rule_id'))}</code></td>"
                f"<td>{esc(d.get('decision'))}</td>"
                f"<td>{esc(d.get('reviewer'))}</td>"
                f"<td>{esc(d.get('rationale'))}</td>"
                f"<td>{esc(d.get('timestamp'))}</td>"
                "</tr>"
            )
        decisions_html = (
            "<table><thead><tr><th>Rule</th><th>Decision</th><th>Reviewer</th>"
            "<th>Rationale</th><th>Timestamp (UTC)</th></tr></thead><tbody>"
            + "".join(drows)
            + "</tbody></table>"
        )
    else:
        decisions_html = '<p class="empty">No human review decisions recorded for this report.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Compliance Report — {status}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="banner">
  <div class="status">Automated compliance status: {status}</div>
  <div class="disclaimer">{esc(DISCLAIMER)}</div>
</div>

<h2>Findings (automated)</h2>
{violations_html}

<h2>Retrieved regulations</h2>
{regs_html}

<h2>Human review decisions</h2>
{decisions_html}

<footer>
Report SHA-256 (canonical JSON): {esc(report_sha256(report))}<br>
Reviewer decisions are stored separately from the automated result and do
not alter it. A review decision is a human triage outcome, not a legal
compliance approval or regulatory certification.
</footer>
</body>
</html>
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a standalone HTML compliance report (automated result + human reviews)."
    )
    parser.add_argument("--report", required=True, help="automated report JSON")
    parser.add_argument("--log", default=None, help="optional append-only review log (JSONL)")
    parser.add_argument("--out", required=True, help="output HTML file")
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"error: report file not found: {report_path}", file=sys.stderr)
        return 2
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"error: report file is not valid JSON: {e}", file=sys.stderr)
        return 2

    decisions: list[dict] = []
    if args.log:
        log_path = Path(args.log)
        if log_path.exists():
            target = report_sha256(report)
            decisions = [
                r for r in read_records(log_path) if r.get("report_sha256") == target
            ]

    out_path = Path(args.out)
    out_path.write_text(render(report, decisions), encoding="utf-8")
    print(f"Wrote {out_path} ({len(decisions)} review decision(s) joined)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
