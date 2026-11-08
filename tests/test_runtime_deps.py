"""Serverless-runtime check: the API must work with ONLY requirements.txt installed.

Runs a child Python process in which every ingestion-only library is blocked (as on Vercel),
then imports the API and answers questions through it. This catches imports like the
pypdf one that broke the first deployment.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fundfacts.config import settings

ROOT = Path(__file__).resolve().parents[1]
INGEST_ONLY = ["pypdf", "pdfplumber", "bs4", "lxml", "requests", "chromadb", "sentence_transformers", "torch", "fontTools"]

CHILD = f"""
import sys, json
for m in {INGEST_ONLY!r}:
    sys.modules[m] = None          # any 'import m' now raises ImportError, like on Vercel
sys.path.insert(0, {str(ROOT)!r})
from fastapi.testclient import TestClient
from api.index import app
c = TestClient(app, raise_server_exceptions=False)
out = {{}}
out["health"] = c.get("/api/index?__route=health").status_code
out["pii"] = c.post("/api/index?__route=chat", json={{"message": "My PAN is ABCDE1234F"}}).json().get("type")
out["fact"] = c.post("/api/index?__route=chat", json={{"message": "Exit load of HDFC Small Cap Fund?"}}).json().get("type")
out["rag"] = c.post("/api/index?__route=chat", json={{"message": "What is NAV?"}}).json().get("type")
print("RESULT" + json.dumps(out))
"""


@pytest.mark.slow
@pytest.mark.skipif(not settings.paths.index_export.exists(), reason="run the ingestion pipeline first")
def test_api_runs_with_runtime_requirements_only():
    env = {**os.environ, "EMBEDDING_BACKEND": "onnx", "VECTOR_DB": "json", "LLM_PROVIDER": "none", "VERCEL": "1"}
    p = subprocess.run([sys.executable, "-c", CHILD], capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=600)
    line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT")), None)
    assert line, f"child failed:\n{p.stderr[-3000:]}"
    out = json.loads(line[len("RESULT"):])
    assert out == {"health": 200, "pii": "refusal_pii", "fact": "answer", "rag": "answer"}, (out, p.stderr[-2000:])
