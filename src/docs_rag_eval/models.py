"""Domain models shared by ingestion, retrieval, and the API."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    """A source document read from the corpus."""

    source: str
    text: str


@dataclass(frozen=True)
class Chunk:
    """A slice of a document that is embedded and stored."""

    id: str
    source: str
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    """A stored chunk paired with its cosine similarity score."""

    chunk: Chunk
    score: float


@dataclass(frozen=True)
class Citation:
    """A reference to a retrieved chunk, with its similarity score."""

    source: str
    chunk_id: str
    score: float


@dataclass(frozen=True)
class Answer:
    """A final answer and the evidence retrieved to support it."""

    question: str
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
