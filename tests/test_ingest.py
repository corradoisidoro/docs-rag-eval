import pytest

from docs_rag_eval.db import IndexMetadata, SQLiteStore
from docs_rag_eval.ingest import (
    DIMENSION_PROBE,
    EMBED_BATCH_SIZE,
    IngestResult,
    calculate_content_hash,
    chunk_document,
    ingest_documents,
    load_documents,
)
from docs_rag_eval.models import Chunk, Document


class FakeEmbedder:
    def __init__(self, embedding_model: str = "fake-embedding") -> None:
        self.embedding_model = embedding_model
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]


class WideEmbedder:
    embedding_model = "fake-embedding"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 1.0, 1.0] for _ in texts]


def make_document(source: str, text: str) -> Document:
    return Document(source=source, text=text)


# --- content hashing ---------------------------------------------------------


def test_content_hash_is_deterministic():
    first = calculate_content_hash("hello")
    second = calculate_content_hash("hello")
    different = calculate_content_hash("hello!")

    assert first == second
    assert first != different


# --- chunking ----------------------------------------------------------------


def test_chunk_ids_are_deterministic():
    document = make_document("a.md", "x" * 2500)

    first = chunk_document(document, chunk_size=1000, overlap=100)
    second = chunk_document(document, chunk_size=1000, overlap=100)

    assert [chunk.id for chunk in first] == ["a.md:0", "a.md:1", "a.md:2"]
    assert first == second


def test_chunks_overlap_and_cover_the_whole_text():
    text = "".join(str(i % 10) for i in range(2500))

    chunks = chunk_document(make_document("a.md", text), 1000, 100)

    assert [len(chunk.text) for chunk in chunks] == [1000, 1000, 700]
    assert chunks[0].text[-100:] == chunks[1].text[:100]
    assert chunks[-1].text.endswith(text[-50:])


def test_short_document_is_a_single_chunk():
    chunks = chunk_document(make_document("a.md", "hello"))

    assert [chunk.text for chunk in chunks] == ["hello"]


def test_blank_document_has_no_chunks():
    assert chunk_document(make_document("a.md", "  \n ")) == []


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (-5, 0), (100, -1), (100, 100), (100, 150)],
)
def test_chunk_document_rejects_invalid_sizes(chunk_size, overlap):
    with pytest.raises(ValueError):
        chunk_document(make_document("a.md", "text"), chunk_size, overlap)


# --- loading -----------------------------------------------------------------


