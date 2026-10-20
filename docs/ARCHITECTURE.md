# Architecture

How the Pharmaceutical Regulatory Compliance Agent is put together: what each
component is responsible for, how a document flows through the system, and
the invariants the design is built to hold.

The system checks a pharmaceutical document against a deterministic rule
taxonomy, optionally grounds each finding in retrieved regulatory clauses,
and emits a structured JSON report for human review. It is a research
prototype: findings are preliminary flags for a qualified reviewer, not
legal determinations.

## Data flow

```
                        config/rules.yaml
                        (5 rule families)
                              |
                              v
 report text ──► compliance_agent.run() ──► src/rule_engine.run_checks()
 (CLI / API)         (orchestrator)           deterministic checks,
                              |               match spans captured
                              v
                     src/hybrid_decision.compute_status()
                     PASS / FAIL / NEEDS_REVIEW  (from rules only)
                              |
              ┌───────────────┴────────────────┐
              │ index missing or unusable      │ index present and usable
              v                                v
   rules-only report               src/rag_explainer.enrich_violations_with_rag()
   (empty retrieval fields,        - retrieve top-3 clauses per violation
    evidence_status =              - manifest join: source title/version/URL
    "insufficient_evidence")       - optional LLM explanation (explain-only)
              └───────────────┬────────────────┘
                              v
                     src/schemas.ComplianceReport.to_dict()
                     JSON report (trace fields on every violation)
```

Supporting tools sit outside this path: `scripts/build_index.py` builds the
vector index the explainer queries; `scripts/evaluate.py` benchmarks the
engine; `scripts/review.py` / `scripts/report_html.py` record and render
human review; `scripts/source_diff.py` assesses the impact of a regulatory
source changing.

## Components

### `compliance_agent.py` — orchestrator and CLI

`run(report_text, top_k=3, use_llm=True, rules_path=None, index_path=None)`
is the single entry point every interface uses. It runs the rule engine,
computes the status, then attempts RAG enrichment if
`outputs/vector_index/` exists. Any failure during enrichment (ChromaDB not
installed, corrupt store, embedding model unavailable) is caught and the
run falls back to a rules-only report — it never crashes a check and never
fabricates retrieval content. As a CLI it reads a file path argument or
stdin and prints the JSON report.

### `src/rule_engine.py` — deterministic rule engine

The only component that decides what is a violation. It loads the taxonomy
from `config/rules.yaml` and runs five checks:

| Rule family (`rule_id`) | What it detects | Severity |
|---|---|---|
| `privacy` | Patient/person names, phone numbers, email addresses, national IDs (SSN format) via patterns | critical |
| `adverse_event` | Adverse-event trigger keywords with no reporting context present | high |
| `mandatory_reporting_context` | Escalation flags (seriousness criteria) that imply mandatory/expedited reporting | high |
| `off_label_promotion` | Promotional indication phrases with no approval anchor; explicit off-label admissions | high |
| `comparative_claims` | Comparative/superiority claim indicators | medium |

Matching properties (all verified by the test suites):

- **Word-boundary matching** — a keyword inside an unrelated word does not
  match ("rash" does not fire inside "crash"); a trailing plural suffix
  (s/es) on the final token is tolerated ("rashes", "side effects").
- **Clause-scoped negation** — negation cues ("no", "not", "never",
  "was not", "not required", …) suppress a match only within their own
  clause. Clause boundaries are commas, semicolons, and
  but/however/yet/although. "No nausea was reported, but the patient
  required hospitalization" therefore still counts the affirmed
  hospitalization.
- **Clause-scoped approval anchoring** (off-label check) — a clause that
  carries its own approval anchor ("approved for", "indicated for",
  "authorised for", …) is treated as compliant recitation and exempted;
  the anchor does not exempt other clauses in the same sentence. Explicit
  admissions ("not approved", "unapproved indication") flag anywhere.
