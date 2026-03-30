"""
Phase 3 — FastAPI backend wrapper for the Phase 2 compliance engine.
Imports and reuses compliance_agent.run(); no business logic duplication.
Stateless API; no database. Serves frontend at /.
"""

import os
import sys
from pathlib import Path

# Ensure project root is on path when running: uvicorn backend.main:app
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# Load .env for COMPLIANCE_USE_LLM, GROQ_API_KEY, etc.
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

app = FastAPI(
    title="Pharmaceutical Compliance API",
    description="Phase 3 wrapper: check compliance via Phase 2 engine.",
    version="1.0",
)

# CORS so frontend can call API from same or different origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CheckComplianceRequest(BaseModel):
    report_text: str


@app.get("/health")
def health():
    """Simple health check."""
    return {"status": "ok"}


@app.post("/check_compliance")
def check_compliance(req: CheckComplianceRequest):
    """
    Run Phase 2 compliance engine on report text.
    Returns compliance_status, violations, retrieved_regulations unchanged.
    """
    use_llm = os.environ.get("COMPLIANCE_USE_LLM", "1").strip().lower() in ("1", "true", "yes")
    try:
        from compliance_agent import run
        result = run(req.report_text.strip(), use_llm=use_llm)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve frontend: index.html at /, static files at /static
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the single-page compliance check UI."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@app.get("/static/{path:path}")
def static_file(path: str):
    """Serve CSS/JS from frontend/static/."""
    file_path = STATIC_DIR / path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(file_path)
