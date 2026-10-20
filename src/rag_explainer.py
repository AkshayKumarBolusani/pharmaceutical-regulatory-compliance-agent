"""
Phase 2 — RAG-grounded LLM explanation only.
Retrieves top-k regulatory clauses from ChromaDB; calls LLM to explain violation and suggest fix.
LLM does NOT decide compliance; it only explains using retrieved text.
"""

import json
import os
from pathlib import Path
from typing import Any

from .schemas import RetrievedRegulation, Violation, apply_trace


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# --- Source-manifest join (Feature 1) -----------------------------------------
# Chunk metadata carries source_id = clean-text file stem; the manifest at
# data/raw_policies/sources_metadata.json keys entries by the source PDF's
# file name, whose stem is the same identifier. The join supplies the
# document title / version / official URL for the evidence trace. Anything
# missing stays empty — metadata is never invented.
_MANIFEST_MAP: dict[str, dict] | None = None


def _manifest_map() -> dict[str, dict]:
    """Map of clean-text file stem -> manifest entry (cached; {} if absent)."""
    global _MANIFEST_MAP
    if _MANIFEST_MAP is None:
        _MANIFEST_MAP = {}
        try:
            path = _get_project_root() / "data" / "raw_policies" / "sources_metadata.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry in data.get("sources", []):
                fname = entry.get("file")
                if fname:
                    _MANIFEST_MAP[Path(fname).stem] = entry
        except Exception:
            _MANIFEST_MAP = {}
    return _MANIFEST_MAP


def _apply_manifest(reg: RetrievedRegulation) -> RetrievedRegulation:
    """Fill title/version_date/official_url from the source manifest when an
    entry matches the chunk's source_id; otherwise leave them empty."""
    entry = _manifest_map().get(reg.source_id)
    if entry:
        reg.title = entry.get("name") or ""
        reg.version_date = entry.get("version_date") or ""
        reg.official_url = entry.get("official_url") or ""
    return reg


def retrieve(
    query: str,
    index_path: Path,
    top_k: int = 3,
    collection_name: str = "policy_chunks",
) -> list[RetrievedRegulation]:
    """Query ChromaDB for top-k chunks. Uses ChromaDB ONNX all-MiniLM-L6-v2 (same model as Phase 1, no PyTorch)."""
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    client = chromadb.PersistentClient(path=str(index_path), settings=Settings(anonymized_telemetry=False))
    collection = client.get_collection(collection_name)
    ef = ONNXMiniLM_L6_V2()
    # ONNX model returns list of arrays; query_embeddings expects list of lists
    q_emb = ef([query])
    q_emb_list = [emb.tolist() for emb in q_emb]
    results = collection.query(
        query_embeddings=q_emb_list,
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas"],
    )
    docs = results["documents"][0] or []
    metas = results["metadatas"][0] or []
    regs = []
    for doc, meta in zip(docs, metas):
        reg = RetrievedRegulation(
            source=meta.get("source", "Unknown"),
            text=doc,
            source_id=meta.get("source_id", ""),
            country=meta.get("country", ""),
            category=meta.get("category", ""),
        )
        regs.append(_apply_manifest(reg))
    return regs


def _get_llm_client():
    """
    Prefer Groq if GROQ_API_KEY is set (OpenAI-compatible); else use OpenAI.
    Returns (client, model_name) or (None, None) if no key.
    """
    try:
        from openai import OpenAI
    except ImportError:
        return None, None
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if groq_key:
        return (
            OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1"),
            os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        )
    if openai_key:
        return OpenAI(api_key=openai_key), os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    return None, None


