# AI-Powered Pharmaceutical Regulatory Compliance Agent

A research prototype that checks a pharmaceutical document against a
deterministic rule taxonomy, grounds each finding in retrieved regulatory
clauses where possible, and produces a structured, auditable JSON report
for human review.

> **Scope & disclaimers**
> - College research project; not a production legal system.
> - Regulations are for reference only; no claim of legal completeness or certification.
> - Findings are preliminary flags for qualified human review — never a
>   legal compliance determination. Never submit real patient data to it.

## What it does

Submit a document (a safety report, promotional draft, or similar) and the
agent reports:

- a status — `PASS`, `FAIL`, or `NEEDS_REVIEW` — rolled up deterministically
  from rule severities;
- one finding per triggered rule family (privacy, adverse-event reporting
  context, mandatory-reporting escalation, off-label promotion, comparative
  claims), each with the exact matched text, its location in the document,
  and a stable finding ID;
- where a vector index is available, the regulatory clauses retrieved for
  each finding, with their source title, version and official URL — or an
  explicit `insufficient_evidence` marker when no clause backs a finding.

An optional LLM (Groq or OpenAI) may *explain* findings in plain English.
It never decides anything: violations, severities and the status are
computed by the deterministic rule engine before any LLM call, and tests
prove model output cannot alter them.

## Architecture (short version)

```
report text → rule engine (config/rules.yaml) → severity roll-up → status
                                            ↘ optional: clause retrieval (ChromaDB)
                                              + LLM explanation → JSON report
```

Full detail — components, data flow, the evidence-trace schema, degradation
behaviour and design invariants — is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Installation

Python 3.10+ (verified on 3.12.3).

```bash
python -m venv .venv
source .venv/bin/activate        # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

The core test suite also runs in a minimal environment (pyyaml, pytest,
pydantic, python-dotenv); tests that need the web/retrieval/LLM packages
skip cleanly when those are absent.

## Usage

**Build the vector index** (from the cleaned corpus in
`data/processed/clean_text/`; produces `outputs/vector_index/` — 255 chunks
from the 6 texts shipped in the release candidate; 649 chunks when the 3
excluded texts below are restored locally):

```bash
python scripts/build_index.py
```

Without an index the agent still works — rules only, with retrieval fields
empty and `evidence_status: "insufficient_evidence"` on every finding.

**Check a document (CLI):**

```bash
python compliance_agent.py path/to/report.txt
echo "Patient John Smith, 555-123-4567..." | python compliance_agent.py
```

**Demo UI + API:**

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
# open http://localhost:8000/  — paste a report, click Check Compliance
```

`GET /health` returns `{ "status": "ok" }`; `POST /check_compliance` takes
`{ "report_text": "..." }` (max 1,000,000 characters) and returns the same
JSON as the CLI. Localhost demo only — no authentication or TLS.

**Optional LLM explanations:** copy `.env.example` to `.env` and set
`GROQ_API_KEY` (preferred) or `OPENAI_API_KEY`. `COMPLIANCE_USE_LLM=0`
disables explanations entirely. Never commit `.env` or real keys. See
[LLM_SETUP.md](LLM_SETUP.md).

**Evaluation lab** (synthetic benchmark — see
[docs/EVALUATION.md](docs/EVALUATION.md) before quoting any number):

```bash
python scripts/evaluate.py
```

**Human review** (decisions are stored separately from the automated
report, in an append-only hash-chained log):

```bash
python compliance_agent.py my_report.txt > report.json
python scripts/review.py add --report report.json --rule-id privacy \
    --decision confirmed --rationale "Real name and phone in a public draft" \
    --reviewer "a.reviewer" --log reviews.jsonl
python scripts/review.py verify --log reviews.jsonl
python scripts/report_html.py --report report.json --log reviews.jsonl --out report.html
```

**Assess the impact of a regulatory source changing:**

```bash
python scripts/source_diff.py --old old_version.txt --new new_version.txt --source-id FDA_AE_1
```

## Example

