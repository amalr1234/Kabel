"""Gemini embeddings shared by ingestion (Chroma) and query-time retrieval."""
from __future__ import annotations

import hashlib

from chromadb import Documents, EmbeddingFunction, Embeddings

from app.gemini import get_genai_client, settings

# Chroma collections were created with 1536-dim vectors; every embedding must match.
EMBEDDING_DIMS = 1536


def demo_embedding(text: str) -> list[float]:
    """Deterministic hash-based placeholder used without Gemini (not semantic)."""
    digest = hashlib.sha256((text or "").encode("utf-8")).digest()
    return [digest[i % len(digest)] / 255.0 for i in range(EMBEDDING_DIMS)]


def _fit_dims(vec: list[float]) -> list[float]:
    if len(vec) >= EMBEDDING_DIMS:
        return vec[:EMBEDDING_DIMS]
    return vec + [0.0] * (EMBEDDING_DIMS - len(vec))


def embed_text(text: str) -> list[float]:
    client = get_genai_client()
    if client is None:
        return demo_embedding(text)
    try:
        emb = client.models.embed_content(model=settings.gemini_embedding_model, contents=[text])
        vec = list(emb.embeddings[0].values) if emb.embeddings else []
    except Exception:
        vec = []
    return _fit_dims(vec) if vec else demo_embedding(text)


class GeminiEmbeddingFunction(EmbeddingFunction[Documents]):
    """ChromaDB embedding function backed by :func:`embed_text`."""

    # Chroma warns when an embedding function does not define __init__.
    def __init__(self) -> None:
        super().__init__()

    def __call__(self, input: Documents) -> Embeddings:
        texts = [input] if isinstance(input, str) else list(input)
        return [embed_text(text) for text in texts]

    def __repr__(self) -> str:
        return f"GeminiEmbeddingFunction(model={settings.gemini_embedding_model!r})"
