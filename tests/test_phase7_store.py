"""Phase 7: ChromaDB store, export parity and build report."""
import base64
import json

import numpy as np
import pytest

from fundfacts.config import settings
from fundfacts.ingest.store import _meta

built = pytest.mark.skipif(not settings.paths.index_export.exists(), reason="run `python -m fundfacts.ingest.store` first")


def test_meta_has_no_none_values():
    m = _meta({"source_id": "x", "scheme_id": None, "page": 3, "doc_date": None})
    assert m["scheme_id"] == "" and m["doc_date"] == "" and m["page"] == 3
    assert all(v is not None for v in m.values())


@pytest.fixture(scope="module")
def export():
    data = json.loads(settings.paths.index_export.read_text(encoding="utf-8"))
    vecs = np.frombuffer(base64.b64decode(data["vectors_b64"]), dtype="<f4").reshape(data["count"], data["dim"])
    return data, vecs


@built
def test_export_matches_embeddings(export):
    data, vecs = export
    emb = json.loads((settings.paths.embeddings / "embeddings.json").read_text())
    assert [c["chunk_id"] for c in data["chunks"]] == [i["chunk_id"] for i in emb["items"]]
    ref = np.asarray([i["vector"] for i in emb["items"]], dtype=np.float32)
    assert np.abs(vecs - ref).max() < 1e-6


@built
def test_chroma_matches_export(export):
    chromadb = pytest.importorskip("chromadb")
    data, vecs = export
    col = chromadb.PersistentClient(path=str(settings.paths.chroma)).get_collection(settings.vector_db.collection)
    assert col.count() == data["count"]
    # the same query vector gives the same top result in ChromaDB and in the export
    q = vecs[[c["chunk_id"] for c in data["chunks"]].index("hdfc_small_cap_sid::p5::fact_hdfc_small_cap_exit_load")]
    top_export = data["chunks"][int(np.argmax(vecs @ q))]["chunk_id"]
    top_chroma = col.query(query_embeddings=[q.tolist()], n_results=1)["ids"][0][0]
    assert top_export == top_chroma == "hdfc_small_cap_sid::p5::fact_hdfc_small_cap_exit_load"


@built
def test_scheme_filter_in_chroma(export):
    chromadb = pytest.importorskip("chromadb")
    data, vecs = export
    col = chromadb.PersistentClient(path=str(settings.paths.chroma)).get_collection(settings.vector_db.collection)
    res = col.query(query_embeddings=[vecs[0].tolist()], n_results=5, where={"scheme_id": "hdfc_elss"})
    assert res["ids"][0] and all(m["scheme_id"] == "hdfc_elss" for m in res["metadatas"][0])


@built
def test_build_report_counts_agree():
    r = json.loads(settings.paths.build_report.read_text())
    c = r["counts"]
    assert c["chunks"] == c["chroma"] == c["export"] and not c["missing_ids"]
    assert r["facts"]["total"] == 50
