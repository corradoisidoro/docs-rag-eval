import pytest

from docs_rag_eval.db import IndexMetadata, SQLiteStore
from docs_rag_eval.models import Chunk
from docs_rag_eval.pipeline import NOT_FOUND_ANSWER, ask


class FixedEmbedder:
    embedding_model = "test-embedding"

    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.vector]


class FakeChatModel:
    def __init__(self, answer: str = "generated answer") -> None:
        self.calls = 0
        self.last_context = ""
        self.answer = answer

    def generate(self, question: str, context: str) -> str:
        self.calls += 1
        self.last_context = context
        return self.answer


def make_store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "rag.db")

    store.replace_document(
        "doc.md",
        "hash",
        [Chunk(id="chunk", source="doc.md", text="stored text")],
        [[1.0, 0.0]],
    )
    store.set_index_metadata(IndexMetadata("test-embedding", 2))

    return store


def test_ask_returns_fallback_without_calling_model_when_nothing_is_relevant(
    tmp_path,
):
    store = make_store(tmp_path)
    chat_model = FakeChatModel()

    answer = ask(
        question="unrelated question",
        embedder=FixedEmbedder([0.0, 1.0]),
        chat_model=chat_model,
        sqlite_store=store,
        min_score=0.5,
        top_k=3,
    )

    assert chat_model.calls == 0
    assert answer.citations == []
    assert answer.answer == NOT_FOUND_ANSWER
    assert answer.retrieved_chunks == []


def test_ask_uses_relevant_chunks_and_returns_citations_with_scores(tmp_path):
    store = make_store(tmp_path)
    chat_model = FakeChatModel()

    answer = ask(
        question="related question",
        embedder=FixedEmbedder([1.0, 0.0]),
        chat_model=chat_model,
        sqlite_store=store,
        min_score=0.5,
        top_k=3,
    )

    assert chat_model.calls == 1
    assert chat_model.last_context == "stored text"
    assert answer.answer == "generated answer"

    [citation] = answer.citations
    assert (citation.source, citation.chunk_id) == ("doc.md", "chunk")
    assert citation.score == pytest.approx(1.0)

    assert len(answer.retrieved_chunks) == 1
    retrieved_chunk = answer.retrieved_chunks[0]
    assert retrieved_chunk.chunk.id == "chunk"
    assert retrieved_chunk.chunk.text == "stored text"
    assert retrieved_chunk.score == pytest.approx(1.0)


def test_ask_abstention_has_no_citations_but_retains_retrieved_context(tmp_path):
    store = make_store(tmp_path)
    chat_model = FakeChatModel(
        "The provided context does not contain information about this question."
    )

    answer = ask(
        question="unanswerable question",
        embedder=FixedEmbedder([1.0, 0.0]),
        chat_model=chat_model,
        sqlite_store=store,
        min_score=0.5,
        top_k=3,
    )

    assert chat_model.calls == 1
    assert answer.citations == []
    assert len(answer.retrieved_chunks) == 1


def test_ask_rejects_blank_question(tmp_path):
    with pytest.raises(ValueError):
        ask(
            question="   ",
            embedder=FixedEmbedder([1.0, 0.0]),
            chat_model=FakeChatModel(),
            sqlite_store=make_store(tmp_path),
            min_score=0.0,
            top_k=3,
        )
