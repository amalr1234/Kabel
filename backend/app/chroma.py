from functools import lru_cache

import chromadb

from app.settings import get_settings


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.ClientAPI:
    persist_dir = get_settings().chroma_persist_directory or "./chroma_data"
    return chromadb.PersistentClient(path=persist_dir)


def get_or_create_collection(name: str, embedding_function=None):
    return get_chroma_client().get_or_create_collection(name, embedding_function=embedding_function)
