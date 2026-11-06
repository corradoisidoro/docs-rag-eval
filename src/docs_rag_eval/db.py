"""SQLite persistence and in-Python cosine-similarity search."""

import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from docs_rag_eval.models import Chunk, RetrievedChunk


@dataclass(frozen=True)
class DocumentWrite:
    """A document revision to store together with its chunk embeddings."""

    source: str
    content_hash: str
    chunks: list[Chunk]
    embeddings: list[list[float]]


@dataclass(frozen=True)
class IndexMetadata:
    """The embedding model and vector size used to build the index."""

    embedding_model: str
    embedding_dimension: int

    def __post_init__(self) -> None:
        if self.embedding_dimension < 1:
            raise ValueError("embedding_dimension must be positive")


class IndexMismatchError(RuntimeError):
    """The stored index is incompatible with the configured embedding model."""


class SQLiteStore:
    """Store documents, chunks, and embeddings in SQLite.

    Embeddings are stored as JSON and compared in Python. This is simple
    and sufficient for a small corpus.
    """

    def __init__(self, database_path: str | Path = "data/rag.db") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a connection, commit on success, and always close it."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    source TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    indexed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    FOREIGN KEY (source)
                        REFERENCES documents(source)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS index_metadata (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    embedding_model TEXT NOT NULL,
                    embedding_dimension INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def list_sources(self) -> list[str]:
        """Return the source of every indexed document."""
        with self._connect() as connection:
            rows = connection.execute("SELECT source FROM documents").fetchall()
        return [row["source"] for row in rows]

    def get_content_hash(self, source: str) -> str | None:
        """Return the hash stored when the source was indexed, if any."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT content_hash FROM documents WHERE source = ?",
                (source,),
            ).fetchone()
        return row["content_hash"] if row else None

    def get_index_metadata(self) -> IndexMetadata | None:
        """Return the embedding model and dimension recorded for the index."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT embedding_model, embedding_dimension
                FROM index_metadata
                WHERE id = 1
                """
            ).fetchone()

        if row is None:
            return None

        return IndexMetadata(
            embedding_model=row["embedding_model"],
            embedding_dimension=row["embedding_dimension"],
        )

    def set_index_metadata(self, metadata: IndexMetadata) -> None:
        """Record the embedding model and dimension used by the index."""
        with self._connect() as connection:
            _set_index_metadata(connection, metadata)

    def has_chunks(self) -> bool:
        """Return whether the index contains any chunks."""
        with self._connect() as connection:
            row = connection.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
        return row is not None

    def stored_embedding_dimensions(self) -> set[int]:
        """Return the distinct embedding dimensions currently stored."""
        with self._connect() as connection:
            rows = connection.execute("SELECT embedding FROM chunks").fetchall()
        return {len(json.loads(row["embedding"])) for row in rows}

    def replace_document(
        self,
        source: str,
        content_hash: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """Save a document and atomically replace its chunks and embeddings."""
        with self._connect() as connection:
            _replace_document(connection, source, content_hash, chunks, embeddings)

    def delete_document(self, source: str) -> None:
        """Delete a document; its chunks go with it via ON DELETE CASCADE."""
        with self._connect() as connection:
            _delete_document(connection, source)

    def apply_changes(
        self,
        *,
        deletions: list[str],
        writes: list[DocumentWrite],
        metadata: IndexMetadata | None = None,
    ) -> None:
        """Apply all deletions, writes, and metadata in a single transaction.

        Any failure rolls back every change, so the index never keeps a
        partially applied corpus update.
        """
        with self._connect() as connection:
            for source in deletions:
                _delete_document(connection, source)
            for write in writes:
                _replace_document(
                    connection,
                    write.source,
                    write.content_hash,
                    write.chunks,
                    write.embeddings,
                )
            if metadata is not None:
                _set_index_metadata(connection, metadata)

    def search(self, embedding: list[float], top_k: int = 5) -> list[RetrievedChunk]:
        """Return the top-k chunks by cosine similarity."""
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, source, text, embedding FROM chunks"
            ).fetchall()

        results = []
        for row in rows:
            stored = json.loads(row["embedding"])
            if len(stored) != len(embedding):
                raise IndexMismatchError(
                    f"Stored embedding dimension {len(stored)} does not match "
                    f"query dimension {len(embedding)}; run POST /ingest to rebuild "
                    "the index."
                )
            chunk = Chunk(id=row["id"], source=row["source"], text=row["text"])
            results.append(
                RetrievedChunk(chunk=chunk, score=_cosine_similarity(embedding, stored))
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]


def _replace_document(
    connection: sqlite3.Connection,
    source: str,
    content_hash: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> None:
    """Replace a document's chunks and embeddings on an open connection."""
    indexed_at = datetime.now(UTC).isoformat()

    connection.execute(
        """
        INSERT INTO documents (source, content_hash, indexed_at)
        VALUES (?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
            content_hash = excluded.content_hash,
            indexed_at = excluded.indexed_at
        """,
        (source, content_hash, indexed_at),
    )
    connection.execute("DELETE FROM chunks WHERE source = ?", (source,))
    connection.executemany(
        "INSERT INTO chunks (id, source, text, embedding) VALUES (?, ?, ?, ?)",
        [
            (chunk.id, chunk.source, chunk.text, json.dumps(embedding))
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ],
    )


def _delete_document(connection: sqlite3.Connection, source: str) -> None:
    """Delete a document on an open connection; chunks cascade."""
    connection.execute("DELETE FROM documents WHERE source = ?", (source,))


def _set_index_metadata(
    connection: sqlite3.Connection,
    metadata: IndexMetadata,
) -> None:
    """Record index metadata on an open connection."""
    connection.execute(
        """
        INSERT INTO index_metadata (
            id, embedding_model, embedding_dimension, updated_at
        )
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            embedding_model = excluded.embedding_model,
            embedding_dimension = excluded.embedding_dimension,
            updated_at = excluded.updated_at
        """,
        (
            metadata.embedding_model,
            metadata.embedding_dimension,
            datetime.now(UTC).isoformat(),
        ),
    )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity, or 0.0 if either vector is all zeros."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)