def explain_violation_with_llm(
    violation: dict,
    retrieved: list[RetrievedRegulation],
    api_key: str | None = None,
) -> tuple[str, str]:
    """
    Call LLM only to generate explanation and suggested_fix. No compliance decision.
    Uses Groq if GROQ_API_KEY is set, else OpenAI if OPENAI_API_KEY is set.
    Returns (explanation, suggested_fix).
    """
    try:
        from openai import OpenAI
    except ImportError:
        return (
            "Explanation unavailable (openai not installed). Review retrieved regulations below.",
            "Redact or revise the flagged content and re-run compliance check.",
        )
    if api_key:
        # Explicit key: assume Groq if base_url provided via env, else OpenAI
        base_url = os.environ.get("LLM_BASE_URL")
        if base_url and "groq" in base_url.lower():
            client = OpenAI(api_key=api_key, base_url=base_url)
            model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        else:
            client = OpenAI(api_key=api_key)
            model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    else:
        client, model = _get_llm_client()
    if not client:
        return (
            "Explanation unavailable (set GROQ_API_KEY or OPENAI_API_KEY). Review retrieved regulations below.",
            "Redact or revise the flagged content and re-run compliance check.",
        )
    reg_snippets = "\n\n".join([f"[{r.source}]: {r.text[:500]}..." if len(r.text) > 500 else f"[{r.source}]: {r.text}" for r in retrieved])
    prompt = f"""You are a compliance assistant. You must ONLY explain and suggest fixes. You must NOT decide whether something is compliant. Do NOT invent any regulations.

VIOLATION DETECTED (by a rule-based system):
- Type: {violation.get('violation_type', 'Unknown')}
- Evidence: {violation.get('evidence_text', '')}

RELEVANT REGULATORY TEXT (retrieved from official sources — cite only these):
{reg_snippets}

Tasks:
1. In 1–3 plain-English sentences, explain why this evidence may violate the regulations above. Cite the relevant snippet (source + key phrase).
2. In one sentence, suggest a concrete fix (e.g. "Remove patient name and use initials" or "Add reporting context for serious AEs").

Reply in this exact format:
EXPLANATION: <your explanation>
SUGGESTED FIX: <your one-sentence fix>"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        content = (resp.choices[0].message.content or "").strip()
        expl, fix = content, ""
        if "SUGGESTED FIX:" in content:
            parts = content.split("SUGGESTED FIX:", 1)
            expl = parts[0].replace("EXPLANATION:", "").strip()
            fix = parts[1].strip()
        elif "EXPLANATION:" in content:
            expl = content.replace("EXPLANATION:", "").strip()
        return (expl, fix)
    except Exception as e:
        return (
            f"Explanation could not be generated ({e!s}). Review retrieved regulations above.",
            "Redact or revise the flagged content and re-run compliance check.",
        )


def enrich_violations_with_rag(
    raw_violations: list[dict],
    index_path: Path,
    top_k: int = 3,
    use_llm: bool = True,
    api_key: str | None = None,
) -> tuple[list[Violation], list[RetrievedRegulation]]:
    """
    For each violation: retrieve top-k clauses, optionally call LLM for explanation/suggested_fix.
    Returns (list of Violation, list of all retrieved regulations for report).
    """
    all_retrieved: list[RetrievedRegulation] = []
    seen: set[tuple[str, str]] = set()

    violations_out: list[Violation] = []
    for v in raw_violations:
        query = v.get("evidence_text", "") or v.get("violation_type", "")
        retrieved = [_apply_manifest(r) for r in retrieve(query, index_path, top_k=top_k)]
        for r in retrieved:
            key = (r.source, r.text[:100])
            if key not in seen:
                seen.add(key)
                all_retrieved.append(r)
        regulatory_basis = retrieved[0].source if retrieved else ""
        explanation = ""
        suggested_fix = ""
        explanation_origin = "none"
        if use_llm and retrieved:
            explanation, suggested_fix = explain_violation_with_llm(v, retrieved, api_key)
            # The explainer returns "unavailable / could not be generated"
            # fallback strings when no LLM actually ran; only a real model
            # response counts as an LLM explanation (Feature 1 provenance).
            if explanation and not explanation.startswith(
                ("Explanation unavailable", "Explanation could not be generated")
            ):
                explanation_origin = "llm"
        violation = Violation(
            type=v["violation_type"],
            severity=v["severity"],
            evidence=v["evidence_text"],
            rule_id=v["rule_id"],
            regulatory_basis=regulatory_basis,
            explanation=explanation,
            suggested_fix=suggested_fix,
            retrieved_regulations=retrieved,
            # A finding is "supported" only when at least one retrieved
            # clause backs it; retrieval alone never proves a violation.
            evidence_status="supported" if retrieved else "insufficient_evidence",
            explanation_origin=explanation_origin,
        )
        if retrieved:
            top = retrieved[0]
            violation.source_title = top.title
            violation.source_version = top.version_date
            violation.source_url = top.official_url
        violations_out.append(apply_trace(violation, v))
    return violations_out, all_retrieved