def test_load_documents_reads_markdown_recursively(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.md").write_text("alpha", encoding="utf-8")
    (tmp_path / "nested" / "b.md").write_text("beta", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("nope", encoding="utf-8")

    documents = load_documents(tmp_path)

    assert [(d.source, d.text) for d in documents] == [
        ("a.md", "alpha"),
        ("nested/b.md", "beta"),
    ]


def test_load_documents_raises_for_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_documents(tmp_path / "missing")


# --- ingestion ---------------------------------------------------------------


def test_ingest_only_processes_changed_documents(tmp_path, stored_chunk_ids):
    store = SQLiteStore(tmp_path / "rag.db")
    embedder = FakeEmbedder()
    documents = [
        make_document("a.md", "alpha"),
        make_document("b.md", "beta"),
    ]

    first = ingest_documents(documents, embedder, store)

    assert first == IngestResult(
        documents_processed=2, documents_deleted=0, chunks_created=2
    )
    assert len(stored_chunk_ids(store)) == 2
    calls_after_first = len(embedder.calls)

    second = ingest_documents(documents, embedder, store)

    assert second == IngestResult()
    # Only the dimension probe runs; documents are not re-embedded.
    assert embedder.calls[calls_after_first:] == [[DIMENSION_PROBE]]
    assert len(stored_chunk_ids(store)) == 2


def test_ingest_reindexes_changed_document(tmp_path, stored_chunk_ids):
    store = SQLiteStore(tmp_path / "rag.db")
    embedder = FakeEmbedder()

    ingest_documents([make_document("a.md", "alpha")], embedder, store)
    result = ingest_documents([make_document("a.md", "changed")], embedder, store)

    assert result == IngestResult(documents_processed=1, chunks_created=1)
    assert stored_chunk_ids(store) == ["a.md:0"]
    assert store.get_content_hash("a.md") == calculate_content_hash("changed")


def test_ingest_removes_documents_missing_from_corpus(tmp_path, stored_chunk_ids):
    store = SQLiteStore(tmp_path / "rag.db")
    embedder = FakeEmbedder()
    both = [make_document("a.md", "alpha"), make_document("b.md", "beta")]

    ingest_documents(both, embedder, store)
    result = ingest_documents(both[:1], embedder, store)

    assert result == IngestResult(documents_deleted=1)
    assert store.list_sources() == ["a.md"]
    assert stored_chunk_ids(store) == ["a.md:0"]


def test_empty_document_is_marked_processed(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    embedder = FakeEmbedder()

    result = ingest_documents([make_document("empty.md", "   ")], embedder, store)

    assert result == IngestResult(documents_processed=1, chunks_created=0)
    assert store.get_content_hash("empty.md") == calculate_content_hash("   ")
    assert embedder.calls == []


def test_ingest_embeds_in_batches(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    embedder = FakeEmbedder()
    document = make_document("big.md", "x" * 40_000)
    expected_chunks = len(chunk_document(document))

    assert expected_chunks > EMBED_BATCH_SIZE

    result = ingest_documents([document], embedder, store)

    assert result.chunks_created == expected_chunks
    assert [len(call) for call in embedder.calls] == [
        EMBED_BATCH_SIZE,
        expected_chunks - EMBED_BATCH_SIZE,
    ]


def test_ingest_raises_when_embedding_count_mismatches(tmp_path):
    class BrokenEmbedder:
        embedding_model = "fake-embedding"

        def embed(self, texts: list[str]) -> list[list[float]]:
            return []

    store = SQLiteStore(tmp_path / "rag.db")

    with pytest.raises(ValueError):
        ingest_documents(
            [make_document("a.md", "alpha")],
            BrokenEmbedder(),
            store,
        )


def test_ingest_leaves_index_unchanged_when_embedding_fails(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    documents = [
        make_document("a.md", "alpha"),
        make_document("b.md", "beta"),
    ]
    ingest_documents(documents, FakeEmbedder(), store)
    old_hash = store.get_content_hash("a.md")
    old_chunks = {
        result.chunk.id: result.chunk.text
        for result in store.search([1.0, 1.0], top_k=10)
    }

    class FailingEmbedder:
        embedding_model = "fake-embedding"

        def embed(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("embedding service unavailable")

    changed_corpus = [make_document("a.md", "changed")]

    with pytest.raises(RuntimeError):
        ingest_documents(changed_corpus, FailingEmbedder(), store)

    assert store.get_content_hash("a.md") == old_hash
    assert sorted(store.list_sources()) == ["a.md", "b.md"]
    assert {
        result.chunk.id: result.chunk.text
        for result in store.search([1.0, 1.0], top_k=10)
    } == old_chunks
    assert old_chunks == {"a.md:0": "alpha", "b.md:0": "beta"}


def test_ingest_records_index_metadata(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")

    ingest_documents([make_document("a.md", "alpha")], FakeEmbedder(), store)

    assert store.get_index_metadata() == IndexMetadata("fake-embedding", 2)


def test_ingest_reindexes_all_documents_when_embedding_model_changes(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    documents = [
        make_document("a.md", "alpha"),
        make_document("b.md", "beta"),
    ]
    ingest_documents(documents, FakeEmbedder("model-a"), store)

    result = ingest_documents(documents, FakeEmbedder("model-b"), store)

    assert result == IngestResult(documents_processed=2, chunks_created=2)
    assert store.get_index_metadata() == IndexMetadata("model-b", 2)


def test_ingest_reindexes_when_metadata_is_missing(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    store.replace_document(
        "a.md",
        calculate_content_hash("alpha"),
        [Chunk(id="a.md:0", source="a.md", text="alpha")],
        [[1.0, 0.0]],
    )

    result = ingest_documents([make_document("a.md", "alpha")], FakeEmbedder(), store)

    assert result == IngestResult(documents_processed=1, chunks_created=1)
    assert store.get_index_metadata() == IndexMetadata("fake-embedding", 2)


def test_ingest_reindexes_when_stored_dimensions_disagree_with_metadata(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    store.replace_document(
        "a.md",
        calculate_content_hash("alpha"),
        [Chunk(id="a.md:0", source="a.md", text="alpha")],
        [[1.0, 0.0, 0.0]],
    )
    store.set_index_metadata(IndexMetadata("fake-embedding", 2))

    result = ingest_documents([make_document("a.md", "alpha")], FakeEmbedder(), store)

    assert result == IngestResult(documents_processed=1, chunks_created=1)
    assert store.get_index_metadata() == IndexMetadata("fake-embedding", 2)
    assert store.stored_embedding_dimensions() == {2}


def test_ingest_reindexes_all_when_embedding_dimension_changes(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    documents = [
        make_document("a.md", "alpha"),
        make_document("b.md", "beta"),
    ]
    ingest_documents(documents, FakeEmbedder(), store)

    result = ingest_documents(
        [
            make_document("a.md", "changed"),
            make_document("b.md", "beta"),
        ],
        WideEmbedder(),
        store,
    )

    assert result == IngestResult(documents_processed=2, chunks_created=2)
    assert store.get_index_metadata() == IndexMetadata("fake-embedding", 3)
    assert store.stored_embedding_dimensions() == {3}


def test_ingest_detects_dimension_change_when_no_document_changed(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    documents = [
        make_document("a.md", "alpha"),
        make_document("b.md", "beta"),
    ]
    ingest_documents(documents, FakeEmbedder(), store)

    result = ingest_documents(documents, WideEmbedder(), store)

    assert result == IngestResult(documents_processed=2, chunks_created=2)
    assert store.get_index_metadata() == IndexMetadata("fake-embedding", 3)
    assert store.stored_embedding_dimensions() == {3}


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (100, 100)],
)
def test_ingest_rejects_invalid_chunk_settings_even_when_documents_are_unchanged(
    tmp_path,
    chunk_size,
    overlap,
):
    store = SQLiteStore(tmp_path / "rag.db")
    embedder = FakeEmbedder()
    documents = [make_document("a.md", "alpha")]

    ingest_documents(documents, embedder, store)
    calls_before = len(embedder.calls)

    with pytest.raises(ValueError):
        ingest_documents(
            documents,
            embedder,
            store,
            chunk_size=chunk_size,
            overlap=overlap,
        )

    assert len(embedder.calls) == calls_before


def test_ingest_removes_all_documents_for_empty_corpus(tmp_path):
    store = SQLiteStore(tmp_path / "rag.db")
    embedder = FakeEmbedder()

    ingest_documents([make_document("a.md", "alpha")], embedder, store)

    result = ingest_documents([], embedder, store)

    assert result == IngestResult(documents_deleted=1)
    assert store.list_sources() == []
    assert store.has_chunks() is False


def test_ingest_rejects_inconsistent_embedding_dimensions(tmp_path):
    class InconsistentEmbedder:
        embedding_model = "fake-embedding"

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [
                [1.0, 0.0] if text == "alpha" else [1.0, 0.0, 0.0] for text in texts
            ]

    store = SQLiteStore(tmp_path / "rag.db")
    documents = [
        make_document("a.md", "alpha"),
        make_document("b.md", "beta"),
    ]

    with pytest.raises(ValueError, match="dimensions"):
        ingest_documents(documents, InconsistentEmbedder(), store)
