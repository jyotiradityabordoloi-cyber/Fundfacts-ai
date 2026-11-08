"""Phase 6 - Embed every chunk with all-MiniLM-L6-v2.

    python -m fundfacts.ingest.embed

What is embedded
- fact cards: their text as-is (already starts with the scheme name and field label)
- other chunks: "<document title>. <chunk text>" so a passage from a long SID still carries
  which document/scheme it belongs to

Output
    data/embeddings/embeddings.json   {model, backend, dim, normalized, embed_text, items: [{chunk_id, vector}]}
"""
from __future__ import annotations

import json
import time

import numpy as np

from fundfacts.config import settings
from fundfacts.embed import get_embedder


def embed_text(chunk: dict) -> str:
    return chunk["text"] if chunk["kind"] == "fact_card" else f"{chunk['title']}. {chunk['text']}"


def run() -> dict:
    chunks = json.loads((settings.paths.chunks / "chunks.json").read_text(encoding="utf-8"))
    emb = get_embedder()
    t0 = time.time()
    vectors = emb.encode([embed_text(c) for c in chunks])
    secs = time.time() - t0
    norms = np.linalg.norm(vectors, axis=1)
    assert vectors.shape == (len(chunks), settings.embedding.dim), vectors.shape
    assert np.allclose(norms, 1.0, atol=1e-3), "vectors must be L2-normalised"

    payload = {
        "model": settings.embedding.model,
        "backend": emb.backend,
        "dim": int(vectors.shape[1]),
        "normalized": True,
        "embed_text": "fact_card: text; others: '<title>. <text>'",
        "count": len(chunks),
        "items": [{"chunk_id": c["chunk_id"], "vector": [round(float(x), 6) for x in v]} for c, v in zip(chunks, vectors)],
    }
    settings.paths.embeddings.mkdir(parents=True, exist_ok=True)
    out = settings.paths.embeddings / "embeddings.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    print(f"[embed] {len(chunks)} chunks -> {vectors.shape[1]}-d vectors with {settings.embedding.model} "
          f"({emb.backend}) in {secs:.1f}s -> {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return payload


def main() -> None:
    run()


if __name__ == "__main__":
    main()
