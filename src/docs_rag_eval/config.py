"""Runtime configuration loaded from environment variables and `.env`."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/docs_rag_eval/config.py -> repository root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings. Defaults target a local Ollama instance.

    Each field is read from the environment variable of the same name
    (``llm_base_url`` <- ``LLM_BASE_URL``), then from ``.env``.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_timeout_seconds: float = Field(default=120.0, gt=0, allow_inf_nan=False)
    # "none" disables thinking on reasoning models; empty omits the parameter.
    llm_reasoning_effort: str = "none"
    min_relevance_score: float = Field(default=0.5, ge=-1.0, le=1.0)

    embedding_model: str = "nomic-embed-text"
    chat_model: str = "qwen3.5:9b"
    corpus_dir: Path = PROJECT_ROOT / "corpus"
    database_path: Path = PROJECT_ROOT / "data" / "rag.db"

    @field_validator("corpus_dir", "database_path")
    @classmethod
    def _resolve_from_project_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value


settings = Settings()
