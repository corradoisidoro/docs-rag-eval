import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from docs_rag_eval.db import SQLiteStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.update(
    {
        "LLM_BASE_URL": "https://provider.invalid/v1",
        "LLM_API_KEY": "test-key",
        "LLM_TIMEOUT_SECONDS": "1",
        "LLM_REASONING_EFFORT": "",
        "MIN_RELEVANCE_SCORE": "0.375",
        "EMBEDDING_MODEL": "test-embedding-model",
        "CHAT_MODEL": "test-chat-model",
        "JUDGE_MODEL": "test-judge-model",
        "CORPUS_DIR": str(PROJECT_ROOT / "tests"),
        "DATABASE_PATH": str(PROJECT_ROOT / "tests" / "test-rag.db"),
        "EVALUATION_REPORTS": str(PROJECT_ROOT / "tests" / "evaluation-reports"),
        "EVALUATION_TOP_K": "3",
        "API_HOST": "127.0.0.2",
        "API_PORT": "8765",
    }
)
if (PROJECT_ROOT / ".env").is_file():
    os.environ.pop("EVALUATION_DATASET", None)
else:
    os.environ["EVALUATION_DATASET"] = str(PROJECT_ROOT / "tests")


@pytest.fixture
def stored_chunk_ids():
    """Return a function that lists every chunk id stored in a SQLiteStore."""

    def read(store: SQLiteStore) -> list[str]:
        with closing(sqlite3.connect(store.database_path)) as connection:
            rows = connection.execute("SELECT id FROM chunks ORDER BY id").fetchall()
        return [row[0] for row in rows]

    return read
