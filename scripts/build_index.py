#!/usr/bin/env python3
"""
Build the ChromaDB policy index from cleaned regulatory texts.

This script is the scripted equivalent of notebooks 02 + 03 (Phase 1):
it replaces the manual "run notebook 02, then notebook 03" procedure with a
single reproducible command:

    python scripts/build_index.py [--input-dir DIR] [--output-dir DIR]
                                  [--manifest PATH] [--collection NAME]

Pipeline
--------
1. Read every ``*.txt`` file in the input directory (default:
   ``data/processed/clean_text/``).
2. Split each document into clause-aware chunks with ``clause_aware_split``,
   copied verbatim from notebook 02 (splits on ``Article N``, ``Section N``
   and numbered headings; short heading-only fragments are merged with the
   following block; blocks shorter than 50 characters are dropped).
3. Attach per-chunk metadata ``{source, source_id, country, category}``
   exactly as notebook 02/03 did. ``source`` is the issuing authority from
   ``data/raw_policies/sources_metadata.json`` (e.g. ``"EMA"``);
   ``source_id`` is the clean-text file stem, which is the manifest lookup
   key (notebook 02 behaviour — *not* the manifest ``"id"`` field).
4. Embed all chunks with ChromaDB's ``ONNXMiniLM_L6_V2`` embedder and store
   them in a persistent ChromaDB collection named ``policy_chunks`` in the
   output directory (default: ``outputs/vector_index/``), with sequential
   ids ``chunk_0``, ``chunk_1``, ... as in notebook 03. An existing
   collection of the same name is deleted and rebuilt.

Documented deviations from the notebooks
-----------------------------------------
1. **Embedder implementation.** Notebook 03 embedded with
   sentence-transformers (``SentenceTransformer('all-MiniLM-L6-v2')``,
   PyTorch). This script uses ChromaDB's ``ONNXMiniLM_L6_V2`` — the same
   underlying model (all-MiniLM-L6-v2, 384 dimensions) but, critically, the
   *same implementation that ``src/rag_explainer.py`` uses at query time*.
   Indexing and querying therefore always share one embedder, which the
   notebook path did not guarantee.
2. **Unlisted input files.** Notebook 02 silently skipped any ``.txt`` file
   whose stem had no manifest entry. This script indexes such files with
   fallback metadata (``source``/``source_id`` = file stem,
   ``country``/``category`` = ``"Unknown"``) and prints a warning, so the
   script works on any directory of ``.txt`` sources (e.g. small synthetic
   corpora used by the tests) instead of only the project corpus.
3. **Steps chained.** Notebooks 02 and 03 were separate, with an
   intermediate ``data/processed/chunked/chunks.json`` file. This script
   performs chunking and indexing in one pass and does not write the
   intermediate JSON.

The output directory is gitignored (``outputs/vector_index/`` in
``.gitignore``): the index is a generated artifact and should be rebuilt
from the cleaned texts, not committed.
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "processed" / "clean_text"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "vector_index"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "raw_policies" / "sources_metadata.json"
COLLECTION_NAME = "policy_chunks"
FALLBACK_COUNTRY = "Unknown"
FALLBACK_CATEGORY = "Unknown"


# --- Chunking: copied verbatim from notebooks/02_chunking.ipynb (cell 3) ---
def clause_aware_split(text: str) -> list[str]:
    """Split text into clauses by common regulatory section patterns."""
    # Patterns: Article 1, Article 12; Section 1, Section 2.3; 1. Introduction, 2.1.1 Subsection
    pattern = re.compile(
        r'(?=\s*(?:Article\s+\d+|Section\s+\d+(?:\.\d+)*|'
        r'\d+\.(?:\d+\.)*\s*[A-Z]|'
        r'\n\s*\d+\.\s))',
        re.IGNORECASE
    )
    parts = pattern.split(text)
    chunks = []
    current = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # If it looks like a heading line only, merge with next
        if len(p) < 80 and not p.endswith('.'):
            current.append(p)
            continue
        current.append(p)
        block = '\n'.join(current).strip()
        if len(block) >= 50:  # skip tiny fragments
            chunks.append(block)
        current = []
    if current:
        block = '\n'.join(current).strip()
        if len(block) >= 50:
            chunks.append(block)
    return chunks if chunks else [text.strip()] if text.strip() else []


def load_manifest(manifest_path: Path | None) -> dict[str, dict]:
    """Return {clean-text file stem: manifest source entry}.

    Mirrors notebook 02 cell 1: the manifest is keyed by Path(file).stem.
    Returns an empty dict if no manifest is available.
    """
    if manifest_path is None or not Path(manifest_path).exists():
        return {}
    with open(manifest_path, encoding="utf-8") as f:
        meta = json.load(f)
    return {Path(s["file"]).stem: s for s in meta.get("sources", []) if s.get("file")}


def build_chunks_for_document(clean_path: Path, source_info: dict, source_id: str) -> list[dict]:
    """Build list of chunk dicts for one document (notebook 02, cell 3)."""
    text = clean_path.read_text(encoding="utf-8")
    raw_chunks = clause_aware_split(text)
    chunks = []
    for i, seg in enumerate(raw_chunks):
        chunks.append({
            "text": seg,
            "source": source_info.get("authority", source_id),
            "country": source_info["country"],
            "category": source_info["category"],
            "source_id": source_id,
            "chunk_index": i,
        })
    return chunks


def build_chunks(input_dir: Path, manifest_path: Path | None = None) -> list[dict]:
    """Chunk every .txt file in input_dir into metadata-tagged chunk dicts."""
    input_dir = Path(input_dir)
    sources = load_manifest(manifest_path)
    all_chunks: list[dict] = []
    for txt_file in sorted(input_dir.glob("*.txt")):
        stem = txt_file.stem
        source_info = sources.get(stem)
        if source_info is None:
            print(f"WARNING: no manifest entry for {stem}; using fallback metadata.",
                  file=sys.stderr)
            source_info = {
                "authority": stem,
                "country": FALLBACK_COUNTRY,
                "category": FALLBACK_CATEGORY,
            }
        doc_chunks = build_chunks_for_document(txt_file, source_info, stem)
        all_chunks.extend(doc_chunks)
        print(f"{stem}: {len(doc_chunks)} chunks")
    return all_chunks


def build_index(
    input_dir: Path,
    output_dir: Path,
    manifest_path: Path | None = None,
    collection_name: str = COLLECTION_NAME,
) -> int:
    """Chunk + embed + store. Returns the number of chunks indexed."""
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    if not any(input_dir.glob("*.txt")):
        raise FileNotFoundError(f"No .txt files in input directory: {input_dir}")

    chunks = build_chunks(input_dir, manifest_path)
    if not chunks:
        raise ValueError(f"No chunks produced from {input_dir}")

    texts = [c["text"] for c in chunks]
    ef = ONNXMiniLM_L6_V2()
    embeddings = [emb.tolist() for emb in ef(texts)]

    output_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(output_dir), settings=Settings(anonymized_telemetry=False)
    )
    # Remove if re-running to avoid duplicate ids (notebook 03 behaviour)
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        name=collection_name,
        metadata={"description": "Phase 1 regulatory policy chunks"},
    )
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "source": c["source"],
            "country": c["country"],
            "category": c["category"],
            "source_id": c.get("source_id", ""),
        }
        for c in chunks
    ]
    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    count = collection.count()
    print(f"Index saved. Collection: {collection_name}, count: {count}")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the ChromaDB policy index from cleaned regulatory texts."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR,
                        help=f"Directory of .txt sources (default: {DEFAULT_INPUT_DIR})")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help=f"ChromaDB persistence directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                        help=f"sources_metadata.json for chunk metadata (default: {DEFAULT_MANIFEST})")
    parser.add_argument("--collection", default=COLLECTION_NAME,
                        help=f"Collection name (default: {COLLECTION_NAME})")
    args = parser.parse_args(argv)
    count = build_index(args.input_dir, args.output_dir, args.manifest, args.collection)
    print(f"Done. {count} chunks indexed from {args.input_dir} -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
