# Audit Report — Pharmaceutical Regulatory Compliance Agent

**Mission:** End-to-End Technical Audit, Remediation & Publication-Readiness · **Dates:** 2026-10-20 · **Branch:** `audit/remediation-2026-10-20` (local only; nothing pushed) · **Base commit:** `83b2b08` · **Baseline:** `docs/AUDIT_BASELINE.md`

This report lists confirmed issues with evidence, the fixes applied, unresolved items, and the validation runs behind every claim. Severity: Critical / High / Medium / Low. "Confirmed" means reproduced by an executed test, probe, or live request — not inferred.

## 1. Confirmed issues and fixes

### 1A. Rule engine (first audit, 2026-10-20 morning — fixed same day)
| ID | Sev | Issue | Fix |
|---|---|---|---|
| A1 | Critical | Privacy name regex with IGNORECASE matched "patient" + any word ("the patient experienced…" → critical FP) | Capitalised-name patterns only |
| A2 | High | Negation blindness: "No hospitalization was required" counted as hospitalization present, misrouting AE cases | Sentence-scoped negation handling |
| A3 | High | Off-label phrases flagged compliant label recitations ("approved for", "indicated for") | Approval-anchor logic (later clause-scoped, D7) |
| A4 | Medium | Substring keyword matching ("rash" inside "crash") | Word-boundary matching |

### 1B. Adversarial battery (workstream D → fixed in E1)
42 hard cases; 13 documented findings. 10 fixed, 2 documented limits, 1 (D-analyst note on "Dr." titles) resolved as by-design.
| ID | Sev | Issue | Outcome |
|---|---|---|---|
| D1 | High | Negation scoped to whole sentence prefix — an early "No" suppressed a later affirmed escalation flag | **Fixed:** clause-scoped negation |
| D7 | High | One approval anchor exempted an entire sentence, hiding unanchored promotional clauses | **Fixed:** clause-scoped anchoring |
| D2 | Medium | Comparative check ignored negation ("not better than placebo" flagged) | **Fixed:** negation-aware matching |
| D3 | Medium | Plural forms missed ("rashes", "side effects") | **Fixed:** plural-tolerant final token |
| D4 | Medium | Space-separated national ID missed | **Fixed:** dashes or spaces |
| D5 | Medium | Non-US phone formats missed (+91 …) in a multi-jurisdiction tool | **Fixed:** international branch (≥9 digits, leading +) |
| D6 | Medium | ALL-CAPS patient names missed | **Fixed:** caps branch (2–3 tokens; ambiguity noted in code) |
| D9 | Medium | Follower-negation clipped at 40 chars | **Fixed:** scan to sentence end |
| D11 | Low | Spaced-obfuscation email missed ("name @ example.com") | **Fixed:** spaced-@ alternative |
| D12 | Low | Literal underscore form ("life_threatening") missed | **Fixed:** joiner class includes `_` |
| D8 | Low | Keywords inside quoted titles flag (no quotation awareness) | **Documented limit** — deterministic rules cannot reliably interpret quotation scope; test stays xfail |
| D10 | Low | First-name-only patient reference not detected | **Documented trade-off** — deliberate; relaxing it resurrects the A1 false-positive class; test stays xfail |

### 1C. Security (workstream B — all fixed in B's round)
| ID | Sev | Issue | Fix |
|---|---|---|---|
| S1 | **High** | Path traversal in `/static/{path:path}`: arbitrary file read (source, config, `/etc/passwd` proven live; a real `.env` would have been served) | Resolve + containment check; uniform 404. Post-fix: 17/17 payloads 404 |
| S2 | Medium | CORS reflected any origin **with credentials** — any website could call the local API and spend the user's LLM quota | Origin allowlist (localhost), credentials off |
| S3 | Medium | HTTP 500 returned raw exception text incl. absolute paths | Generic client message; detail to server log only |
| S4 | Low | No request-size limit on `report_text` | 1,000,000-char cap (422), documented as demo-grade |
| S5 | Low | Latent unescaped `innerHTML` sink for the status value in the UI (server enum, so latent) | `escapeHtml()` applied |
| S6 | — | Prompt injection via submitted documents — **tested, no defect**: injection text cannot change the verdict; hostile fake-LLM test proves model output is confined to explanation fields | Regression tests retained |

