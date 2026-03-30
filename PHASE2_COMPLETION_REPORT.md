# Phase 2 — Completion Report  
## AI-Powered Pharmaceutical Regulatory Compliance Agent

**Status:** Complete  
**Phase 1:** Frozen (no modifications to Phase 1 artifacts)

---

## 1. Objective & Alignment

Phase 2 implements a **Compliance Reasoning Engine** that:

- **Detects** pharmaceutical regulatory violations using deterministic rules.
- **Explains** why a violation occurred using RAG-grounded LLM output.
- **Grounds** explanations in retrieved regulatory clauses (ChromaDB).
- **Suggests** corrective actions per violation.
- **Produces** an auditable, structured compliance decision (JSON).

This matches the project abstract: *“Automatically detects, explains, and prevents compliance violations at the point of report submission using RAG + hybrid reasoning.”*

**Constraints respected:** No legal certification claims; no invention of regulations; no retraining of LLMs; no frontend UI; no storage or output of real patient data. Implemented as a research prototype for a college project.

---

## 2. Scope Implemented

| Component | Description | Status |
|-----------|-------------|--------|
| **A. Rule-based compliance engine** | Deterministic checks from `config/rules.yaml`: privacy (PII/PHI), adverse event (trigger keywords), mandatory reporting context (escalation flags), off-label promotion, comparative claims. | Done |
| **B. RAG-grounded LLM reasoning** | Retrieval from existing ChromaDB index; LLM (Groq or OpenAI) used only to explain violations and suggest fixes; no compliance decisions by LLM. | Done |
| **C. Hybrid decision logic** | Deterministic mapping from violation severities to final status: PASS / FAIL / NEEDS_REVIEW. | Done |
| **D. Structured output** | JSON with `compliance_status`, `violations` (type, severity, evidence, rule_id, regulatory_basis, explanation, suggested_fix), `retrieved_regulations`. | Done |
| **E. Backend-only execution** | No UI; CLI and programmatic API only. | Done |

---

## 3. Deliverables

### 3.1 Code

| Item | Path | Purpose |
|------|------|---------|
| Rule engine | `src/rule_engine.py` | Loads `config/rules.yaml`; runs PII/PHI, AE, mandatory reporting, off-label, comparative checks. Returns list of violations with `violation_type`, `severity`, `evidence_text`, `rule_id`. |
| RAG explainer | `src/rag_explainer.py` | Queries ChromaDB (same embedding model as Phase 1); optionally calls LLM (Groq or OpenAI) for explanation and suggested fix. LLM does not decide compliance. |
| Hybrid decision | `src/hybrid_decision.py` | Maps violation severities to `PASS` / `FAIL` / `NEEDS_REVIEW`. |
| Schemas | `src/schemas.py` | Data classes for `Violation`, `RetrievedRegulation`, `ComplianceReport`; `to_dict()` for JSON output. |
| Orchestrator | `compliance_agent.py` | Entry point: runs rule_engine → rag_explainer → hybrid_decision; returns structured JSON. Reads report from file or stdin. |

### 3.2 Tests & Demo

| Item | Path | Purpose |
|------|------|---------|
| Synthetic reports | `tests/fixtures/synthetic_reports.py` | Five test cases: clean, privacy violation, off-label, AE without reporting, comparative claim. No real patient data. |
| Test suite | `tests/test_compliance_agent.py` | Asserts compliance status and rule_id for each fixture; validates output structure. |
| Demo notebook | `notebooks/05_compliance_demo.ipynb` | Runs agent on all synthetic cases; shows violations and full JSON for one example. Supports optional LLM (Groq/OpenAI via `.env`). |

### 3.3 Configuration & Documentation

- **Rules:** Phase 1 `config/rules.yaml` is read-only; no new rules added. Rule taxonomy includes `privacy`, `adverse_event`, `mandatory_reporting_context`, `off_label_promotion`, `comparative_claims`.
- **LLM setup:** `LLM_SETUP.md` describes Groq/OpenAI keys via `.env`; `.env.example` provides a template.

---

## 4. Design Summary

### 4.1 Severity Mapping (Deterministic)

