#!/usr/bin/env python3
"""
Human review log for compliance reports (Feature 4).

Reviewer decisions (confirmed / dismissed / escalated) are stored SEPARATELY
from the automated report, in an append-only JSONL log. The automated report
file is only ever READ by this tool, never written.

Each log record is hash-chained:

    record_hash = sha256( canonical_json(record content incl. prev_hash) )

and each record carries the previous record's hash as ``prev_hash`` (the
genesis record uses 64 zero hex chars). This makes edits to an individual
stored record detectable by ``verify``. It is tamper-EVIDENCE relative to the
log file itself, not legal immutability: see docs/SECURITY.md / the module
notes in the audit report for the honest limitations (no signatures, no
external anchoring, whole-file rewrite by someone with write access is not
detectable).

Records are keyed to a finding by (report_sha256, rule_id, evidence_excerpt),
where report_sha256 is the SHA-256 of the canonical JSON of the automated
report. When Feature 1 (evidence trace) adds a stable ``finding_id`` to
violations, the keying can migrate to that ID; the stored fields already
carry everything needed to re-key.

Usage:
    python scripts/review.py add --report report.json --rule-id privacy \
        [--evidence-contains "phone"] --decision confirmed \
        --rationale "..." --reviewer "Jane Doe" --log reviews.jsonl
    python scripts/review.py verify --log reviews.jsonl
    python scripts/review.py export --log reviews.jsonl --format json

Stdlib only. No network, no credentials.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DECISIONS = ("confirmed", "dismissed", "escalated")
GENESIS_HASH = "0" * 64

# Fields that make up the hashed content of a record (everything except
# record_hash itself). Order is irrelevant: canonical JSON sorts keys.
CONTENT_FIELDS = (
    "timestamp",
    "report_sha256",
    "rule_id",
    "evidence_excerpt",
    "decision",
    "rationale",
    "reviewer",
    "prev_hash",
)


def canonical_json(obj) -> str:
    """Deterministic JSON serialisation used for all hashing here."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def report_sha256(report: dict) -> str:
    """SHA-256 of the canonical JSON of an automated report dict.

    Stable across whitespace/key-order differences in the report file,
    because the parsed report is re-serialised canonically before hashing.
    """
    return sha256_hex(canonical_json(report))


def record_hash(content: dict) -> str:
    """Hash of a record's content (which includes its prev_hash)."""
    return sha256_hex(canonical_json({k: content[k] for k in CONTENT_FIELDS}))


