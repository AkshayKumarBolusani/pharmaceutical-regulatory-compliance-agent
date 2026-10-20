# AI-Powered Pharmaceutical Regulatory Compliance Agent

**A Python research prototype for pharmaceutical regulatory document review, deterministic compliance rules, regulatory-clause retrieval (RAG), evidence traceability, and human-in-the-loop review.**

The Pharmaceutical Regulatory Compliance Agent analyzes pharmaceutical safety reports, pharmacovigilance text, and promotional drafts against a configurable rule taxonomy. It produces a structured JSON report with a `PASS`, `FAIL`, or `NEEDS_REVIEW` status, traceable findings, and regulatory-source evidence when retrieval is available.

> **Research prototype — not legal advice or a compliance certification tool.** Findings are preliminary signals for qualified human review. The system has not been validated on real-world documents. Do not submit real patient data.

## Key features

- **Deterministic compliance rules:** Rule matches, severity levels, and final status are computed by the rule engine, not by an LLM.
- **Evidence-traceable findings:** Findings include matched text, location, stable identifiers, rule details, and regulatory evidence where available.
- **Regulatory RAG:** Optional ChromaDB retrieval connects findings to indexed source passages and metadata. When supporting evidence is unavailable, the report marks it as insufficient rather than inventing a citation.
- **Optional LLM explanations:** Groq or OpenAI can explain existing findings in plain language; the model does not decide the compliance status.
- **Human review history:** Reviewer decisions are recorded separately from automated results in an append-only, hash-chained log.
- **Evaluation tools:** A reproducible synthetic evaluation script reports metrics while explicitly distinguishing regression consistency from real-world accuracy.
- **Change-impact helper:** Compare two local versions of a regulatory source and identify potentially affected rule families for human review.
- **CLI and local web demo:** Run checks from the command line or through a FastAPI endpoint and browser interface.
- **Security and adversarial tests:** Regression coverage addresses input handling, static-file path traversal, error leakage, and difficult rule-engine cases.

## Project status and validation

This is an independently developed research and engineering prototype. The latest reported audit run on 20 October 2026 recorded:

- **Full environment:** 141 passed, 2 expected failures (`xfail`).
- **Minimal environment:** 109 passed, 11 skipped, 2 expected failures.
- **Evaluation data:** Synthetic fixtures and seeded reports only.
- **Real-world accuracy:** Not measured.
- **Regulatory completeness:** Not established.
- **Production readiness:** Not production-ready; intended for localhost demonstration and research.

The two expected failures document known deterministic limits involving keywords inside quoted text and first-name-only patient references. See [Evaluation](docs/EVALUATION.md) for details. Re-run tests in your environment before relying on these historical results.

## How it works

```text
Input document
     |
     v
Deterministic rule engine (config/rules.yaml)
     |
     v
Severity roll-up --> PASS / FAIL / NEEDS_REVIEW
     |
     +--> Optional regulatory-clause retrieval (ChromaDB)
     |
     +--> Optional LLM explanation (never controls the verdict)
     |
     v
Structured JSON report + evidence trace
     |
     v
Optional human review and audit history
```

The design invariant is that optional retrieval and LLM explanation must not change the deterministic verdict. See [Architecture](docs/ARCHITECTURE.md).

## Technology stack

- **Language:** Python 3.10+
- **API:** FastAPI, Uvicorn
- **Rule configuration:** YAML
- **Retrieval:** ChromaDB and sentence embeddings
- **Optional explanations:** Groq or OpenAI API
- **Validation and testing:** Pydantic, pytest
- **Interface:** HTML/CSS/JavaScript local demo

## Quick start

### 1. Install

```bash
git clone https://github.com/AkshayKumarBolusani/pharmaceutical-regulatory-compliance-agent.git
cd pharmaceutical-regulatory-compliance-agent

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Python 3.10 or newer is required. Some retrieval and API tests depend on optional packages; consult the test output and `requirements.txt` for the environment you installed.

### 2. Build the regulatory retrieval index

```bash
python scripts/build_index.py
```

The index builder processes the local text files under `data/processed/clean_text/` and writes a generated index under `outputs/vector_index/`. The reported audit build contained 649 chunks when all nine source texts were present. Do not commit generated indexes unless the project documentation explicitly calls for them.

**Source-material notice:** the current audit branch contains cleaned EMA and ICH regulatory texts whose redistribution terms have not yet been verified. The MIT license applies to original project code, not automatically to third-party regulatory publications. Review [NOTICE.md](NOTICE.md) and [Regulatory Sources](docs/REGULATORY_SOURCES.md) before redistributing the repository. If preparing a public source package, confirm the terms for each text or omit any material whose redistribution is not permitted.

The agent can still run in rules-only mode without an index. In that mode, retrieval evidence is unavailable and findings should be interpreted accordingly.

### 3. Check a text file with the CLI

```bash
python compliance_agent.py synthetic_reports/01_clean.txt
```

You can also provide a file path:

```bash
python compliance_agent.py path/to/report.txt
```

The CLI emits a structured report. Use only synthetic or appropriately authorized, de-identified material.

### 4. Start the local web demo

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` in your browser. The API exposes `GET /health` and `POST /check_compliance`. The demo is for localhost use; it does not provide production authentication, authorization, TLS, or multi-user isolation.

### 5. Run tests and the synthetic evaluation

