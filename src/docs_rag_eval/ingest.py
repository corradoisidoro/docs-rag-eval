import hashlib
from dataclasses import dataclass
from pathlib import Path

from docs_rag_eval.db import DocumentWrite, IndexMetadata, SQLiteStore
from docs_rag_eval.llm import Embedder
from docs_rag_eval.models import Chunk, Document

EMBED_BATCH_SIZE = 32
DIMENSION_PROBE = "dimension probe"


@dataclass(frozen=True)
class IngestResult:
    documents_processed: int = 0
    documents_deleted: int = 0
    chunks_created: int = 0


def calculate_content_hash(text: str) -> str:
    """Return a stable fingerprint used to detect changed documents."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_documents(corpus_dir: Path) -> list[Document]:
    """Read every Markdown file under the corpus directory."""
    if not corpus_dir.is_dir():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_dir}")

    return [
        Document(
            source=path.relative_to(corpus_dir).as_posix(),
            text=path.read_text(encoding="utf-8"),
        )
        for path in sorted(corpus_dir.rglob("*.md"))
        if path.is_file()
    ]


def chunk_document(
    document: Document,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[Chunk]:
    """Split a document into overlapping character windows.

    Chunk ids are deterministic (``<source>:<index>``), so re-ingesting the
    same text yields the same ids and citations stay comparable across runs.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")

    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size - 1")

    text = document.text.strip()
    chunks = []

    for index, start in enumerate(range(0, len(text), chunk_size - overlap)):
        chunks.append(
            Chunk(
                id=f"{document.source}:{index}",
                source=document.source,
                text=text[start : start + chunk_size],
            )
        )
        if start + chunk_size >= len(text):
            break  # the last window reached the end; no redundant tail chunk

    return chunks


def ingest_documents(
    documents: list[Document],
    embedder: Embedder,
    sqlite_store: SQLiteStore,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> IngestResult:
    """Sync the index with the corpus: add, update, and remove documents.

    Every changed document is chunked and embedded before anything is written.
    The resulting deletions and writes are then applied in one transaction, so
    a failed embedding leaves the previous index untouched.

    If the index was built with a different embedding model, every document is
    re-embedded so the stored vectors stay comparable.
    """

    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")

    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size - 1")

    current_sources = {document.source for document in documents}
    stale_sources = [s for s in sqlite_store.list_sources() if s not in current_sources]

    embedding_model = embedder.embedding_model
    metadata = sqlite_store.get_index_metadata()
    has_chunks = sqlite_store.has_chunks()

    reindex_all = has_chunks and (
        metadata is None or metadata.embedding_model != embedding_model
    )

    if has_chunks and metadata is not None and not reindex_all:
        reindex_all = sqlite_store.stored_embedding_dimensions() != {
            metadata.embedding_dimension
        }

    writes, chunks_created, dimension = _build_writes(
        documents,
        embedder,
        sqlite_store,
        chunk_size,
        overlap,
        force=reindex_all,
    )

    if not reindex_all and dimension is None and has_chunks and metadata is not None:
        # Nothing changed, but the model name does not guarantee a stable
        # vector size. Probe once so a silently changed model cannot leave
        # /ask stuck on 409 without a way to rebuild through /ingest.
        [probe] = _embed_in_batches(embedder, [DIMENSION_PROBE])
        dimension = len(probe)

    if (
        not reindex_all
        and dimension is not None
        and metadata is not None
        and dimension != metadata.embedding_dimension
    ):
        # The model name is unchanged but its output dimension changed.
        writes, chunks_created, dimension = _build_writes(
            documents,
            embedder,
            sqlite_store,
            chunk_size,
            overlap,
            force=True,
        )

    new_metadata = (
        IndexMetadata(embedding_model, dimension) if dimension is not None else None
    )

    sqlite_store.apply_changes(
        deletions=stale_sources,
        writes=writes,
        metadata=new_metadata,
    )

    return IngestResult(
        documents_processed=len(writes),
        documents_deleted=len(stale_sources),
        chunks_created=chunks_created,
    )


def _build_writes(
    documents: list[Document],
    embedder: Embedder,
    sqlite_store: SQLiteStore,
    chunk_size: int,
    overlap: int,
    *,
    force: bool,
) -> tuple[list[DocumentWrite], int, int | None]:
    """Chunk and embed documents, returning writes, chunk count, and dimension."""
    writes: list[DocumentWrite] = []
    chunks_created = 0
    dimension: int | None = None

    for document in documents:
        content_hash = calculate_content_hash(document.text)

        if not force and sqlite_store.get_content_hash(document.source) == content_hash:
            continue  # unchanged since last ingest

        chunks = chunk_document(document, chunk_size, overlap)
        embeddings = _embed_in_batches(embedder, [chunk.text for chunk in chunks])

        if embeddings:
            document_dimension = len(embeddings[0])
            if dimension is None:
                dimension = document_dimension
            elif dimension != document_dimension:
                raise ValueError("Embedding dimensions differ between documents")

        writes.append(
            DocumentWrite(
                source=document.source,
                content_hash=content_hash,
                chunks=chunks,
                embeddings=embeddings,
            )
        )
        chunks_created += len(chunks)

    return writes, chunks_created, dimension


def _embed_in_batches(embedder: Embedder, texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        embeddings.extend(embedder.embed(texts[start : start + EMBED_BATCH_SIZE]))

    if len(embeddings) != len(texts):
        raise ValueError("Embedding count does not match chunk count")

    if embeddings:
        dimension = len(embeddings[0])
        if dimension < 1:
            raise ValueError("Embedding vectors must not be empty")
        if any(len(embedding) != dimension for embedding in embeddings):
            raise ValueError("Embedding vectors have inconsistent dimensions")

    return embeddings