def load_report(path: Path) -> dict:
    if not path.exists():
        raise ReviewError(f"report file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ReviewError(f"report file is not valid JSON: {path} ({e})")
    if not isinstance(data, dict) or "violations" not in data:
        raise ReviewError(f"report file does not look like a compliance report: {path}")
    return data


def read_records(log_path: Path) -> list[dict]:
    """Read all records from the JSONL log (empty list if no log yet)."""
    if not log_path.exists():
        return []
    records = []
    for lineno, line in enumerate(
        log_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ReviewError(f"log line {lineno} is not valid JSON: {e}")
    return records


class ReviewError(Exception):
    """User-facing error: printed to stderr, non-zero exit."""


def find_violation(report: dict, rule_id: str, evidence_contains: str | None) -> dict:
    """Locate the violation a review decision refers to.

    Raises ReviewError if the rule_id does not occur in this report, or if
    --evidence-contains matches none of that rule's violations.
    """
    matches = [v for v in report.get("violations", []) if v.get("rule_id") == rule_id]
    if not matches:
        known = sorted({v.get("rule_id") for v in report.get("violations", [])})
        raise ReviewError(
            f"unknown rule_id '{rule_id}' for this report "
            f"(report contains: {', '.join(known) if known else 'no violations'})"
        )
    if evidence_contains is not None:
        narrowed = [v for v in matches if evidence_contains in v.get("evidence", "")]
        if not narrowed:
            raise ReviewError(
                f"no violation with rule_id '{rule_id}' has evidence containing "
                f"'{evidence_contains}'"
            )
        matches = narrowed
    return matches[0]


def cmd_add(args) -> int:
    if args.decision not in DECISIONS:
        raise ReviewError(
            f"invalid decision '{args.decision}' (must be one of: {', '.join(DECISIONS)})"
        )
    if not args.rationale or not args.rationale.strip():
        raise ReviewError("rationale must not be empty")
    if not args.reviewer or not args.reviewer.strip():
        raise ReviewError("reviewer must not be empty")

    report_path = Path(args.report)
    report = load_report(report_path)
    violation = find_violation(report, args.rule_id, args.evidence_contains)

    log_path = Path(args.log)
    existing = read_records(log_path)
    prev_hash = existing[-1]["record_hash"] if existing else GENESIS_HASH

    content = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "report_sha256": report_sha256(report),
        "rule_id": args.rule_id,
        "evidence_excerpt": violation.get("evidence", ""),
        "decision": args.decision,
        "rationale": args.rationale.strip(),
        "reviewer": args.reviewer.strip(),
        "prev_hash": prev_hash,
    }
    record = dict(content)
    record["record_hash"] = record_hash(content)

    # Append-only: open in append mode, write exactly one line. The report
    # file is never opened for writing anywhere in this tool.
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(
        f"Recorded: record #{len(existing)} {args.decision} "
        f"rule_id={args.rule_id} hash={record['record_hash'][:12]}... "
        f"log={log_path}"
    )
    return 0


def verify_chain(records: list[dict]) -> tuple[bool, int | None, str]:
    """Recompute the hash chain. Returns (ok, first_broken_index, reason).

    Index is 0-based, matching the record numbers printed by `add`.
    """
    prev = GENESIS_HASH
    for i, rec in enumerate(records):
        missing = [k for k in CONTENT_FIELDS + ("record_hash",) if k not in rec]
        if missing:
            return False, i, f"missing field(s): {', '.join(missing)}"
        if rec["prev_hash"] != prev:
            return False, i, "prev_hash does not match the previous record's hash"
        if record_hash(rec) != rec["record_hash"]:
            return False, i, "record_hash does not match the record's content (content was altered)"
        prev = rec["record_hash"]
    return True, None, ""


def cmd_verify(args) -> int:
    log_path = Path(args.log)
    if not log_path.exists():
        raise ReviewError(f"log file not found: {log_path}")
    records = read_records(log_path)
    ok, idx, reason = verify_chain(records)
    if ok:
        print(f"OK: chain valid, {len(records)} record(s) verified in {log_path}")
        return 0
    print(
        f"BROKEN: record index {idx} (line {idx + 1}) in {log_path}: {reason}",
        file=sys.stderr,
    )
    return 1


def cmd_export(args) -> int:
    if args.format != "json":
        raise ReviewError(f"unsupported export format '{args.format}' (only 'json')")
    log_path = Path(args.log)
    if not log_path.exists():
        raise ReviewError(f"log file not found: {log_path}")
    records = read_records(log_path)
    ok, idx, reason = verify_chain(records)
    dump = {
        "format": "pharma-compliance-review-log/v1",
        "log": str(log_path),
        "record_count": len(records),
        "chain_valid": ok,
        "chain_break": None if ok else {"record_index": idx, "reason": reason},
        "records": records,
    }
    print(json.dumps(dump, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Append-only, hash-chained human review log for compliance reports."
    )
    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("add", help="record a reviewer decision for one finding")
    pa.add_argument("--report", required=True, help="automated report JSON (read-only)")
    pa.add_argument("--rule-id", required=True, help="rule_id of the finding being reviewed")
    pa.add_argument(
        "--evidence-contains",
        default=None,
        help="optional substring to disambiguate when a rule fired more than once",
    )
    pa.add_argument("--decision", required=True, help="confirmed | dismissed | escalated")
    pa.add_argument("--rationale", required=True, help="reviewer rationale (must not be empty)")
    pa.add_argument("--reviewer", required=True, help="reviewer name/identifier")
    pa.add_argument("--log", required=True, help="path to the append-only JSONL review log")
    pa.set_defaults(func=cmd_add)

    pv = sub.add_parser("verify", help="recompute the hash chain and report its status")
    pv.add_argument("--log", required=True)
    pv.set_defaults(func=cmd_verify)

    pe = sub.add_parser("export", help="machine-readable dump of the log incl. chain status")
    pe.add_argument("--log", required=True)
    pe.add_argument("--format", default="json")
    pe.set_defaults(func=cmd_export)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ReviewError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
