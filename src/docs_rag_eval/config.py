"""Runtime configuration loaded from environment variables and `.env`."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/docs_rag_eval/config.py -> repository root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from the process environment or local `.env`.

    Environment variables take precedence over values in `.env`. The tracked
    `.env.example` is a template and is never loaded automatically.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str
    llm_api_key: str
    llm_timeout_seconds: float = Field(gt=0, allow_inf_nan=False)
    llm_reasoning_effort: str
    min_relevance_score: float = Field(ge=-1.0, le=1.0)
    embedding_model: str
    chat_model: str
    judge_model: str
    corpus_dir: Path
    database_path: Path
    evaluation_dataset: Path
    evaluation_reports: Path
    evaluation_top_k: int = Field(gt=0, le=20)
    api_host: str
    api_port: int = Field(gt=0, le=65535)

    @field_validator(
        "corpus_dir",
        "database_path",
        "evaluation_dataset",
        "evaluation_reports",
    )
    @classmethod
    def _resolve_from_project_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value


settings = Settings()
