from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ---- AI Provider ----
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    # ---- Demo mode ----
    demo_mode: bool = False

    # ---- Vector database ----
    chroma_persist_directory: str = "./chroma_data"

    # ---- Application database ----
    database_url: str = "sqlite+aiosqlite:///./solvia_dev.db"

    # ---- Server ----
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def gemini_available(self) -> bool:
        return bool(self.gemini_api_key and not self.demo_mode)


@lru_cache
def get_settings() -> Settings:
    return Settings()
