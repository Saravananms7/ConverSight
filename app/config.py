"""Application configuration and settings."""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    deepgram_api_key: str = ""
    google_api_key: str = ""  # For TTS + Gemini LLM (optional; else use service account)
    google_application_credentials: Optional[str] = None  # Service account JSON path for TTS
    api_secret_key: Optional[str] = None
    host: str = "0.0.0.0"
    port: int = 8000

    # Whisper (OpenAI API)
    openai_api_key: str = ""

    # Policy embeddings: local file storage
    policy_storage_path: str = "data/policy_embeddings.json"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