- **Match-span capture** — each violation records up to 5 exact spans from
  the input (`matched_text`, surrounding `context`, `start`, `end`), which
  the schema layer turns into the evidence trace.

Two deterministic limits are known and documented rather than fixed:
keywords inside quoted text still flag (D8), and a patient referenced by a
single first name only ("Patient John") is not detected — a deliberate
recall trade-off (D10). See `docs/EVALUATION.md`.

### `src/hybrid_decision.py` — status roll-up

Maps the rule violations to one status, deterministically:

- any critical or high severity → `FAIL`
- else any medium → `NEEDS_REVIEW`
- else → `PASS`

The status is computed from the raw rule violations **before** enrichment.
Retrieval and LLM output can never change it.

### `src/rag_explainer.py` — retrieval-grounded explanation (optional)

For each violation it queries ChromaDB (collection `policy_chunks`,
ONNX all-MiniLM-L6-v2 embeddings — the same embedder used at index time)
for the top-3 clauses, using the violation's evidence text as the query.
Retrieved clauses are joined against the source manifest
(`data/raw_policies/sources_metadata.json`) to attach the document title,
version/date and official URL when the manifest has them; anything missing
stays empty — metadata is never invented.

If an LLM is configured (Groq via `GROQ_API_KEY`, else OpenAI via
`OPENAI_API_KEY`) it is called under an explain-only prompt contract: it
may only explain the already-detected violation and suggest a fix, citing
the retrieved text; it must not decide compliance and must not invent
regulations. Its output is written only into the `explanation` /
`suggested_fix` fields. If no LLM actually responded (package missing, no
key, provider error), `explanation_origin` stays `"none"` and the field
holds an explicit "explanation unavailable" fallback string instead.

### `src/schemas.py` — report types and the evidence trace

Dataclasses `ComplianceReport`, `Violation`, `RetrievedRegulation`, plus
the trace helpers `compute_finding_id` / `apply_trace`. `to_dict()` defines
the JSON contract. Every violation carries:

| Field | Meaning |
|---|---|
| `type`, `severity`, `evidence`, `rule_id` | The finding itself, from the rule engine |
| `finding_id` | Deterministic ID (`F-` + SHA-256 prefix over rule ID + first match text + offset); the same finding in the same document gets the same ID across runs, so it can be tracked in a review history |
| `matched_text`, `context` | The first matched span and its surrounding sentence |
| `matches` | Up to 5 spans: `{matched_text, context, start, end}` |
| `evidence_status` | `"supported"` only if at least one retrieved clause is attached to this violation; otherwise `"insufficient_evidence"`. Retrieval alone never proves a violation — the field records whether backing text exists, and makes its absence explicit |
| `origin` | Always `"deterministic_rule"` for findings |
| `explanation_origin` | `"llm"` only when a real model response was parsed, else `"none"` |
| `regulatory_basis` | Source label of the top retrieved clause ("" when none) |
| `source_title`, `source_version`, `source_url` | Manifest metadata for that top clause ("" when unknown) |
| `explanation`, `suggested_fix` | LLM text, or fallback/empty (see above) |
| `retrieved_regulations` | This violation's clauses, each `{source, text, source_id, title, version_date, official_url, country, category}` |

The report also carries a top-level `retrieved_regulations` list (the
deduplicated union across violations).

### `backend/main.py` + `frontend/` — demo API and UI

A stateless FastAPI wrapper around `compliance_agent.run()` — no business
logic is duplicated. `POST /check_compliance` accepts
`{ "report_text": "..." }` (capped at 1,000,000 characters; oversized
bodies are rejected with HTTP 422 before processing) and returns the report
JSON unchanged. `GET /health` returns `{ "status": "ok" }`. The single-page
frontend is served at `/` with static assets under `/static/`
(path-contained; see `docs/SECURITY.md`). CORS is restricted to the app's
own localhost origins without credentials. This layer is a local demo —
no authentication, no TLS, no database.

### Scripts

