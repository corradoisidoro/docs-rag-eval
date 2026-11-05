from typing import Annotated

from fastapi import APIRouter, Depends, Request

from docs_rag_eval.api.schemas import (
    AskRequest,
    AskResponse,
    CitationResponse,
    IngestResponse,
    ModelInfo,
    ModelsResponse,
    RetrievedChunkResponse,
)
from docs_rag_eval.config import Settings
from docs_rag_eval.db import SQLiteStore
from docs_rag_eval.ingest import ingest_documents, load_documents
from docs_rag_eval.llm import OpenAICompatibleModels
from docs_rag_eval.pipeline import ask as answer_question

router = APIRouter()


# Dependencies read what `create_app` stored on the app. Provider errors are
# translated to HTTP responses by the exception handlers in `main.py`.
def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_models(request: Request) -> OpenAICompatibleModels:
    return request.app.state.models


def get_store(request: Request) -> SQLiteStore:
    return request.app.state.store


SettingsDep = Annotated[Settings, Depends(get_settings)]
ModelsDep = Annotated[OpenAICompatibleModels, Depends(get_models)]
StoreDep = Annotated[SQLiteStore, Depends(get_store)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ingest")
def ingest(
    settings: SettingsDep,
    models: ModelsDep,
    store: StoreDep,
) -> IngestResponse:
    result = ingest_documents(
        documents=load_documents(settings.corpus_dir),
        embedder=models,
        sqlite_store=store,
    )

    return IngestResponse(
        status="completed",
        documents_processed=result.documents_processed,
        documents_deleted=result.documents_deleted,
        chunks_created=result.chunks_created,
    )


@router.post("/ask")
def ask(
    payload: AskRequest,
    settings: SettingsDep,
    models: ModelsDep,
    store: StoreDep,
) -> AskResponse:
    result = answer_question(
        question=payload.question,
        embedder=models,
        chat_model=models,
        sqlite_store=store,
        min_score=settings.min_relevance_score,
        top_k=payload.top_k,
    )

    return AskResponse(
        question=result.question,
        answer=result.answer,
        citations=[
            CitationResponse(
                source=citation.source,
                chunk_id=citation.chunk_id,
                score=citation.score,
            )
            for citation in result.citations
        ],
        retrieved_chunks=[
            RetrievedChunkResponse(
                chunk_id=item.chunk.id,
                source=item.chunk.source,
                text=item.chunk.text,
                score=item.score,
            )
            for item in result.retrieved_chunks
        ],
    )


@router.get("/v1/models")
def list_models(settings: SettingsDep) -> ModelsResponse:
    return ModelsResponse(data=[ModelInfo(id=settings.chat_model)])
