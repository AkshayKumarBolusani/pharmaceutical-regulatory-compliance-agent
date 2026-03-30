# Phase 3 — Demo-Ready End-to-End System: Proposal

**Status:** Awaiting confirmation before implementation.

**Phase 1 and Phase 2 are frozen.** No changes to Phase 1 or Phase 2 artifacts (data, rules, vector index, notebooks, `src/`, `compliance_agent.py` logic).

---

## 1. Phase 3 Folder Structure (Additive Only)

Only **new** folders and files. No moves, no edits to existing Phase 1/2 code.

```
Pharmaceutical Regulatory Compliance Agent/
├── ... (all existing: config/, data/, notebooks/, src/, tests/, compliance_agent.py, etc.)
│
├── backend/                    # NEW
│   ├── __init__.py            # (optional, empty)
│   └── main.py                # FastAPI app: /health, POST /check_compliance
│
├── frontend/                   # NEW
│   ├── index.html             # Single-page UI: textarea, button, results area
│   └── static/
│       └── style.css          # Optional minimal CSS (or inline in HTML)
│
├── PHASE3_PROPOSAL.md         # This file
└── README.md                  # UPDATED: add Phase 3 run steps only
```

**Design choices:**
- **Backend:** Single `main.py` that imports `compliance_agent.run()` from the project root. Run with `uvicorn` from project root so `compliance_agent` and `src` resolve.
- **Frontend:** Plain HTML + CSS + JS (no build step, no React/Vue). Served either by FastAPI static mount or by opening `index.html` and calling the API (CORS allowed from backend).
- **No** `backend/requirements.txt` — use project root `requirements.txt` plus `uvicorn` and `fastapi` if not already present.

---

## 2. Backend–Frontend Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  USER: Opens frontend (index.html in browser)                                │
│  → Pastes report text in <textarea>                                          │
│  → Clicks "Check Compliance"                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (JavaScript)                                                        │
│  - Read report_text from textarea                                             │
│  - POST /check_compliance with JSON body: { "report_text": "..." }           │
│  - Target: same host as backend (e.g. http://localhost:8000) or configurable  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI main.py)                                                    │
│  - Receives POST /check_compliance                                            │
│  - Calls compliance_agent.run(report_text, use_llm=env COMPLIANCE_USE_LLM)    │
│  - No change to run() logic or return shape                                   │
│  - Returns 200 + JSON: { compliance_status, violations, retrieved_regulations }│
│  - On exception: 500 + JSON { "detail": "..." }                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (JavaScript)                                                        │
│  - Parse JSON response                                                        │
│  - Display:                                                                   │
│      - Compliance status (PASS=green, FAIL=red, NEEDS_REVIEW=amber)           │
│      - List of violations (type, severity, evidence, explanation, suggested_fix)│
│      - Retrieved regulations (source + text snippet) if present               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**CORS:** Backend will enable CORS for the frontend origin (e.g. `http://localhost:8000` when frontend is served by FastAPI, or a separate port if we serve HTML from FastAPI).

**Serving frontend:** Option A — FastAPI serves `frontend/index.html` and `frontend/static/` at `/` and `/static/` so one process serves both API and UI. Option B — Open `frontend/index.html` as file and set API base URL to `http://localhost:8000`; backend allows that origin. **Recommendation:** Option A (single run command, no CORS issues).

---

## 3. API Contract (Exact)

**POST /check_compliance**

- **Request body:** `{ "report_text": "string" }`
- **Success (200):**  
  `{ "compliance_status": "PASS"|"FAIL"|"NEEDS_REVIEW", "violations": [...], "retrieved_regulations": [...] }`  
  Same shape as `compliance_agent.run()` return.
- **Error (e.g. 500):** `{ "detail": "error message" }`

**GET /health**

- **Success (200):** `{ "status": "ok" }` (or similar minimal JSON).

---

## 4. Exact Run Commands

**Assumptions:** Venv activated from project root; `outputs/vector_index/` exists (Phase 1); dependencies installed (`pip install -r requirements.txt`). Add to `requirements.txt` if missing: `fastapi`, `uvicorn`.

**4.1 Run backend (and serve frontend)**

From **project root**:

```bash
cd "/Users/kumar/Documents/projects/new projects/Pharmaceutical Regulatory Compliance Agent"
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
export COMPLIANCE_USE_LLM=1   # optional, for LLM explanations
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- UI: `http://localhost:8000/` (FastAPI serves `frontend/index.html` at root).
- Health: `http://localhost:8000/health`

**4.2 Optional: frontend only (if served separately)**

If we keep frontend as static file and don’t mount it in FastAPI:

- Open `frontend/index.html` in browser (file://) and set API URL to `http://localhost:8000`, with backend started as above and CORS set for that origin.

**Recommendation:** Single-command run: backend serves both API and static frontend so the only command is the `uvicorn` line above.

---

## 5. UI Content (Minimal)

- **One textarea:** “Paste your pharmaceutical report below”
- **One button:** “Check Compliance”
- **Results section (after response):**
  - **Status badge:** PASS (green) / FAIL (red) / NEEDS_REVIEW (amber)
  - **Violations:** for each — type, severity, evidence; explanation (if present); suggested fix (if present)
  - **Retrieved regulations:** collapsible or short list (source + text snippet)
- No auth, no DB, no extra frameworks. Plain HTML + minimal CSS + vanilla JS.

---

## 6. What Will Not Be Done (Phase 3)

- No changes to Phase 1 or Phase 2 artifacts.
- No new rules, regulations, or ML models.
- No authentication, user accounts, or database.
- No legal or regulatory certification claims.
- No storage of real patient data.

---

## 7. README Update (Additive Only)

Add a **“Phase 3: Demo UI”** section with:

- How to run: `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000` from project root.
- Open `http://localhost:8000/` for the UI.
- Env vars: `COMPLIANCE_USE_LLM`, `GROQ_API_KEY` / `OPENAI_API_KEY` (optional).
- Demo steps: paste sample report (e.g. from synthetic_reports), click Check Compliance, view status and violations.

---

## 8. Confirmation Checklist

Please confirm:

1. **Folder structure:** Add only `backend/` (with `main.py`) and `frontend/` (with `index.html` and optional `static/style.css`). No other new top-level folders.
2. **Backend:** FastAPI in `backend/main.py`; imports and calls `compliance_agent.run()`; exposes `POST /check_compliance` and `GET /health`; serves frontend at `/` (and static at `/static` if used).
3. **Frontend:** Plain HTML + CSS + JS; one page with textarea, button, and results (status, violations, explanations, suggested fixes, retrieved regulations).
4. **Run:** Single command from project root: `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`; UI at `http://localhost:8000/`.
5. **CORS:** Backend allows necessary origins (e.g. same origin when UI is served by FastAPI).

Once you confirm (or request small changes), implementation will proceed without modifying any Phase 1 or Phase 2 artifact.
