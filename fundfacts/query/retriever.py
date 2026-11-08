"""Step 3b - Retrieval with the same embedding model and the same vectors as ingestion.

Backends (config `vector_db.backend`):
- chroma : query the persistent ChromaDB collection (local runs)
- json   : cosine search over vector_store/index.json, the exact export of that collection (Vercel)
- auto   : chroma if chromadb is installed and the store exists, else json

Re-ranking is small, explicit and recorded on every hit (`adjustments`):
  +scheme_boost  chunk belongs to the scheme named in the question
  -scheme_boost  chunk belongs to a *different* in-scope scheme
  +phrase_bonus  per exact query bigram found in the chunk (capped)
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from fundfacts.config import settings
from fundfacts.embed import get_embedder

STOP = set("the a an of is are what whats how to for in on and or do does i my me can be it this that with "
           "hdfc fund funds scheme plan direct growth please tell about".split())


@dataclass
class Hit:
    chunk_id: str
    text: str
    meta: dict
    score: float                       # cosine similarity
    adjustments: dict[str, float] = field(default_factory=dict)

    @property
    def final(self) -> float:
        return self.score + sum(self.adjustments.values())


class JsonStore:
    name = "json-export"

    def __init__(self):
        data = json.loads(settings.paths.index_export.read_text(encoding="utf-8"))
        self.chunks = data["chunks"]
        self.vectors = np.frombuffer(base64.b64decode(data["vectors_b64"]), dtype="<f4").reshape(data["count"], data["dim"])
        self.scheme = np.array([c["scheme_id"] for c in self.chunks])

    def search(self, q: np.ndarray, k: int, scheme_id: str | None = None) -> list[Hit]:
        scores = self.vectors @ q
        if scheme_id:
            scores = np.where(self.scheme == scheme_id, scores, -np.inf)
        idx = np.argsort(-scores)[:k]
        return [Hit(self.chunks[i]["chunk_id"], self.chunks[i]["text"], self.chunks[i], float(scores[i]))
                for i in idx if np.isfinite(scores[i])]


class ChromaStore:
    name = "chromadb"

    def __init__(self):
        import chromadb

        self.col = chromadb.PersistentClient(path=str(settings.paths.chroma)).get_collection(settings.vector_db.collection)

    def search(self, q: np.ndarray, k: int, scheme_id: str | None = None) -> list[Hit]:
        res = self.col.query(query_embeddings=[q.tolist()], n_results=k, where={"scheme_id": scheme_id} if scheme_id else None,
                             include=["documents", "metadatas", "distances"])
        return [Hit(cid, doc, {**meta, "chunk_id": cid}, 1.0 - dist)
                for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])]


@lru_cache(maxsize=1)
def get_store():
    backend = settings.vector_db.backend
    if backend in ("auto", "chroma"):
        try:
            if settings.paths.chroma.exists():
                return ChromaStore()
        except ImportError:
            if backend == "chroma":
                raise
    return JsonStore()


def _bigrams(text: str) -> set[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]
    return {f"{a} {b}" for a, b in zip(words, words[1:])}


def phrase_bonus(query: str, text: str) -> float:
    grams = _bigrams(query)
    flat = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    hits = sum(1 for g in grams if g in flat)
    return min(settings.retrieval.phrase_bonus_cap, settings.retrieval.phrase_bonus * hits)


def retrieve(query: str, scheme_id: str | None = None, k: int | None = None) -> list[Hit]:
    k = k or settings.retrieval.top_k
    r = settings.retrieval
    q = get_embedder().encode([query])[0]
    store = get_store()
    hits: dict[str, Hit] = {h.chunk_id: h for h in store.search(q, k * 3)}
    if scheme_id:  # make sure the named scheme's own chunks are candidates
        for h in store.search(q, k * 2, scheme_id=scheme_id):
            hits.setdefault(h.chunk_id, h)
    for h in hits.values():
        sid = h.meta.get("scheme_id") or None
        if scheme_id and sid == scheme_id:
            h.adjustments["scheme_match"] = r.scheme_boost
        elif scheme_id and sid and sid != scheme_id:
            h.adjustments["other_scheme"] = -r.scheme_boost
        pb = phrase_bonus(query, h.text)
        if pb:
            h.adjustments["phrase"] = round(pb, 3)
    return sorted(hits.values(), key=lambda h: -h.final)[:k]