### 1D. Retrieval & corpus (workstream A)
| ID | Sev | Issue | Outcome |
|---|---|---|---|
| R1 | High | RAG layer irreproducible from a clone (notebooks-only build; silent degradation) | **Fixed:** `scripts/build_index.py` (649 chunks, idempotent); degradation now explicit via `evidence_status` |
| R2 | Medium | Embedder inconsistency: notebooks embed with sentence-transformers, runtime queries with ChromaDB ONNX (same model, different implementations) | **Resolved in the scripted build** (runtime embedder used); noted in script docstring |
| R3 | Medium | Corpus currency: 3 of 9 texts are superseded revisions (EMA GVP Module VI Rev 1 — current Rev 2; GVP Annex I Rev 4 — current Rev 5, 2024; ICH E2D 2003 — E2D(R1) adopted 2025) | **Unresolved — owner decision.** Flagged in `docs/REGULATORY_SOURCES.md`; refreshing source texts is a content decision, not done silently |
| R4 | Medium | GDPR absent from corpus while early docs (and the manifest's own scope note) implied its use | **Corrected:** manifest gained a `missing` GDPR entry and the scope note was rewritten (2026-10-20) |
| R5 | Low | Manifest accuracy: FDA_AE_1's underlying document may be a 2001 draft guidance; title states neither | Recorded as a note in the manifest; unverified items left `unverified` with empty URLs (3 of 9), never claimed |

### 1E. Robustness & integration (workstreams C + coordinator)
| ID | Sev | Issue | Fix |
|---|---|---|---|
| C1 | Medium | CLI crashed with a traceback when passed a directory or a non-UTF-8 file | Clean JSON error + exit 1 (`compliance_agent.py`) |
| C2 | Medium | **Graceful-degradation breach:** once an index existed, `run()` crashed in environments where chromadb was unusable instead of degrading | try/except fallback to rules-only output |
| C3 | Low | `Violation.retrieved_regulations` was silently dropped by `to_dict()` — per-violation clause linkage invisible | Serialized (Feature 1) |
| C4 | Low | Test-suite portability: security tests errored at collection without fastapi; one LLM-isolation test silently depended on the `openai` package | `importorskip` guards; sys.modules stub in the test |
| C5 | Low | `pdfplumber` in requirements but never imported anywhere | Removed (verified by repo-wide grep); noted in requirements header |

## 2. Features delivered (per the feature addendum)
- **F1 Evidence-First Compliance Trace** — every violation carries `finding_id` (deterministic hash), exact `matched_text` + sentence `context` + spans, `evidence_status` (`supported` only when clauses were actually retrieved; otherwise explicit `insufficient_evidence`), `origin` (`deterministic_rule`), `explanation_origin` (`llm`/`none`), and manifest-joined `source_title`/`source_version`/`source_url` (left empty where the manifest itself is empty — never invented), plus per-violation `retrieved_regulations`.
- **F2 Evaluation & Error Analysis Lab** — `evaluation/labeled_cases.json` (24 synthetic cases, every label traced to a fixture, seeded report, or passing test) + `scripts/evaluate.py`: per-rule TP/FP/FN/TN and P/R/F1 with denominators, status accuracy, NEEDS_REVIEW count, FP/FN listings. Scores on the shipped set are 1.000 **by construction** (specification cases — regression consistency, not accuracy); the report header states this verbatim, and the lab's own mini-dataset test proves it reports imperfection when labels stipulate it (P=R=0.5 case).
- **F3 Regulatory Source & Version Manifest** — `sources_metadata.json` v2.0: official URLs with honest verification states (2 verified exact, 4 landing-page-only, 3 unverified), structured version dates, applicable-rules mapping, reuse notes, GDPR recorded as missing. Human-readable form: `docs/REGULATORY_SOURCES.md`.
- **F4 Human Review & Audit History** — `scripts/review.py` + `scripts/report_html.py`: reviewers confirm/dismiss/escalate findings with rationale in an append-only, hash-chained JSONL log stored separately from automated results (tamper-evident, **not** legally immutable — the limits are documented in the tool output and SECURITY.md); JSON export; escaped standalone HTML report carrying the "preliminary flags for qualified human review" banner.
- **F5 Regulatory Change Impact Analysis** — `scripts/source_diff.py`: passage-level diff of two local source versions → changed passages, rule-keyword overlap, potentially affected families and their test files, as a human checklist. It never modifies rules.

## 3. Validation evidence (executed 2026-10-20)
- Full test suite, full environment: **141 passed, 2 xfailed** (D8, D10). Minimal environment: **109 passed, 11 skipped, 2 xfailed** (skips = optional-dependency tests skipping by design).
- Seeded reports parity after all changes: statuses and rule IDs identical to the pre-mission verified behaviour (6/6 document-level, 6/6 rule-level).
- Security: post-fix live probes — 17/17 traversal payloads → 404; foreign CORS preflight → 400 without reflection; oversized body → 422.
- Index build: 649 chunks; re-run idempotent; end-to-end CLI run against the built index returns populated retrieval + trace fields.
- `pip check` (full venv): no broken requirements. Verified-working versions recorded in `requirements.txt` header.
- Evaluation lab on the shipped set: status accuracy 24/24; per-rule counts in `docs/EVALUATION.md`.

## 4. Unresolved items & blockers
1. **Corpus refresh (owner decision):** replace the three superseded texts (R3); optionally add GDPR. The F5 tool can then diff old vs new and list affected rules/tests for review.
2. **LICENSE — RESOLVED 2026-10-20 (owner decision):** MIT license added at repo root (`LICENSE`, Copyright (c) 2026 Akshay Kumar Bolusani), covering the project's code only. License scope and the one unresolved provenance concern (redistribution terms of the cleaned EMA/ICH regulatory texts) are documented in `NOTICE.md`.
3. **Real-world validation does not exist:** no authorized, independently labelled real documents. All behavioural evidence is synthetic (evidence classes A/B; class C absent — see `docs/EVALUATION.md`). No accuracy claim is made anywhere.
4. **Retrieval quality is unmeasured:** no labelled relevant-clause judgments; one anecdotal off-target top hit (ICH chunk for a privacy-flavoured query) is recorded in REGULATORY_SOURCES.md as an observation, not a finding.
5. **Explanation-wording manipulation:** crafted document/retrieved text can bias LLM *explanation wording* (never the verdict — proven by test). Reviewers should treat explanations as drafts.
6. **Demo-grade application limits:** no authentication, rate limiting, or LLM-call timeouts — the app must remain on localhost. Provider error strings can appear inside explanation fields.
7. **Review-log limits:** hash chain is tamper-evident only against partial edits; a full-file rewrite with recomputed hashes verifies clean; reviewer identity is self-declared (no signatures); single-writer assumption.
8. **FDA_AE_1 / INDIA_DMRA_1954 / ICH_E2D official URLs** remain unverified (fetch blocks); manifest says so.

## 5. Publication-readiness (summary; full assessment in the final deliverables)
- Public GitHub: **ready** (LICENSE in place since 2026-10-20) pending the owner's push and the NOTICE.md redistribution consideration for the cleaned corpus texts.
- Zenodo software release: ready (needs a tagged release by the owner).
- Free preprint (TechRxiv): the honest paper exists — a measurement/failure-analysis of a deterministic compliance checker — once the owner approves the outline.
- Peer-reviewed software paper (JOSS): **not yet eligible** — JOSS requires a license and sustained public development history; revisit after the repo has been public for some months.

## Addendum — release-candidate pass (2026-10-20, after the MIT decision)
- LICENSE added (MIT, code only) + `NOTICE.md` license-scope/provenance statement; README and docs updated to match.
- The cleaned **EMA GVP Module VI, EMA GVP Annex I, and ICH E2D texts were excluded from the release candidate** (redistribution terms unverified). Manifest entries, official URLs, attribution, and restoration instructions preserved (`corpus_status: excluded_from_distribution_pending_redistribution_verification`). Shipped corpus: 6 texts; scripted index build verified at **255 chunks** (full corpus: 649). No test depended on the excluded texts (retrieval tests use synthetic corpora); the full suite was re-run green after the change (counts in the mission's final report). **Scope limit, stated plainly:** the exclusion governs this release candidate only — the texts remain present in the repository's earlier public history (commit `83b2b08` and the original GitHub repo); removing them there would require a separate history-rewrite decision by the owner.
- Local commit `eeed10c` (the full remediation) exists on this branch in the working clone; the push is the owner's action (this environment has no GitHub write credentials).
