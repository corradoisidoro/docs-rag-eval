import pytest

from docs_rag_eval.db import (
    DocumentWrite,
    IndexMetadata,
    IndexMismatchError,
    SQLiteStore,
)
from docs_rag_eval.models import Chunk


def make_chunk(
    chunk_id: str,
    text: str | None = None,
    source: str = "doc.md",
) -> Chunk:
    return Chunk(
        id=chunk_id,
        source=source,
        text=chunk_id if text is None else text,
    )


def test_search_returns_top_k_sorted(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")

    store.replace_document(
        source="doc.md",
        content_hash="hash",
        chunks=[make_chunk("a"), make_chunk("b"), make_chunk("c")],
        embeddings=[[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]],
    )

    results = store.search([1.0, 0.0], top_k=2)

    assert [item.chunk.id for item in results] == ["a", "b"]
    assert results[0].score >= results[1].score


def test_search_on_empty_store_returns_empty_list(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")

    assert store.search([1.0, 0.0]) == []


def test_search_scores_zero_vectors_as_zero(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    store.replace_document("doc.md", "hash", [make_chunk("a")], [[0.0, 0.0]])

    [result] = store.search([1.0, 0.0])

    assert result.score == 0.0


def test_search_rejects_embeddings_with_wrong_dimension(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")

    store.replace_document(
        "a.md",
        "hash-a",
        [make_chunk("a", source="a.md")],
        [[1.0, 0.0]],
    )
    store.replace_document(
        "b.md",
        "hash-b",
        [make_chunk("b", source="b.md")],
        [[1.0, 0.0, 0.0]],
    )

    with pytest.raises(IndexMismatchError, match="dimension"):
        store.search([1.0, 0.0], top_k=5)


def test_replace_document_removes_stale_chunks(tmp_path, stored_chunk_ids):
    store = SQLiteStore(tmp_path / "rag.db")

    store.replace_document("doc.md", "old", [make_chunk("old")], [[1.0]])
    store.replace_document("doc.md", "new", [make_chunk("new")], [[1.0]])

    assert stored_chunk_ids(store) == ["new"]
    assert store.get_content_hash("doc.md") == "new"


def test_get_content_hash_is_none_for_unknown_source(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")

    assert store.get_content_hash("missing.md") is None


def test_list_sources_returns_indexed_documents(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    store.replace_document("a.md", "h", [make_chunk("a", source="a.md")], [[1.0]])
    store.replace_document("b.md", "h", [], [])

    assert sorted(store.list_sources()) == ["a.md", "b.md"]


def test_delete_document_cascades_to_chunks(tmp_path, stored_chunk_ids):
    store = SQLiteStore(tmp_path / "rag.db")
    store.replace_document("a.md", "h", [make_chunk("a", source="a.md")], [[1.0]])
    store.replace_document("b.md", "h", [make_chunk("b", source="b.md")], [[1.0]])

    store.delete_document("a.md")

    assert store.list_sources() == ["b.md"]
    assert stored_chunk_ids(store) == ["b"]


def test_apply_changes_deletes_and_replaces_documents(tmp_path, stored_chunk_ids):
    store = SQLiteStore(tmp_path / "rag.db")
    store.replace_document("a.md", "old-a", [make_chunk("a", source="a.md")], [[1.0]])
    store.replace_document("b.md", "hash-b", [make_chunk("b", source="b.md")], [[1.0]])

    store.apply_changes(
        deletions=["b.md"],
        writes=[
            DocumentWrite(
                source="a.md",
                content_hash="new-a",
                chunks=[make_chunk("a-new", source="a.md")],
                embeddings=[[0.5, 0.5]],
            )
        ],
    )

    assert store.list_sources() == ["a.md"]
    assert store.get_content_hash("a.md") == "new-a"
    assert stored_chunk_ids(store) == ["a-new"]


def test_apply_changes_rolls_back_when_a_write_fails(tmp_path, stored_chunk_ids):
    store = SQLiteStore(tmp_path / "rag.db")
    store.replace_document("a.md", "hash-a", [make_chunk("a", source="a.md")], [[1.0]])
    store.replace_document("b.md", "hash-b", [make_chunk("b", source="b.md")], [[1.0]])

    good_write = DocumentWrite(
        source="a.md",
        content_hash="new-a",
        chunks=[make_chunk("a-new", source="a.md")],
        embeddings=[[0.5, 0.5]],
    )
    bad_write = DocumentWrite(
        source="c.md",
        content_hash="h",
        chunks=[make_chunk("c", source="c.md")],
        embeddings=[],
    )

    with pytest.raises(ValueError):
        store.apply_changes(deletions=["b.md"], writes=[good_write, bad_write])

    assert sorted(store.list_sources()) == ["a.md", "b.md"]
    assert store.get_content_hash("a.md") == "hash-a"
    assert store.get_content_hash("b.md") == "hash-b"
    assert stored_chunk_ids(store) == ["a", "b"]


def test_set_and_get_index_metadata(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    metadata = IndexMetadata("test-embedding", 3)

    store.set_index_metadata(metadata)

    assert store.get_index_metadata() == metadata


def test_index_metadata_is_none_for_a_new_store(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")

    assert store.get_index_metadata() is None


@pytest.mark.parametrize("dimension", [0, -1])
def test_index_metadata_rejects_non_positive_dimension(dimension):
    with pytest.raises(ValueError):
        IndexMetadata("test-embedding", dimension)


def test_has_chunks_reports_whether_any_chunks_exist(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")

    assert store.has_chunks() is False

    store.replace_document("a.md", "h", [make_chunk("a", source="a.md")], [[1.0]])

    assert store.has_chunks() is True


def test_stored_embedding_dimensions(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")

    assert store.stored_embedding_dimensions() == set()

    store.replace_document(
        "a.md",
        "hash-a",
        [make_chunk("a", source="a.md")],
        [[1.0, 0.0]],
    )
    store.replace_document(
        "b.md",
        "hash-b",
        [make_chunk("b", source="b.md")],
        [[1.0, 0.0, 0.0]],
    )

    assert store.stored_embedding_dimensions() == {2, 3}


def test_apply_changes_writes_metadata(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    metadata = IndexMetadata("test-embedding", 2)

    store.apply_changes(
        deletions=[],
        writes=[
            DocumentWrite(
                source="a.md",
                content_hash="h",
                chunks=[make_chunk("a", source="a.md")],
                embeddings=[[1.0, 0.0]],
            )
        ],
        metadata=metadata,
    )

    assert store.get_index_metadata() == metadata


def test_apply_changes_does_not_write_metadata_when_a_write_fails(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    bad_write = DocumentWrite(
        source="a.md",
        content_hash="h",
        chunks=[make_chunk("a", source="a.md")],
        embeddings=[],
    )

    with pytest.raises(ValueError):
        store.apply_changes(
            deletions=[],
            writes=[bad_write],
            metadata=IndexMetadata("test-embedding", 2),
        )

    assert store.get_index_metadata() is None


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5])
def test_search_rejects_invalid_top_k(tmp_path, top_k):
    store = SQLiteStore(tmp_path / "rag.db")

    with pytest.raises(ValueError, match="top_k"):
        store.search([1.0, 0.0], top_k=top_k)
