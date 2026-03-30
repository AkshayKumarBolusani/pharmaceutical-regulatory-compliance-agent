# Phase 2 — Compliance Reasoning Engine: Proposal

**Status:** Awaiting confirmation before implementation.

**Phase 1 is frozen.** No changes to Phase 1 artifacts (notebooks, `data/raw_policies/`, `config/rules.yaml`, `config/chunk_schema.json`, `outputs/vector_index/`, clause chunking).

---

## 1. Phase 2 Folder Structure (Additions Only)

All new under project root. No new top-level config; we **read** `config/rules.yaml` and **read** existing vector index.

```
Pharmaceutical Regulatory Compliance Agent/
├── ... (all Phase 1 content unchanged)
│
├── src/                          # NEW — Phase 2 Python package
│   ├── __init__.py
│   ├── rule_engine.py             # A. Rule-based compliance (deterministic)
│   ├── rag_explainer.py           # B. RAG retrieval + LLM explanation only
│   ├── hybrid_decision.py        # C. Combine rule + LLM → final status
│   └── schemas.py                 # D. Structured output (Pydantic/dataclasses)
│
├── compliance_agent.py           # NEW — E. Orchestrator script (CLI entrypoint)
│
├── tests/                        # NEW — Synthetic test suite
│   ├── __init__.py
│   ├── fixtures/
│   │   └── synthetic_reports.py   # Clean, privacy, off-label, AE, comparative
│   └── test_compliance_agent.py  # Run agent on fixtures; assert violations + decision
│
├── notebooks/                     # UNCHANGED (Phase 1)
│   └── 05_compliance_demo.ipynb   # NEW — Demo: run agent on test cases, show output
│
└── outputs/                       # UNCHANGED layout
    └── vector_index/              # READ-ONLY (Phase 1 ChromaDB)
```

**Design choices:**
- **`src/`** keeps Phase 2 logic in one place; `compliance_agent.py` is a thin CLI that calls `src`.
- **No new config files** — we load `config/rules.yaml` as-is.
- **Tests** use synthetic text only (no real patient data); fixtures live in code for reproducibility.

---

## 2. Module Breakdown

| Module | Responsibility | Inputs | Outputs | Constraint |
|--------|----------------|--------|---------|------------|
| **rule_engine** | Run all deterministic checks from `rules.yaml`. No LLM. | Report text (string), path to `rules.yaml` | List of violations: `violation_type`, `severity`, `evidence_text`, `rule_id` | Does not decide PASS/FAIL alone; that is in hybrid_decision. |
| **rag_explainer** | (1) Retrieve top-k chunks from ChromaDB for each violation type/category. (2) Call LLM **only** to generate explanation + suggested_fix; LLM must cite retrieved text. | Report text, list of rule violations, index path, top_k | Per violation: `explanation`, `suggested_fix`, `retrieved_regulations` (source + text). | LLM does **not** make compliance decisions or invent regulations. |
| **hybrid_decision** | Map severities to status: PASS / FAIL / NEEDS_REVIEW. Deterministic. | List of violations (with severity) | `compliance_status`, optional summary. | FAIL if any critical or high; NEEDS_REVIEW if only medium; PASS if none. |
| **schemas** | Data classes or Pydantic models for: Violation, RetrievedRegulation, ComplianceReport (full JSON output). | — | Typed structures for orchestrator and tests. | Matches the required JSON shape. |
| **compliance_agent** | Load config and index; run rule_engine → rag_explainer → hybrid_decision; return structured JSON. | Report text (file path or string), options (e.g. top_k) | Single JSON object (compliance_status, violations, retrieved_regulations). | Backend-only; no UI. |

**Rule → severity mapping (deterministic):**
- **privacy** → `critical`
- **mandatory_reporting_context** (escalation flags) → `high` (mandatory reporting required)
- **adverse_event** (trigger present but no reporting context) → `high` (non-compliance)
- **off_label_promotion** → `high`
- **comparative_claims** → `medium`

**Status logic:**
- If any `critical` or `high` → **FAIL**
- Else if any `medium` → **NEEDS_REVIEW**
- Else → **PASS**

---

## 3. Data Flow (Textual)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  INPUT: One “report” (e.g. promotional text, safety narrative) — string       │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  A. RULE ENGINE (deterministic)                                              │
│  - Load config/rules.yaml                                                    │
│  - Run: PII/PHI detection → privacy violation (critical)                     │
│        AE trigger keywords → adverse_event violation (high if no context)    │
│        Escalation flags → mandatory_reporting_context (high)                 │
│        Phrase patterns → off_label_promotion (high)                          │
│        Indicators → comparative_claims (medium)                              │
│  - Output: list of { violation_type, severity, evidence_text, rule_id }      │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  B. RAG EXPLAINER                                                            │
│  - If no violations: skip LLM; retrieved_regulations = [] or from one generic │
│    query for “compliance”.                                                   │
│  - If violations: for each violation (or per category to limit calls),      │
│      (1) Query ChromaDB with evidence_text / violation_type → top-k chunks   │
│      (2) Call LLM with: violation + retrieved text only; prompt:             │
│          “Explain why this is a violation in plain English; cite the        │
│           regulation snippet; suggest a fix. Do not invent regulations.”     │
│  - Output: same violations enriched with explanation, suggested_fix,         │
│            retrieved_regulations (source + text)                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  C. HYBRID DECISION                                                          │
│  - Input: list of violations (with severity)                                 │
│  - Apply status rule: critical/high → FAIL; else medium → NEEDS_REVIEW;     │
│    else PASS                                                                 │
│  - Output: compliance_status (PASS | FAIL | NEEDS_REVIEW)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  D. STRUCTURED OUTPUT                                                        │
│  - Build final JSON: compliance_status, violations (with type, severity,     │
│    evidence, regulatory_basis, explanation, suggested_fix),                 │
│    retrieved_regulations (source, text)                                      │
│  - regulatory_basis: from rule_id + retrieved source (e.g. “GDPR Article 9”) │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: Single JSON (to stdout, file, or test assertion)                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Important:** The LLM is never asked “is this compliant?” — only “explain this violation and suggest a fix using these regulation snippets.” Decisions come only from the rule engine + hybrid_decision.

