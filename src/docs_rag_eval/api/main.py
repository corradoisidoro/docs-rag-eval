from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

from docs_rag_eval.api.routes import router
from docs_rag_eval.config import Settings
from docs_rag_eval.config import settings as default_settings
from docs_rag_eval.db import IndexMismatchError, SQLiteStore
from docs_rag_eval.llm import OpenAICompatibleModels


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


async def _timeout(request: Request, exc: APITimeoutError) -> JSONResponse:
    return _error(status.HTTP_504_GATEWAY_TIMEOUT, "Model provider timed out")


async def _unavailable(request: Request, exc: APIConnectionError) -> JSONResponse:
    return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Model provider unavailable")


async def _rate_limited(request: Request, exc: RateLimitError) -> JSONResponse:
    return _error(
        status.HTTP_429_TOO_MANY_REQUESTS, "Model provider rate limit exceeded"
    )


async def _provider_error(request: Request, exc: APIStatusError) -> JSONResponse:
    return _error(status.HTTP_502_BAD_GATEWAY, "Model provider returned an error")


async def _corpus_missing(request: Request, exc: FileNotFoundError) -> JSONResponse:
    return _error(status.HTTP_404_NOT_FOUND, "Corpus directory not found")


async def _index_mismatch(request: Request, exc: IndexMismatchError) -> JSONResponse:
    return _error(status.HTTP_409_CONFLICT, str(exc))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else default_settings

    app = FastAPI(
        title="Docs RAG API",
        description="API for ingestion and retrieval-augmented generation.",
        version="0.1.0",
    )

    app.state.settings = settings
    app.state.store = SQLiteStore(settings.database_path)
    app.state.models = OpenAICompatibleModels(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        embedding_model=settings.embedding_model,
        chat_model=settings.chat_model,
        timeout=settings.llm_timeout_seconds,
        reasoning_effort=settings.llm_reasoning_effort,
    )

    # Starlette picks the most specific handler, so the timeout handler wins
    # over the connection handler (APITimeoutError subclasses APIConnectionError).
    app.add_exception_handler(APITimeoutError, _timeout)
    app.add_exception_handler(APIConnectionError, _unavailable)
    app.add_exception_handler(RateLimitError, _rate_limited)
    app.add_exception_handler(APIStatusError, _provider_error)
    app.add_exception_handler(FileNotFoundError, _corpus_missing)
    app.add_exception_handler(IndexMismatchError, _index_mismatch)

    app.include_router(router)

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(
        "docs_rag_eval.api.main:create_app",
        factory=True,
        host=default_settings.api_host,
        port=default_settings.api_port,
    )
