"""Embedding model: sentence-transformers/all-MiniLM-L6-v2 (384-d, L2-normalised).

Two interchangeable backends that produce the same vectors:
- "sentence-transformers": PyTorch; used for ingestion and local runs.
- "onnx": the same model's official ONNX export (from its Hugging Face repo) run with
  onnxruntime + tokenizers. Used on Vercel, where PyTorch does not fit in a function.
  Mean pooling + L2 normalisation reproduce the sentence-transformers pipeline exactly.

`embedding.backend: auto` picks sentence-transformers when installed, else ONNX.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from fundfacts.config import ROOT, settings

HF_FILE = "https://huggingface.co/{repo}/resolve/main/{file}"
ONNX_FILES = {"onnx/model.onnx": "model.onnx", "tokenizer.json": "tokenizer.json"}


def onnx_cache_dir() -> Path:
    if os.getenv("ONNX_MODEL_DIR"):
        return Path(os.environ["ONNX_MODEL_DIR"])
    # serverless functions can only write to /tmp
    return Path("/tmp/minilm") if os.getenv("VERCEL") or os.name != "nt" else ROOT / ".cache" / "minilm"


class SentenceTransformerEmbedder:
    backend = "sentence-transformers"

    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model, device="cpu")
        self.max_tokens = self.model.max_seq_length

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        vecs = self.model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


class OnnxEmbedder:
    backend = "onnx"

    def __init__(self, model: str, cache: Path | None = None):
        import httpx
        import onnxruntime as ort
        from tokenizers import Tokenizer

        cache = cache or onnx_cache_dir()
        cache.mkdir(parents=True, exist_ok=True)
        for remote, local in ONNX_FILES.items():
            target = cache / local
            if target.exists():
                continue
            tmp = target.with_suffix(".part")
            with httpx.stream("GET", HF_FILE.format(repo=model, file=remote), follow_redirects=True, timeout=120) as r:
                r.raise_for_status()
                with open(tmp, "wb") as fh:
                    for block in r.iter_bytes():
                        fh.write(block)
            tmp.replace(target)
        self.max_tokens = 256  # same truncation as sentence-transformers for this model
        self.tokenizer = Tokenizer.from_file(str(cache / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=self.max_tokens)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(cache / "model.onnx"), opts, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.session.get_inputs()}

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        out = []
        for i in range(0, len(texts), batch_size):
            enc = self.tokenizer.encode_batch(texts[i:i + batch_size])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self.session.run(None, feed)[0]                       # (batch, tokens, 384)
            m = mask[..., None].astype(np.float32)
            pooled = (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)  # mean pooling
            out.append(pooled / np.linalg.norm(pooled, axis=1, keepdims=True))
        return np.vstack(out).astype(np.float32)


@lru_cache(maxsize=1)
def get_embedder():
    backend, model = settings.embedding.backend, settings.embedding.model
    if backend in ("auto", "sentence-transformers"):
        try:
            return SentenceTransformerEmbedder(model)
        except ImportError:
            if backend == "sentence-transformers":
                raise
    return OnnxEmbedder(model)
