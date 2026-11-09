import pytest

from docs_rag_eval.db import IndexMetadata, IndexMismatchError, SQLiteStore
from docs_rag_eval.models import Chunk
from docs_rag_eval.retrieve import retrieve


class FixedEmbedder:
    def __init__(
        self,
        vector: list[float],
        embedding_model: str = "test-embedding",
    ) -> None:
        self.vector = vector
        self.embedding_model = embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.vector]


def make_store(tmp_path, *, metadata: bool = True) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "rag.db")

    store.replace_document(
        "relevant.md",
        "hash-a",
        [Chunk(id="relevant", source="relevant.md", text="relevant")],
        [[1.0, 0.0]],
    )
    store.replace_document(
        "irrelevant.md",
        "hash-b",
        [Chunk(id="irrelevant", source="irrelevant.md", text="irrelevant")],
        [[0.0, 1.0]],
    )

    if metadata:
        store.set_index_metadata(IndexMetadata("test-embedding", 2))

    return store


def test_retrieve_filters_chunks_below_min_score(tmp_path):
    results = retrieve(
        question="question",
        embedder=FixedEmbedder([1.0, 0.0]),
        sqlite_store=make_store(tmp_path),
        top_k=5,
        min_score=0.5,
    )

    assert [item.chunk.id for item in results] == ["relevant"]


def test_retrieve_respects_top_k(tmp_path):
    results = retrieve(
        question="question",
        embedder=FixedEmbedder([1.0, 0.0]),
        sqlite_store=make_store(tmp_path),
        top_k=1,
        min_score=-1.0,
    )

    assert [item.chunk.id for item in results] == ["relevant"]


def test_retrieve_returns_empty_list_when_index_is_empty(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")

    results = retrieve(
        question="question",
        embedder=FixedEmbedder([1.0, 0.0]),
        sqlite_store=store,
        top_k=5,
        min_score=0.5,
    )

    assert results == []


def test_retrieve_rejects_blank_question(tmp_path):
    with pytest.raises(ValueError):
        retrieve(
            question=" ",
            embedder=FixedEmbedder([1.0, 0.0]),
            sqlite_store=make_store(tmp_path),
            min_score=0.0,
            top_k=3,
        )


@pytest.mark.parametrize(
    ("top_k", "min_score"),
    [
        (0, 0.0),
        (-1, 0.0),
        (True, 0.0),
        (5, 1.5),
        (5, -1.5),
        (5, float("nan")),
        (5, float("inf")),
        (5, float("-inf")),
    ],
)
def test_retrieve_rejects_invalid_arguments(tmp_path, top_k, min_score):
    with pytest.raises(ValueError):
        retrieve(
            question="question",
            embedder=FixedEmbedder([1.0, 0.0]),
            sqlite_store=make_store(tmp_path),
            top_k=top_k,
            min_score=min_score,
        )


def test_retrieve_rejects_index_without_metadata(tmp_path):
    with pytest.raises(IndexMismatchError, match="metadata"):
        retrieve(
            question="question",
            embedder=FixedEmbedder([1.0, 0.0]),
            sqlite_store=make_store(tmp_path, metadata=False),
            top_k=5,
            min_score=0.5,
        )


def test_retrieve_rejects_different_embedding_model(tmp_path):
    with pytest.raises(IndexMismatchError, match="other-embedding"):
        retrieve(
            question="question",
            embedder=FixedEmbedder(
                [1.0, 0.0],
                embedding_model="other-embedding",
            ),
            sqlite_store=make_store(tmp_path),
            top_k=5,
            min_score=0.5,
        )


def test_retrieve_rejects_dimension_mismatch(tmp_path):
    with pytest.raises(IndexMismatchError, match="dimension"):
        retrieve(
            question="question",
            embedder=FixedEmbedder([1.0, 0.0, 0.0]),
            sqlite_store=make_store(tmp_path),
            top_k=5,
            min_score=0.5,
        )


@pytest.mark.parametrize(
    "embeddings",
    [
        [],
        [[1.0, 0.0], [0.0, 1.0]],
    ],
)
def test_retrieve_rejects_invalid_query_embedding_count(tmp_path, embeddings):
    class BrokenEmbedder:
        embedding_model = "test-embedding"

        def embed(self, texts: list[str]) -> list[list[float]]:
            return embeddings

    with pytest.raises(ValueError):
        retrieve(
            question="question",
            embedder=BrokenEmbedder(),
            sqlite_store=make_store(tmp_path),
            top_k=5,
            min_score=0.5,
        )
