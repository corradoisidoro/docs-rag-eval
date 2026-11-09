from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

import docs_rag_eval.api.routes as routes_mod
from docs_rag_eval.api.main import create_app
from docs_rag_eval.config import Settings
from docs_rag_eval.models import Answer, Chunk


class FakeModels:
    """Stands in for OpenAICompatibleModels (embeddings and chat)."""

    embedding_model = "fake-embedding"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def generate(self, question: str, context: str) -> str:
        return f"answer based on: {context[:20]}"


class AbstainingFakeModels(FakeModels):
    def generate(self, question: str, context: str) -> str:
        return (
            "The provided context does not contain information about who "
            "Acme's chief executive officer is."
        )


def make_settings(tmp_path, **overrides) -> Settings:
    values = {
        "database_path": tmp_path / "rag.db",
        "corpus_dir": tmp_path / "corpus",
        "min_relevance_score": 0.0,
        "evaluation_top_k": 3,
        "llm_base_url": "https://provider.test/v1",
        "llm_api_key": "test-key",
        "llm_timeout_seconds": 1.0,
        "llm_reasoning_effort": "",
        "embedding_model": "embedding-model",
        "chat_model": "chat-model",
        "judge_model": "judge-model",
        "evaluation_dataset": tmp_path / "cases.json",
        "evaluation_reports": tmp_path / "reports",
        "api_host": "127.0.0.2",
        "api_port": 8765,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def client(tmp_path):
    app = create_app(make_settings(tmp_path))
    app.state.models = FakeModels()
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_list_models_returns_configured_chat_model(tmp_path):
    app = create_app(make_settings(tmp_path, chat_model="my-model"))

    response = TestClient(app).get("/v1/models")

    assert response.json()["data"][0]["id"] == "my-model"


@pytest.mark.parametrize(
    ("request_top_k", "expected_top_k"),
    [(None, 3), (7, 7)],
)
def test_ask_uses_configured_top_k_unless_request_overrides_it(
    client,
    monkeypatch,
    request_top_k,
    expected_top_k,
):
    received = {}

    def fake_answer_question(**kwargs):
        received.update(kwargs)
        return Answer(
            question=kwargs["question"],
            answer="answer",
            citations=[],
            retrieved_chunks=[],
        )

    monkeypatch.setattr(routes_mod, "answer_question", fake_answer_question)
    payload: dict[str, str | int] = {"question": "What is retrieval?"}
    if request_top_k is not None:
        payload["top_k"] = request_top_k

    response = client.post("/ask", json=payload)

    assert response.status_code == 200
    assert received["top_k"] == expected_top_k


def test_ingest_then_ask_returns_answer_with_citations(client, tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_text("Retrieval finds relevant text.", encoding="utf-8")

    ingest = client.post("/ingest")

    assert ingest.status_code == 200
    assert ingest.json() == {
        "status": "completed",
        "documents_processed": 1,
        "documents_deleted": 0,
        "chunks_created": 1,
    }

    response = client.post("/ask", json={"question": " What is retrieval? "})

    body = response.json()
    assert response.status_code == 200
    assert body["question"] == "What is retrieval?"
    assert body["answer"].startswith("answer based on: Retrieval")
    assert body["citations"] == [
        {"source": "doc.md", "chunk_id": "doc.md:0", "score": pytest.approx(1.0)}
    ]

    assert body["retrieved_chunks"] == [
        {
            "chunk_id": "doc.md:0",
            "source": "doc.md",
            "text": "Retrieval finds relevant text.",
            "score": pytest.approx(1.0),
        }
    ]


def test_ask_abstention_returns_empty_citations(client, tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_text(
        "Acme engineering handbook details.",
        encoding="utf-8",
    )
    client.app.state.models = AbstainingFakeModels()
    assert client.post("/ingest").status_code == 200

    response = client.post(
        "/ask",
        json={"question": "Who is Acme's chief executive officer?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"].startswith(
        "The provided context does not contain information"
    )
    assert response.json()["citations"] == []
    assert response.json()["retrieved_chunks"]


def test_ingest_without_corpus_directory_returns_404(client):
    response = client.post("/ingest")

    assert response.status_code == 404
    assert response.json() == {"detail": "Corpus directory not found"}


def test_ask_with_changed_embedding_model_returns_409(client, tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_text("Retrieval finds relevant text.", encoding="utf-8")
    assert client.post("/ingest").status_code == 200

    client.app.state.models.embedding_model = "other-embedding"

    response = client.post("/ask", json={"question": "What is retrieval?"})

    assert response.status_code == 409
    assert "other-embedding" in response.json()["detail"]


def test_ask_without_index_metadata_returns_409(tmp_path):
    app = create_app(make_settings(tmp_path))
    app.state.store.replace_document(
        "doc.md",
        "hash",
        [Chunk(id="doc.md:0", source="doc.md", text="text")],
        [[1.0, 0.0]],
    )
    app.state.models = FakeModels()

    response = TestClient(app).post("/ask", json={"question": "question"})

    assert response.status_code == 409
    assert "metadata" in response.json()["detail"]


def test_ingest_reindexes_after_embedding_model_change(client, tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_text("Retrieval finds relevant text.", encoding="utf-8")
    assert client.post("/ingest").json()["documents_processed"] == 1

    client.app.state.models.embedding_model = "other-embedding"
    second = client.post("/ingest")

    assert second.status_code == 200
    assert second.json()["documents_processed"] == 1
    assert second.json()["chunks_created"] == 1

    ask = client.post("/ask", json={"question": "What is retrieval?"})
    assert ask.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "q", "top_k": 0},
        {"question": "q", "top_k": 21},
        {},
    ],
)
def test_ask_rejects_invalid_requests(client, payload):
    assert client.post("/ask", json=payload).status_code == 422


def test_ask_timeout_returns_504(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path))

    def raising(**kwargs: Any) -> None:
        raise APITimeoutError(request=cast(Any, None))

    monkeypatch.setattr(routes_mod, "answer_question", raising)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/ask", json={"question": "question"})

    assert response.status_code == 504
    assert response.json() == {"detail": "Model provider timed out"}


def test_ask_connection_error_returns_503(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path))

    def raising(**kwargs: Any) -> None:
        raise APIConnectionError(request=cast(Any, None))

    monkeypatch.setattr(routes_mod, "answer_question", raising)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/ask", json={"question": "question"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Model provider unavailable"}


def _provider_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", "http://test"))


def test_ask_rate_limit_returns_429(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path))

    def raising(**kwargs: Any) -> None:
        raise RateLimitError(
            "rate limited",
            response=_provider_response(429),
            body=None,
        )

    monkeypatch.setattr(routes_mod, "answer_question", raising)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/ask", json={"question": "question"})

    assert response.status_code == 429
    assert response.json() == {"detail": "Model provider rate limit exceeded"}


def test_ask_provider_error_returns_502(tmp_path, monkeypatch):
    app = create_app(make_settings(tmp_path))

    def raising(**kwargs: Any) -> None:
        raise APIStatusError(
            "provider error",
            response=_provider_response(500),
            body=None,
        )

    monkeypatch.setattr(routes_mod, "answer_question", raising)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/ask", json={"question": "question"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Model provider returned an error"}
