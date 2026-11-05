import sqlite3
from contextlib import closing

import pytest

from docs_rag_eval.db import SQLiteStore


@pytest.fixture
def stored_chunk_ids():
    """Return a function that lists every chunk id stored in a SQLiteStore."""

    def read(store: SQLiteStore) -> list[str]:
        with closing(sqlite3.connect(store.database_path)) as connection:
            rows = connection.execute("SELECT id FROM chunks ORDER BY id").fetchall()
        return [row[0] for row in rows]

    return read