```bash
python -m pytest -q
python scripts/evaluate.py
```

Read [Evaluation](docs/EVALUATION.md) before quoting any score. The synthetic benchmark checks implementation behavior against constructed cases; perfect synthetic results do **not** establish real-world extraction quality, regulatory accuracy, or legal compliance.

## Optional LLM explanations

Copy `.env.example` to `.env` and set `GROQ_API_KEY` or `OPENAI_API_KEY` if you want optional plain-language explanations. Set `COMPLIANCE_USE_LLM=0` to disable LLM explanations.

```bash
cp .env.example .env
```

Never commit `.env`, API keys, confidential documents, or real patient data. See [LLM setup](LLM_SETUP.md).

## Human review and report export

Example workflow:

```bash
python compliance_agent.py synthetic_reports/02_privacy_violation.txt > report.json

python scripts/review.py add \
  --report report.json \
  --rule-id privacy \
  --decision confirmed \
  --rationale "Example reviewer rationale for a synthetic case" \
  --reviewer "reviewer-1" \
  --log reviews.jsonl

python scripts/review.py verify --log reviews.jsonl

python scripts/report_html.py \
  --report report.json \
  --log reviews.jsonl \
  --out report.html
```

Review actions supplement the automated report; they do not convert the prototype into a legal approval system. The local hash-chained log is tamper-evident, not absolutely immutable against an attacker who can rewrite the entire log.

## Regulatory source change analysis

Compare two local versions of a source document:

```bash
python scripts/source_diff.py \
  --old old_version.txt \
  --new new_version.txt \
  --source-id FDA_AE_1
```

The tool identifies text changes and potentially affected rule families. It does not interpret regulatory changes or update rules automatically; qualified human review is required.

## Rule coverage

The current rule taxonomy includes checks for:

- Privacy and selected personal identifiers
- Adverse-event mentions without reporting context
- Mandatory-reporting escalation context
- Off-label promotional language
- Comparative claims

Coverage is partial. The current implementation detects only a subset of the privacy entity types declared in configuration. See [Audit Report](docs/AUDIT_REPORT.md) and [Regulatory Sources](docs/REGULATORY_SOURCES.md) for the detailed scope and known gaps.

## Repository guide

| Path | Purpose |
|---|---|
| `src/rule_engine.py` | Deterministic rule matching |
| `src/hybrid_decision.py` | Severity roll-up and status decision |
| `src/rag_explainer.py` | Regulatory retrieval and optional explanation |
| `config/rules.yaml` | Configurable rule taxonomy |
| `data/raw_policies/sources_metadata.json` | Regulatory-source metadata and provenance |
| `scripts/build_index.py` | Rebuild the retrieval index |
| `scripts/evaluate.py` | Synthetic evaluation report |
| `scripts/review.py` | Reviewer decisions and audit-log verification |
| `scripts/report_html.py` | HTML report export |
| `scripts/source_diff.py` | Source-version text comparison |
| `tests/` | Unit, integration, security, and adversarial tests |
| `synthetic_reports/` | Synthetic demo reports |
| `docs/` | Architecture, security, source provenance, evaluation, and audit notes |

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Security threat model and audit](docs/SECURITY.md)
- [Evaluation methodology and limitations](docs/EVALUATION.md)
- [Regulatory sources and provenance](docs/REGULATORY_SOURCES.md)
- [Audit baseline](docs/AUDIT_BASELINE.md)
- [Audit and remediation report](docs/AUDIT_REPORT.md)
- [Optional LLM setup](LLM_SETUP.md)
- [Notice and source-material limitations](NOTICE.md)

## Known limitations

- **No real-world validation:** the labeled evaluation set is synthetic; performance on real pharmaceutical documents is unknown.
- **No legal certification:** the rules are not a complete representation of any regulator's requirements.
- **Source currency and redistribution:** some included EMA/ICH texts are older versions, and their redistribution terms have not been verified. Check the source manifest and notice before public redistribution.
- **Partial privacy detection:** not every entity type declared in configuration is implemented.
- **Known deterministic edge cases:** quoted text can still trigger findings, and first-name-only patient references may be missed.
- **Retrieval quality unmeasured:** there is no human-judged relevance benchmark yet.
- **Localhost-grade deployment:** authentication, rate limiting, TLS, and multi-user isolation are not provided.
- **Human review required:** a PASS result is not proof of legal or regulatory compliance.

## Contributing

Contributions and issue reports are welcome. Before submitting a change:

1. Run `python -m pytest -q`.
2. Add positive, negative, and negation/anchoring tests for rule changes.
3. Keep test data synthetic or appropriately authorized.
4. Do not add credentials, private patient data, or unverified third-party content.
5. Document limitations and avoid claims not supported by code and evaluation.

## License

Original project code is licensed under the [MIT License](LICENSE), copyright © 2026 Akshay Kumar Bolusani. The MIT license does not automatically apply to third-party regulatory publications, source texts, dependencies, or future research papers. See [NOTICE.md](NOTICE.md).

## Keywords

Pharmaceutical regulatory compliance, pharmacovigilance, adverse event reporting, regulatory document analysis, deterministic rule engine, explainable AI, retrieval-augmented generation, RAG, ChromaDB, evidence traceability, human-in-the-loop review, pharmaceutical safety, Python, FastAPI.