| Rule / violation type | Severity |
|------------------------|----------|
| Privacy (PII/PHI detected) | critical |
| Adverse event (trigger keywords, no reporting context) | high |
| Mandatory reporting context (escalation flags present) | high |
| Off-label promotion (phrase patterns) | high |
| Comparative claims (indicators) | medium |

### 4.2 Decision Logic (Deterministic)

- **FAIL:** Any violation with severity `critical` or `high`.
- **NEEDS_REVIEW:** No critical/high; at least one `medium`.
- **PASS:** No violations.

### 4.3 Data Flow

1. **Input:** Report text (string).
2. **Rule engine:** Runs all checks from `config/rules.yaml`; outputs list of raw violations.
3. **RAG explainer:** For each violation, retrieves top-k regulatory chunks from ChromaDB; optionally calls LLM to generate explanation and suggested fix using retrieved text only.
4. **Hybrid decision:** Computes `compliance_status` from violation severities.
5. **Output:** Single JSON: `compliance_status`, `violations` (with explanation/suggested_fix when LLM used), `retrieved_regulations`.

### 4.4 LLM Role

The LLM is used **only** as an explainer: it receives the violation and retrieved regulatory snippets and produces plain-English explanation and a one-sentence suggested fix. It does **not** classify compliance or invent regulations. Compliance decisions are entirely rule-based and deterministic.

---

## 5. Test Suite & Evaluation

- **Five synthetic test cases** cover: clean report (PASS), privacy (FAIL, critical), off-label (FAIL, high), AE without reporting (FAIL, high), comparative claim (NEEDS_REVIEW, medium).
- **Test runner:** `python -m pytest tests/test_compliance_agent.py -v` from project root.
- **Demo:** Notebook 05 runs the agent on all five cases and prints one full JSON example (e.g. privacy violation). With `GROQ_API_KEY` or `OPENAI_API_KEY` set in `.env`, explanations and suggested fixes are populated via the LLM.

---

## 6. How to Run Phase 2

1. **Environment:** From project root, activate venv and ensure dependencies are installed (`pip install -r requirements.txt`). Phase 1 vector index must exist at `outputs/vector_index/` (run notebooks 01–03 if not already done).

2. **CLI (report from file):**
   ```bash
   python compliance_agent.py path/to/report.txt
   ```
   Or stdin:
   ```bash
   echo "Report text here..." | python compliance_agent.py
   ```
   Optional: set `COMPLIANCE_USE_LLM=1` to enable LLM explanations (requires `GROQ_API_KEY` or `OPENAI_API_KEY` in environment or `.env`).

3. **Demo notebook:** Open `notebooks/05_compliance_demo.ipynb`, run from project root, execute all cells. If `.env` contains `GROQ_API_KEY` (or `OPENAI_API_KEY`), the notebook uses the LLM for explanations.

4. **Tests:** `python -m pytest tests/test_compliance_agent.py -v`

---

## 7. Sample Output Structure

```json
{
  "compliance_status": "FAIL",
  "violations": [
    {
      "type": "Patient Privacy Violation",
      "severity": "critical",
      "evidence": "PII/PHI detected: phone number, patient/person name",
      "rule_id": "privacy",
      "regulatory_basis": "HIPAA",
      "explanation": "…",
      "suggested_fix": "…"
    }
  ],
  "retrieved_regulations": [
    { "source": "HIPAA", "text": "…" }
  ]
}
```

---

## 8. Phase 1 Freeze

Phase 2 does **not** modify:

- `config/rules.yaml` (read-only)
- Phase 1 notebooks (01–04)
- `data/raw_policies/`, `sources_metadata.json`
- Chunking logic or chunk schema
- Vector index location or embedding model

---

## 9. Conclusion

Phase 2 delivers a working compliance reasoning engine that combines deterministic rule-based detection with RAG-grounded LLM explanations and a clear, auditable JSON output. The design keeps compliance decisions rule-based and deterministic while using the LLM only for explanation and suggested fixes, aligned with the project abstract and suitable for demonstration and evaluation.

---

*Document generated for Phase 2 completion. Export this file to PDF or DOC if required for submission.*
