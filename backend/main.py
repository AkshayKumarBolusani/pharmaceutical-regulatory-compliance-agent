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
from pydantic import BaseModel, Field

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

# CORS: the shipped UI is served same-origin by this app, so cross-origin
# access is only a local-development convenience. Origins are therefore
# restricted to this app's own local addresses, and credentials are NOT
# allowed (the API is stateless and uses no cookies/auth). The previous
# wildcard + allow_credentials combination made Starlette reflect ANY
# requesting origin with credentials enabled — any website open in the
# user's browser could have called this local API (and spent the user's
# LLM API quota). See docs/SECURITY.md.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Demo-grade request-size limit for report_text (characters). Oversized
# bodies are rejected by pydantic validation with HTTP 422 before any
# processing happens. This is a local-demo safeguard, not a substitute
# for a reverse-proxy body limit in a real deployment.
MAX_REPORT_CHARS = 1_000_000


class CheckComplianceRequest(BaseModel):
    report_text: str = Field(max_length=MAX_REPORT_CHARS)


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
    except Exception:
        # Never return exception text to the client: str(e) can contain
        # absolute filesystem paths and provider internals. The full
        # traceback goes to the server log (stderr) only.
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Internal error while processing the report. See server log for details.",
        )


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
    """Serve CSS/JS from frontend/static/.

    The requested path is resolved and required to stay inside the static
    directory: `..` segments (raw or percent-encoded) previously escaped
    it and exposed arbitrary files readable by the server process
    (repository source, config, a local .env, /etc/passwd). Containment
    failures return the same 404 as a missing file.
    """
    static_root = STATIC_DIR.resolve()
    file_path = (static_root / path).resolve()
    if not file_path.is_relative_to(static_root) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(file_path)
