"""Phase 6: embeddings file integrity and ONNX / sentence-transformers parity."""
import json

import numpy as np
import pytest

from fundfacts.config import settings
from fundfacts.ingest.embed import embed_text

EMB = settings.paths.embeddings / "embeddings.json"
needs = pytest.mark.skipif(not EMB.exists(), reason="run `python -m fundfacts.ingest.embed` first")


def test_embed_text_prefixes_title_except_fact_cards():
    assert embed_text({"kind": "fact_card", "text": "HDFC Mid Cap Fund - Exit load", "title": "SID"}) == "HDFC Mid Cap Fund - Exit load"
    assert embed_text({"kind": "pdf", "text": "Exit Load: Nil", "title": "SID - HDFC ELSS"}) == "SID - HDFC ELSS. Exit Load: Nil"


@needs
def test_one_normalised_384d_vector_per_chunk():
    emb = json.loads(EMB.read_text())
    chunks = json.loads((settings.paths.chunks / "chunks.json").read_text(encoding="utf-8"))
    assert emb["model"] == settings.embedding.model and emb["dim"] == 384
    assert [i["chunk_id"] for i in emb["items"]] == [c["chunk_id"] for c in chunks]
    m = np.array([i["vector"] for i in emb["items"]], dtype=np.float32)
    assert m.shape == (len(chunks), 384)
    assert np.allclose(np.linalg.norm(m, axis=1), 1.0, atol=1e-3)


@pytest.mark.slow
def test_onnx_matches_sentence_transformers():
    """The Vercel runtime (ONNX) must produce the same vectors as ingestion (PyTorch)."""
    st = pytest.importorskip("sentence_transformers")  # noqa: F841
    from fundfacts.embed import OnnxEmbedder, SentenceTransformerEmbedder

    texts = ["What is the exit load of HDFC Mid Cap Fund?", "ELSS lock-in period",
             "HDFC Small Cap Fund (Direct Plan - Growth Option) - Benchmark index: BSE 250 SmallCap Index (TRI)."]
    a = SentenceTransformerEmbedder(settings.embedding.model).encode(texts)
    b = OnnxEmbedder(settings.embedding.model).encode(texts)
    assert np.all((a * b).sum(axis=1) >= 0.9999)
