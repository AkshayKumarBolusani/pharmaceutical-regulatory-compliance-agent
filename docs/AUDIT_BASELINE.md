# Audit Baseline — Pharmaceutical Regulatory Compliance Agent

**Date:** 2026-10-20 · **Branch:** `audit/remediation-2026-10-20` (created for this mission; nothing pushed) · **Base commit:** `83b2b08` "Initial commit" (2026-03-31, the repository's only commit) · **Working tree at baseline:** 2 modified files + 1 untracked test file, all from the 2026-10-20 audit fix round (see "Prior work" below). No user changes were discarded.

## Prior work incorporated into this baseline
A first audit was completed earlier on 2026-10-20 (report: research workspace `AUDIT.md`). It found and fixed four rule-engine defects (privacy false positive, negation blindness, off-label anchoring, substring matching) and annotated the privacy taxonomy. **Shipped state at clone (83b2b08): test suite 6 passed / 1 failed; seeded reports rule-level 4/6. Current state: 19 passed; seeded reports rule-level 6/6.** This baseline document describes the CURRENT tree; the mission's remaining sections audit what the first pass did not cover (retrieval, security, API/CLI robustness, adversarial depth, dependencies, docs, licensing).

## Repository structure
```
compliance_agent.py        CLI + orchestrator (run(): rules → status → optional RAG enrichment)
src/rule_engine.py         Deterministic checks driven by config/rules.yaml
src/hybrid_decision.py     Severity roll-up → PASS / FAIL / NEEDS_REVIEW
src/rag_explainer.py       ChromaDB retrieval + LLM explanation (explain-only contract)
src/schemas.py             ComplianceReport / Violation / RetrievedRegulation dataclasses
backend/main.py            FastAPI wrapper (GET /health, POST /check_compliance, serves UI)
frontend/index.html        Single-page demo UI (+ static/)
config/rules.yaml          Rule taxonomy (5 families)
config/chunk_schema.json   PolicyChunk schema (clause, source, jurisdiction, category, page span)
data/raw_policies/         sources_metadata.json provenance manifest (PDFs NOT committed, gitignored)
data/processed/clean_text/ 9 cleaned regulatory texts (~18,500 lines)
notebooks/01–05            Phase-1 pipeline: ingestion, chunking, indexing, retrieval test, demo
synthetic_reports/         6 seeded reports (500–1,000 statements each) + generator + README
tests/                     test_compliance_agent.py (7) + test_rule_engine_fixes.py (12)
PHASE1/2/3 proposal docs, LLM_SETUP.md, README.md, requirements.txt, .env.example, .gitignore
```
No `docs/` directory existed before this mission. No LICENSE file exists.

## Runtime & dependencies
- Python **3.12.3** (this machine); project declares 3.10+.
- Test environment used for baseline: venv with pyyaml 6.0.3, python-dotenv 1.2.4, pydantic 2.14.1, pytest 9.1.1. The full `requirements.txt` (chromadb, sentence-transformers, jupyter, fastapi…) was NOT installed for the baseline run; the rule-engine test path does not need it.
- Shipped-code third-party imports: `yaml`; `fastapi`/`pydantic` (backend only); `dotenv` (optional); `chromadb` + `openai` (lazy imports inside `rag_explainer.py` only). `sentence-transformers` is in requirements.txt but is not imported by shipped code (notebooks may use it — dependency audit pending).

## Baseline test results (evidence)
- Command: `python -m pytest -q` → **19 passed in 0.18s** (2026-10-20).
- Seeded synthetic reports via CLI (`COMPLIANCE_USE_LLM=0`, no vector index): statuses PASS / FAIL / FAIL / FAIL / NEEDS_REVIEW / FAIL with rule-level matches 6/6 against `synthetic_reports/README.md` expectations.
- CLI: works from the repo root with a file argument or stdin; prints the JSON report. API: not yet exercised at baseline (covered by the API/CLI workstream).

## Current rule coverage (verified against code + rules.yaml)
| Family | Implemented detection | Severity |
|---|---|---|
| privacy | phone, email, capitalised patient/person names, SSN-format national ID (4 of 8 declared entity types) | critical |
| adverse_event | 17 trigger keywords, word-boundary, negation-aware; suppressed when non-negated escalation context present | high |
| mandatory_reporting_context | 7 escalation flags, word-boundary, negation-aware | high |
| off_label_promotion | sentence-scoped phrase matching with approval-anchor exemption; explicit admissions flag anywhere | high |
| comparative_claims | 8 indicators, word-boundary | medium |
Decision roll-up: any critical/high → FAIL; else any medium → NEEDS_REVIEW; else PASS.

## Retrieval-index status
- `outputs/vector_index/` is **absent** (gitignored by design). The only build path is notebooks 01–03. From a fresh clone the system runs **rules-only** with empty `retrieved_regulations` and empty explanation fields. A scripted, reproducible build is a mission deliverable (workstream A).
- Corpus present as cleaned text: FDA ×3, EMA GVP ×2, CDSCO, ICH E2D, HIPAA Privacy Rule, India Drugs and Magic Remedies Act 1954. **GDPR is not in the corpus** (named in early docs only) — confirmed discrepancy.

## Known limitations & reproducibility gaps (confirmed at baseline)
1. No LICENSE → blocks clean open-source release decisions (author decision required).
2. RAG layer not reproducible without manual notebook execution; no scripted build, no retrieval tests.
3. No security audit yet: prompt-injection surface (LLM explainer), frontend rendering of untrusted text, CORS `*`, `/static/{path:path}` file serving, no request-size limits — all unverified at baseline.
4. API/CLI edge behaviour (empty input, malformed bodies, Unicode, very long documents) untested at baseline.
5. Privacy taxonomy declares 8 entity types; 4 implemented (documented in rules.yaml itself).
6. Real-world accuracy: **not established**. All behavioural evidence is synthetic (fixtures + 6 seeded reports). No labelled real documents exist in the project.
7. Single-commit history; no tags; no CI.
8. `requirements.txt` unpinned upper bounds; at least one listed dependency (`sentence-transformers`) may be unused by shipped code.

## Prioritised issue list (entering remediation)
| # | Severity | Issue | Evidence | Affected |
|---|---|---|---|---|
| B1 | High | No scripted index build; RAG silently degrades on fresh clones | `outputs/` absent; notebooks-only path | rag_explainer, notebooks, docs |
| B2 | High | No LICENSE; redistribution status of corpus texts unassessed | repo root listing | repo root, data/ |
| B3 | Medium | Security surface unaudited (injection, XSS, CORS, static path, error leakage) | backend/main.py, frontend/, rag prompt | backend, frontend, src |
| B4 | Medium | API/CLI edge cases untested | tests/ contents | compliance_agent.py, backend |
| B5 | Medium | Adversarial depth of rule engine untested beyond the fix-round cases | tests/ contents | src/rule_engine.py |
| B6 | Low | Dependency list likely over-broad and unpinned | requirements.txt vs import scan | requirements.txt |
| B7 | Low | Documentation scattered (phase proposals); no ARCHITECTURE/EVALUATION/SECURITY docs | repo listing | docs/ |

Severity scale: Critical = incorrect verdicts on ordinary input or safety/integrity failure; High = major function unverifiable/unreproducible or release-blocking; Medium = robustness/security gaps with workarounds; Low = hygiene.
