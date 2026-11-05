from math import isfinite

from docs_rag_eval.db import IndexMismatchError, SQLiteStore
from docs_rag_eval.llm import Embedder
from docs_rag_eval.models import RetrievedChunk


def retrieve(
    question: str,
    embedder: Embedder,
    sqlite_store: SQLiteStore,
    *,
    min_score: float,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Return the top-k chunks whose similarity is at least ``min_score``."""
    if not question.strip():
        raise ValueError("Question must not be blank")

    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")

    if not isfinite(min_score) or not -1.0 <= min_score <= 1.0:
        raise ValueError("min_score must be between -1.0 and 1.0")

    has_chunks = sqlite_store.has_chunks()
    metadata = sqlite_store.get_index_metadata()
    embedding_model = embedder.embedding_model

    if has_chunks:
        if metadata is None:
            raise IndexMismatchError(
                "Index metadata is missing; run POST /ingest to rebuild the index."
            )
        if metadata.embedding_model != embedding_model:
            raise IndexMismatchError(
                f"Index was built with embedding model "
                f"'{metadata.embedding_model}', but '{embedding_model}' is "
                "configured; run POST /ingest to rebuild the index."
            )

    embeddings = embedder.embed([question])

    if len(embeddings) != 1:
        raise ValueError("Expected exactly one query embedding")

    query_embedding = embeddings[0]

    if (
        has_chunks
        and metadata is not None
        and len(query_embedding) != metadata.embedding_dimension
    ):
        raise IndexMismatchError(
            f"Stored embeddings have dimension {metadata.embedding_dimension}, "
            f"but the configured model produces dimension {len(query_embedding)}; "
            "run POST /ingest to rebuild the index."
        )

    results = sqlite_store.search(query_embedding, top_k)

    return [item for item in results if item.score >= min_score]