Input (`my_report.txt`, the repo's demo snippet):

```
Patient John Smith, 555-123-4567, had nausea.
```

Output (core fields shown; the full JSON adds the evidence trace):

```json
{
  "compliance_status": "FAIL",
  "violations": [
    { "type": "Patient Privacy Violation", "severity": "critical",
      "evidence": "PII/PHI detected: phone number, patient/person name",
      "rule_id": "privacy" },
    { "type": "Adverse Event Without Reporting Context", "severity": "high",
      "evidence": "AE trigger keywords found (nausea); no reporting context (e.g. serious, hospitalization) provided.",
      "rule_id": "adverse_event" }
  ],
  "retrieved_regulations": []
}
```

A named patient with a phone number is a critical privacy finding, and an
adverse event mentioned with none of the context regulators require is a
high-severity finding — any critical/high finding makes the status FAIL.

Six seeded synthetic reports with known expected outcomes live in
`synthetic_reports/` for a larger demo.

## Tests

```bash
python -m pytest
```

Verified 2026-10-20: **141 passed, 2 xfailed** in a full environment
(chromadb + fastapi + openai); **109 passed, 11 skipped, 2 xfailed** in a
minimal one. The 2 xfails are documented deterministic limits (quoted-text
keywords; first-name-only patient references) — see
[docs/EVALUATION.md](docs/EVALUATION.md), which also explains why the
synthetic benchmark's perfect scores measure regression consistency, not
accuracy, and why no real-world accuracy is claimed.

## Security

The demo treats submitted documents, retrieved text and the LLM as
untrusted. Confirmed issues found in audit (path traversal in static file
serving, CORS with credentials, error responses leaking internals) are
fixed and covered by regression tests. Keep the app on localhost, and
never submit real patient data. Full threat model and findings:
[docs/SECURITY.md](docs/SECURITY.md).

## Limitations

- **Evaluation is synthetic only.** All labelled data is fixtures, seeded
  reports and regression tests authored alongside the rules. Real-world
  accuracy on real documents is unmeasured.
- **The corpus is not current.** Three of the nine source texts are
  superseded revisions (EMA GVP Module VI Rev 1, GVP Annex I Rev 4,
  ICH E2D as adopted in 2003). Details: [docs/REGULATORY_SOURCES.md](docs/REGULATORY_SOURCES.md).
- **Three texts are excluded from distribution.** The cleaned EMA GVP
  Module VI, EMA GVP Annex I, and ICH E2D texts are **not shipped** in the
  release candidate: their issuers' redistribution terms have not been
  verified. Their manifest entries, official URLs, and attribution are
  preserved in `data/raw_policies/sources_metadata.json`; to use them,
  obtain the documents from the official URLs there and place the cleaned
  texts in `data/processed/clean_text/` before building the index. The
  shipped corpus is the remaining 6 texts (FDA ×3, CDSCO, HIPAA, India
  Drugs and Magic Remedies Act).
- **GDPR is not in the corpus**, despite being named in early project
  documents; the working corpus is the 9 texts listed in
  `docs/REGULATORY_SOURCES.md` (6 shipped, 3 excluded as above).
- **Privacy coverage is partial.** `config/rules.yaml` declares 8 PII/PHI
  entity types; 4 are implemented (patient name, phone, email, national
  ID). Address, health-plan beneficiary number, device and biometric
  identifiers are not detected.
- **Deterministic limits.** Keywords inside quoted text still flag (D8);
  a patient referenced by first name only is not detected (D10).
- **Localhost demo only.** No authentication, authorisation, TLS or
  multi-user isolation.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components, data flow, trace schema, invariants
- [docs/EVALUATION.md](docs/EVALUATION.md) — test/benchmark evidence, and what is not measured
- [docs/REGULATORY_SOURCES.md](docs/REGULATORY_SOURCES.md) — corpus provenance, versions, verified URLs
- [docs/SECURITY.md](docs/SECURITY.md) — threat model, audit findings and fixes
- [docs/AUDIT_BASELINE.md](docs/AUDIT_BASELINE.md) — the pre-remediation baseline audit
- [docs/AUDIT_REPORT.md](docs/AUDIT_REPORT.md) — confirmed issues, fixes and validation evidence from the 2026-10-20 audit & remediation mission
- [LLM_SETUP.md](LLM_SETUP.md) — optional LLM explanation setup
- `PHASE1_PROPOSAL.md`, `PHASE2_PROPOSAL.md`, `PHASE2_COMPLETION_REPORT.md`,
  `PHASE3_PROPOSAL.md` — the original phase-by-phase design documents

## Contributing

- Run `python -m pytest` before and after your change; the full suite
  must stay green (xfails D8/D10 excepted).
- Rule changes live in `config/rules.yaml` and **require tests** covering
  a positive, a negative, and a negation/anchoring case for the change.
- Never commit `.env`, API keys, or real patient data. Test and demo data
  must be synthetic.
- Keep the honesty rules: do not document or claim a capability you have
  not verified in code and tests.

## License

The project's **code** is licensed under the **MIT License** — see
[`LICENSE`](LICENSE) (Copyright (c) 2026 Akshay Kumar Bolusani).

The MIT license applies to the original code, tests, scripts, and project
documentation only. It does **not** extend to the third-party regulatory
documents in `data/processed/clean_text/` (publications of the FDA, HHS,
EMA, CDSCO, ICH, and the Government of India, each under its issuer's own
terms), to external dependencies (not vendored here), or to any future
research paper. See [`NOTICE.md`](NOTICE.md) for the full license-scope
and provenance statement.
