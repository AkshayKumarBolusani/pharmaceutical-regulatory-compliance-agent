# AI-Powered Pharmaceutical Regulatory Compliance Agent

**Phase 1: Policy Intelligence Layer (RAG-ready)**  
No UI, no LLM reasoning — ground truth and structure only.

---

## Before You Start

1. **Read the proposal:** [PHASE1_PROPOSAL.md](PHASE1_PROPOSAL.md)  
   It defines the folder structure and the **exact regulatory documents** to use (FDA, EMA, CDSCO, India Drugs and Magic Remedies Act 1954, ICH, GDPR, HIPAA). All sources are public and traceable.

2. **Download PDFs** from the official links in the proposal and place them in `data/raw_policies/` using the filenames in `sources_metadata.json`.

---

## How to Run Phase 1

1. **Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Download PDFs**  
   Place regulatory PDFs in `data/raw_policies/` using filenames from `data/raw_policies/sources_metadata.json` (see [PHASE1_PROPOSAL.md](PHASE1_PROPOSAL.md) for official links). India promotion document: `India_Drugs_and_Magic_Remedies_Act_1954.pdf`.

3. **Run notebooks in order**
   - `notebooks/01_policy_ingestion.ipynb` — PDF → clean text in `data/processed/clean_text/`
   - `notebooks/02_chunking.ipynb` — clause-aware chunks → `data/processed/chunked/chunks.json`
   - `notebooks/03_vector_index.ipynb` — embeddings + ChromaDB → `outputs/vector_index/`
   - `notebooks/04_retrieval_test.ipynb` — query → retrieved regulation text (no LLM)

4. **Rules**  
   Deterministic rules (privacy, AE triggers, off-label, comparative claims, `mandatory_reporting_context`) are in `config/rules.yaml`.

---

## Phase 2: Compliance Reasoning Engine

Phase 2 adds a **rule-based + RAG-grounded** compliance agent (no UI). Design: [PHASE2_PROPOSAL.md](PHASE2_PROPOSAL.md).

1. **Run the agent** (from project root):
   ```bash
   # Report from file
   python compliance_agent.py path/to/report.txt
   # Or stdin
   echo "Patient John Smith, 555-123-4567..." | python compliance_agent.py
   ```
   Output is JSON: `compliance_status`, `violations`, `retrieved_regulations`.

2. **Optional LLM explanations (Groq or OpenAI)**  
   The agent uses **Groq** if `GROQ_API_KEY` is set, otherwise **OpenAI** if `OPENAI_API_KEY` is set. Do not commit real keys.
   - Copy `.env.example` to `.env` and set `GROQ_API_KEY=your_key` (or use `OPENAI_API_KEY`).
   - Use the agent with `use_llm=True` (or env `COMPLIANCE_USE_LLM=1` for CLI). The LLM only explains violations using retrieved text; it does not make compliance decisions.

3. **Tests** (synthetic reports only):
   ```bash
   pip install pytest
   python -m pytest tests/test_compliance_agent.py -v
   ```

4. **Demo**  
   Run `notebooks/05_compliance_demo.ipynb` from project root to see all test cases and JSON output.

**Phase 1 is frozen:** Phase 2 does not modify `config/rules.yaml`, Phase 1 notebooks, or the vector index.

---

## Phase 3: Demo UI (End-to-End)

Phase 3 adds a **FastAPI backend** and a **single-page frontend** so you can submit a report in the browser and view compliance results. Phase 1 and Phase 2 logic are unchanged; the backend only wraps `compliance_agent.run()`.

### Run the demo

1. **From project root** (with venv activated and Phase 1 vector index built):
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Open in browser:** [http://localhost:8000/](http://localhost:8000/)

3. **Demo flow:**
   - Paste a pharmaceutical report (or use sample text from `tests/fixtures/synthetic_reports.py`).
   - Click **Check Compliance**.
   - View status (PASS / FAIL / NEEDS_REVIEW), violations, explanations, suggested fixes, and retrieved regulations.

### Environment variables

- **COMPLIANCE_USE_LLM** — Set to `1` to enable LLM explanations (uses `GROQ_API_KEY` or `OPENAI_API_KEY` from `.env`). Default: `1`.
- **GROQ_API_KEY** / **OPENAI_API_KEY** — Optional; see [LLM_SETUP.md](LLM_SETUP.md).

### API endpoints

- **GET /health** — Returns `{ "status": "ok" }`.
- **POST /check_compliance** — Body: `{ "report_text": "string" }`. Returns the same JSON as the Phase 2 engine: `compliance_status`, `violations`, `retrieved_regulations`.

---

## Project Assumptions

- College research project; not a production legal system.
- Regulations are for reference only; no claim of legal completeness or certification.
- All regulation text is from user-downloaded, publicly available official documents.
