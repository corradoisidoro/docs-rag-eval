from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    top_k: int = Field(default=5, ge=1, le=20)


class CitationResponse(BaseModel):
    source: str
    chunk_id: str
    score: float


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    source: str
    text: str
    score: float


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationResponse] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunkResponse] = Field(default_factory=list)


class IngestResponse(BaseModel):
    status: Literal["completed"]
    documents_processed: int
    documents_deleted: int
    chunks_created: int


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "local"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]