---

## 4. Test Suite (Synthetic Reports)

| Test case | Content (synthetic) | Expected |
|-----------|---------------------|----------|
| **Clean** | Short narrative with no PII, no AE keywords, no off-label or comparative phrasing | PASS, no violations |
| **Privacy** | “Patient John Smith, 555-123-4567, from Boston reported…” | FAIL; critical; Patient Privacy Violation |
| **Off-label** | “This product is recommended for weight loss.” (where approved indication is different) | FAIL or NEEDS_REVIEW; off-label promotion |
| **AE without reporting** | “Patient experienced nausea and discontinued medication.” (no “serious”/reporting context) | Violation: AE detected, no reporting context → high |
| **Comparative** | “Our drug is better than Drug X.” | NEEDS_REVIEW; comparative claim, medium |

We will **not** store or output real patient data; all test text is made up.

---

## 5. Clarifications / Assumptions

1. **PII/PHI detection:** We implement simple pattern-based checks (e.g. regex for phone-like digits, “patient” + capitalized name pattern, email regex). We do **not** use NER models or store real identifiers.
2. **“AE without reporting context”:** If trigger keywords are present but none of the `mandatory_reporting_context` escalation flags appear in the text, we flag as violation (reporting expected but context missing). No timeline logic.
3. **Approved indication:** For off-label we only detect promotional phrasing; we do **not** have a real approved-indication DB. We assume “approved indication context” is absent in the report unless we add a simple placeholder (e.g. optional config list). **Recommendation:** flag presence of off-label phrases as medium/high and let explanation say “verify against approved indication.”
4. **LLM choice:** We use one provider (e.g. OpenAI API or local Ollama) behind an env var (e.g. `OPENAI_API_KEY`). No fine-tuning; prompt-only.
5. **ChromaDB path:** Read from `outputs/vector_index/` (Phase 1 path). Same embedding model as Phase 1 (`all-MiniLM-L6-v2`) for query embedding.
6. **regulatory_basis:** Filled from retrieved chunk’s `source` (and optionally a snippet of the chunk); we do not parse “Article 9” from the chunk automatically—we can put “GDPR” or “GDPR (see retrieved text)” unless we add minimal parsing.

---

## 6. What We Will Not Do (Phase 2)

- No UI, no FastAPI, no frontend.
- No changes to Phase 1 artifacts (notebooks, rules.yaml, sources_metadata, vector index, chunking).
- No new regulations or new rules in `rules.yaml`.
- No retraining of LLMs.
- No storage or output of real patient data.
- No claim of legal or regulatory certification.

---

## 7. Expected Deliverables (After Confirmation)

- `src/rule_engine.py` — deterministic checks from rules.yaml
- `src/rag_explainer.py` — ChromaDB retrieval + LLM explanation only
- `src/hybrid_decision.py` — status from severities
- `src/schemas.py` — structured output types
- `compliance_agent.py` — orchestrator CLI
- `tests/fixtures/synthetic_reports.py` — test report strings
- `tests/test_compliance_agent.py` — test runner
- `notebooks/05_compliance_demo.ipynb` — demo with test cases and JSON output
- `requirements-phase2.txt` or additions to `requirements.txt` (e.g. openai, pydantic) — no change to Phase 1 deps required for Phase 1 notebooks

---

## 8. Confirmation Checklist

Please confirm or adjust:

1. **Folder structure** — Add only `src/`, `compliance_agent.py`, `tests/`, and `notebooks/05_compliance_demo.ipynb`. No changes to existing Phase 1 paths.
2. **Module breakdown** — Rule engine → RAG explainer → hybrid decision → structured output; LLM only as explainer.
3. **Severity mapping** — privacy=critical; AE without context, mandatory_reporting, off_label=high; comparative=medium. Status: any critical/high → FAIL; else any medium → NEEDS_REVIEW; else PASS.
4. **PII detection** — Pattern-based (regex / simple heuristics), no NER, no real data.
5. **Off-label** — Flag phrase patterns; no approved-indication DB; explanation suggests “verify against approved indication.”
6. **LLM** — Single provider via env var; prompt-only; no decision role.

Once you confirm (or specify changes), implementation will start without modifying any Phase 1 artifact.
