"""Phase 7 - Store in ChromaDB, verify, export, report.

    python -m fundfacts.ingest.store
    python -m fundfacts.ingest.store --query "exit load HDFC Small Cap"   # quick check

Steps
1. Recreate the persistent collection `vector_db.collection` (cosine space).
2. Add every chunk with its precomputed vector and metadata.
3. Verify: collection count == chunk count, every chunk id present, stored vectors equal
   the embeddings file (spot check). Stop with an error otherwise.
4. Export the collection to vector_store/index.json - the exact same ids/text/metadata/vectors -
   for the serverless runtime, which cannot run a ChromaDB server.
5. Write data/build_report.json: sources, fact coverage, and the three counts.

index.json layout (compact): {"model", "dim", "collection", "count", "chunks": [metadata+text],
"vectors_b64": base64 of float32[count x dim] in chunk order}
"""
from __future__ import annotations

import base64
import json
import sys
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from fundfacts.config import settings
from fundfacts.sources import load_sources

META_KEYS = ["source_id", "scheme_id", "page", "section", "kind", "title", "url", "publisher",
             "doc_type", "doc_date", "fetched_at", "field"]
BATCH = 500


def _meta(chunk: dict) -> dict:
    """Chroma metadata values must be str/int/float/bool (no None)."""
    out = {}
    for k in META_KEYS:
        v = chunk.get(k)
        out[k] = "" if v is None else v
    return out


def load_inputs() -> tuple[list[dict], np.ndarray, dict]:
    chunks = json.loads((settings.paths.chunks / "chunks.json").read_text(encoding="utf-8"))
    emb = json.loads((settings.paths.embeddings / "embeddings.json").read_text())
    ids = [i["chunk_id"] for i in emb["items"]]
    if ids != [c["chunk_id"] for c in chunks]:
        raise SystemExit("embeddings.json is out of date with chunks.json - run the embed phase again")
    vectors = np.asarray([i["vector"] for i in emb["items"]], dtype=np.float32)
    return chunks, vectors, emb


def store(chunks: list[dict], vectors: np.ndarray, model: str):
    import chromadb

    client = chromadb.PersistentClient(path=str(settings.paths.chroma))
    name = settings.vector_db.collection
    if name in [c.name for c in client.list_collections()]:
        client.delete_collection(name)
    col = client.create_collection(name, metadata={"hnsw:space": "cosine", "embedding_model": model})
    for i in range(0, len(chunks), BATCH):
        part = chunks[i:i + BATCH]
        col.add(ids=[c["chunk_id"] for c in part], documents=[c["text"] for c in part],
                embeddings=vectors[i:i + BATCH].tolist(), metadatas=[_meta(c) for c in part])
    return col


def verify(col, chunks: list[dict], vectors: np.ndarray) -> dict:
    expected = [c["chunk_id"] for c in chunks]
    stored = set(col.get(include=[])["ids"])
    missing = [i for i in expected if i not in stored]
    sample = expected[:: max(1, len(expected) // 25)]
    got = col.get(ids=sample, include=["embeddings"])
    lookup = dict(zip(got["ids"], got["embeddings"]))
    idx = {cid: n for n, cid in enumerate(expected)}
    max_diff = max(float(np.abs(np.asarray(lookup[cid]) - vectors[idx[cid]]).max()) for cid in sample)
    result = {"chunks": len(chunks), "chroma": col.count(), "missing_ids": missing[:20],
              "vector_spot_check": len(sample), "vector_max_abs_diff": max_diff}
    if col.count() != len(chunks) or missing or max_diff > 1e-5:
        raise SystemExit(f"[store] VERIFY FAILED: {result}")
    return result


def export(chunks: list[dict], vectors: np.ndarray, model: str) -> int:
    payload = {
        "model": model,
        "dim": int(vectors.shape[1]),
        "collection": settings.vector_db.collection,
        "count": len(chunks),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "chunks": [{"chunk_id": c["chunk_id"], "text": c["text"], **_meta(c)} for c in chunks],
        "vectors_b64": base64.b64encode(vectors.astype("<f4").tobytes()).decode("ascii"),
    }
    out = settings.paths.index_export
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return out.stat().st_size


def build_report(counts: dict, export_bytes: int) -> dict:
    manifest = json.loads((settings.paths.raw / "manifest.json").read_text(encoding="utf-8"))
    facts = json.loads((settings.paths.facts / "facts.json").read_text(encoding="utf-8"))
    sources = load_sources()
    coverage: dict[str, dict] = {}
    for f in facts:
        coverage.setdefault(f["scheme_id"], {})[f["field"]] = f["status"]
    report = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "embedding_model": settings.embedding.model,
        "sources": {
            "registry": len(sources),
            "by_status": dict(Counter(s.status.value for s in sources)),
            "fetched": [m["source_id"] for m in manifest if m.get("path")],
            "not_fetched": {m["source_id"]: m.get("error") for m in manifest if not m.get("path")},
        },
        "facts": {"found": sum(f["status"] == "found" for f in facts), "total": len(facts), "coverage": coverage},
        "counts": {**counts, "export": counts["chunks"], "export_bytes": export_bytes},
    }
    settings.paths.build_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def quick_query(text: str, k: int = 5) -> None:
    import chromadb

    from fundfacts.embed import get_embedder

    col = chromadb.PersistentClient(path=str(settings.paths.chroma)).get_collection(settings.vector_db.collection)
    q = get_embedder().encode([text])[0].tolist()
    res = col.query(query_embeddings=[q], n_results=k, include=["metadatas", "distances"])
    for cid, meta, dist in zip(res["ids"][0], res["metadatas"][0], res["distances"][0]):
        print(f"  {1 - dist:.3f}  {cid:<62} {meta['url'][:60]}")


def run() -> dict:
    chunks, vectors, emb = load_inputs()
    col = store(chunks, vectors, emb["model"])
    counts = verify(col, chunks, vectors)
    size = export(chunks, vectors, emb["model"])
    report = build_report(counts, size)
    print(f"[store] chroma '{settings.vector_db.collection}': {counts['chroma']} vectors "
          f"(chunks {counts['chunks']}, missing ids {len(counts['missing_ids'])}, "
          f"vector spot-check max diff {counts['vector_max_abs_diff']:.1e})")
    print(f"[store] exported {counts['chunks']} vectors -> {settings.paths.index_export} ({size / 1e6:.1f} MB)")
    print(f"[store] facts {report['facts']['found']}/{report['facts']['total']} found; "
          f"build report -> {settings.paths.build_report}")
    return report


def main(argv: list[str]) -> None:
    if "--query" in argv:
        quick_query(" ".join(argv[argv.index("--query") + 1:]))
        return
    run()


if __name__ == "__main__":
    main(sys.argv[1:])
