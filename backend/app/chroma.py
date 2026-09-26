import os
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.settings import get_settings


def get_chroma_client() -> chromadb.PersistentClient:
    settings = get_settings()
    persist_dir = settings.chroma_persist_directory or "./chroma_data"
    os.environ.setdefault("CHROMA_PERSIST_DIRECTORY", persist_dir)
    return chromadb.PersistentClient(path=persist_dir)


def get_or_create_collection(name: str, embedding_function=None):
    client = get_chroma_client()
    # ChromaDB 1.x uses get_or_create_collection; fall back to manual check if needed.
    try:
        return client.get_or_create_collection(name, embedding_function=embedding_function)
    except TypeError:
        # Older API surface without embedding_function kwarg in get_or_create
        if client.get_collection(name):
            return client.get_collection(name)
        return client.create_collection(name, embedding_function=embedding_function)
