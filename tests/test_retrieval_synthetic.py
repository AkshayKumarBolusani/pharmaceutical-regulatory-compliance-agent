"""Synthetic retrieval tests for scripts/build_index.py + src/rag_explainer.py.

Everything here is SYNTHETIC: the "regulatory" documents below are short
invented texts written for these tests. They are not real regulations and
make no legal claims.

The tests build a real ChromaDB index in a pytest tmp dir using the same
builder the CLI uses, then query it through the production
``rag_explainer.retrieve()`` path. They need no API keys. They DO need
chromadb and its ONNX embedding model (all-MiniLM-L6-v2, ~80 MB, downloaded
by chromadb into ~/.cache/chroma on first use); if that model is not
available (e.g. no network on first run), the index-dependent tests skip
with an explicit reason instead of failing.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# --- Synthetic corpus (invented for tests; NOT real regulations) ---
SYNTH_ADVERSE_EVENTS = """\
FAKE REGULATION ALPHA — SYNTHETIC TEST DOCUMENT

Article 1
A marketing authorisation holder must report every serious adverse reaction
to the competent authority no later than fifteen calendar days after the
day on which the holder first became aware of the reaction occurring.

Article 2
Non-serious adverse reactions shall be recorded in the periodic safety
summary and submitted within ninety days of the reporting period closing,
together with a line listing of all cases received during that period.
"""

SYNTH_PRIVACY = """\
FAKE REGULATION BETA — SYNTHETIC TEST DOCUMENT

Section 1
A covered entity must not disclose a patient's full name together with a
telephone number or email address in any promotional material, and must
apply safeguards to protect the confidentiality of personal health data.

Section 2
When a disclosure of personal health data is required by this regulation,
only the minimum amount of personal data necessary for the purpose may be
shared with the receiving party, and the disclosure must be documented.
"""

SYNTH_PROMOTION = """\
FAKE REGULATION GAMMA — SYNTHETIC TEST DOCUMENT

Section 1
Promotional material for a medicinal product must present a fair balance
of benefit information and risk information, and must not claim that the
product is superior to a competing product without substantiating data.

Section 2
An advertisement must not promote a medicinal product for an indication
that has not been approved by the competent authority, and must include
the required risk disclosure statement for general audiences in print.
"""


def _model_available() -> bool:
    """True if chromadb's ONNX embedder can be constructed and run."""
    try:
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (
            ONNXMiniLM_L6_V2,
        )

        ONNXMiniLM_L6_V2()(["probe"])
        return True
    except Exception:
        return False


MODEL_AVAILABLE = _model_available()
requires_model = pytest.mark.skipif(
    not MODEL_AVAILABLE,
    reason=(
        "chromadb ONNX embedding model (all-MiniLM-L6-v2) not available in "
        "this environment (first-use download may have failed); "
        "index-building tests skipped, not failed."
    ),
)


@pytest.fixture(scope="module")
def synthetic_index(tmp_path_factory):
    """Build a real index from the synthetic corpus via scripts/build_index.py."""
    import build_index

    base = tmp_path_factory.mktemp("synthetic_corpus")
    input_dir = base / "clean_text"
    input_dir.mkdir()
    (input_dir / "SYNTH_Adverse_Events.txt").write_text(SYNTH_ADVERSE_EVENTS, encoding="utf-8")
    (input_dir / "SYNTH_Privacy.txt").write_text(SYNTH_PRIVACY, encoding="utf-8")
    (input_dir / "SYNTH_Promotion.txt").write_text(SYNTH_PROMOTION, encoding="utf-8")
    output_dir = base / "vector_index"
    # No manifest exists for the synthetic stems: the builder must fall back
    # to filename-derived metadata instead of skipping the files.
    count = build_index.build_index(input_dir, output_dir, manifest_path=None)
    return {"input_dir": input_dir, "output_dir": output_dir, "count": count}


def test_clause_aware_split_on_article_boundaries():
    """Chunking alone needs no model: verify the notebook-02 splitter behaviour."""
    import build_index

    chunks = build_index.clause_aware_split(SYNTH_ADVERSE_EVENTS)
    assert len(chunks) >= 2
    assert any("fifteen calendar days" in c for c in chunks)
    # Tiny fragments below the 50-char floor are dropped by design.
    assert build_index.clause_aware_split("") == []


@requires_model
def test_index_builds_and_counts_chunks(synthetic_index):
    import chromadb
    from chromadb.config import Settings

    assert synthetic_index["count"] > 0
    client = chromadb.PersistentClient(
        path=str(synthetic_index["output_dir"]),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection("policy_chunks")
    assert collection.count() == synthetic_index["count"]


@requires_model
def test_retrieve_returns_expected_chunk(synthetic_index):
    from src.rag_explainer import retrieve

    results = retrieve(
        "serious adverse reaction reporting deadline fifteen days",
        synthetic_index["output_dir"],
        top_k=2,
    )
    assert len(results) == 2
    # Top hit is from the adverse-events document, and the exact clause is
    # in the top 2 (on a 6-chunk synthetic corpus the sibling Article 2
    # chunk can outrank Article 1; we assert document-level precision and
    # clause presence rather than an exact rank-1 clause match).
    assert results[0].source == "SYNTH_Adverse_Events"
    assert any("fifteen calendar days" in r.text for r in results)


@requires_model
def test_retrieved_chunks_carry_metadata(synthetic_index):
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(synthetic_index["output_dir"]),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection("policy_chunks")
    got = collection.get(include=["metadatas"])
    assert got["metadatas"], "index contains no chunks"
    for meta in got["metadatas"]:
        # The four fields rag_explainer / notebook 03 rely on.
        assert {"source", "source_id", "country", "category"} <= set(meta)
        assert meta["source"] and meta["source_id"]


@requires_model
def test_retrieve_privacy_query_hits_privacy_doc(synthetic_index):
    from src.rag_explainer import retrieve

    results = retrieve(
        "patient name telephone number disclosure in promotional material",
        synthetic_index["output_dir"],
        top_k=2,
    )
    assert results
    assert any("telephone number" in r.text for r in results)


def test_missing_index_degrades_to_rules_only(tmp_path):
    """compliance_agent.run() with a nonexistent index path must still
    return a deterministic rules-only report (no retrieval, no LLM)."""
    from compliance_agent import run

    report = run(
        "Patient John Smith, 555-123-4567, had nausea.",
        use_llm=False,
        index_path=tmp_path / "does_not_exist",
    )
    assert report["compliance_status"] == "FAIL"  # privacy (critical) via rules
    assert report["retrieved_regulations"] == []
    assert any(v["rule_id"] == "privacy" for v in report["violations"])