| Script | Role |
|---|---|
| `scripts/build_index.py` | Chunks the cleaned corpus (`data/processed/clean_text/`) clause-aware and builds the ChromaDB `policy_chunks` index at `outputs/vector_index/` (255 chunks from the 6 texts shipped in the release candidate; 649 chunks from the full 9-document corpus when the 3 distribution-excluded texts are restored locally — see `NOTICE.md`). Flags: `--input-dir`, `--output-dir`, `--manifest`, `--collection` |
| `scripts/evaluate.py` | Feature-2 evaluation lab: runs the rules-only engine over `evaluation/labeled_cases.json` and reports per-rule TP/FP/FN/TN, precision/recall/F1, status accuracy, FP/FN examples (see `docs/EVALUATION.md`) |
| `scripts/review.py` | Human review log: `add` / `verify` / `export` subcommands over an append-only, hash-chained JSONL log. Reviewer decisions live outside the automated report, keyed to findings |
| `scripts/report_html.py` | Renders a report JSON (plus an optional review log) as a standalone HTML report |
| `scripts/source_diff.py` | Compares two versions of a regulatory source text and emits a Markdown change-impact checklist: changed passages, rule families whose keywords they touch, and the tests that cover those families. It never changes rules itself |

### Data and configuration

- `config/rules.yaml` — the rule taxonomy; the engine reads it at runtime,
  so rule changes are configuration changes (and require tests — see the
  README's contribution notes). The privacy family declares 8 entity
  types; 4 are implemented (patient name, phone, email, national ID) —
  the file states this in its own header comment.
- `config/chunk_schema.json` — the chunk metadata schema.
- `data/raw_policies/sources_metadata.json` — the source manifest
  (see `docs/REGULATORY_SOURCES.md`).
- `data/processed/clean_text/` — the 9 cleaned regulatory texts that make
  up the working corpus.
- `notebooks/` — the original Phase-1 pipeline (ingestion, chunking,
  indexing, retrieval test, demo). The scripted index path is
  `scripts/build_index.py`.
- `.env` (never committed) — optional `GROQ_API_KEY` / `OPENAI_API_KEY`
  and `COMPLIANCE_USE_LLM`.

## Degradation behaviour

The engine's core path has no hard dependency on retrieval or on an LLM:

| Condition | Behaviour |
|---|---|
| No vector index | Rules-only report; `retrieved_regulations` empty; every violation has `evidence_status: "insufficient_evidence"`, empty source fields |
| Index present but unusable (library missing, corrupt store, embedder unavailable) | Enrichment exception is caught; same rules-only fallback as above |
| Index usable, no LLM available | Clauses are retrieved and attached (`evidence_status: "supported"`); `explanation` holds an explicit unavailability message; `explanation_origin: "none"` |
| Manifest missing/unreadable | Clauses still retrieved; manifest-derived fields stay empty |
| Empty input | `PASS` with zero violations — this means "nothing to check", not "compliant" |

## Design invariants

1. **Rules decide.** Violations, severities and the PASS / FAIL /
   NEEDS_REVIEW status come only from the deterministic engine and the
   severity roll-up.
2. **The LLM never alters a finding.** It cannot create, remove, re-grade
   or re-label violations; its text is confined to `explanation` /
   `suggested_fix`. This is enforced structurally (the verdict is computed
   before any LLM call) and proven by tests, including a hostile fake-LLM
   test (see `docs/SECURITY.md`).
3. **No fabricated grounding.** A finding is marked `"supported"` only
   when a retrieved clause is actually attached; otherwise the absence is
   stated as `"insufficient_evidence"`. Manifest metadata is copied, never
   invented.
4. **Deterministic with the LLM off.** Same input + same rules → same
   report, including `finding_id`s (asserted byte-identical by tests).
5. **Retrieved and submitted text is data, never instructions.** The
   corpus and the submitted document are untrusted input (see
   `docs/SECURITY.md`).
6. **Human review is separate.** Reviewer decisions are appended to their
   own hash-chained log; the automated report is never mutated.
