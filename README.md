# docs-rag-eval

A lightweight Retrieval-Augmented Generation (RAG) application with Markdown ingestion, SQLite-backed embedding storage, cosine-similarity retrieval, and LLM-powered question answering over an ingested corpus.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- An OpenAI-compatible API. The defaults target a local [Ollama](https://ollama.com/) instance.

Pull the required models:

```powershell
ollama pull nomic-embed-text
ollama pull qwen3.5:9b
```

## Setup

```powershell
uv sync
copy .env.example .env
```

On macOS or Linux, use `cp .env.example .env` instead.

Every setting has a default, so `.env` is optional. Values come from environment variables first, then `.env`. Relative paths are resolved from the project root.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible API base URL |
| `LLM_API_KEY` | `ollama` | API key |
| `LLM_TIMEOUT_SECONDS` | `120` | Request timeout |
| `LLM_REASONING_EFFORT` | `none` | Optional reasoning-effort value sent to the provider |
| `CHAT_MODEL` | `qwen3.5:9b` | Chat model |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `MIN_RELEVANCE_SCORE` | `0.5` | Minimum cosine similarity for a chunk to be used |
| `DATABASE_PATH` | `data/rag.db` | SQLite database file |
| `CORPUS_DIR` | `corpus` | Directory containing Markdown files |

`LLM_REASONING_EFFORT` is passed to the provider as `reasoning_effort`. Provider support and behaviour may vary. Set `LLM_REASONING_EFFORT=` to omit the parameter entirely.

If no chunk reaches `MIN_RELEVANCE_SCORE`, the API returns a response indicating that relevant information could not be found, includes no citations, and does not call the chat model.

## Run the API

```powershell
uv run docs-rag-eval
```

Or, with auto-reload:

```powershell
uv run uvicorn docs_rag_eval.api.main:create_app --factory --reload
```

The API is served at `http://127.0.0.1:8000`. Interactive API documentation is available at `/docs`.

## Usage

Sync the index with the Markdown files in `corpus/`:

```powershell
curl.exe -X POST http://127.0.0.1:8000/ingest
```

Ingestion is incremental:

- New and changed files (detected by content hash) are re-chunked and re-embedded.
- Unchanged files are skipped.
- Files removed from `corpus/` are removed from the index.
- All changes are applied in one transaction, so a failed embedding leaves the previous index untouched.

Ask a question:

```powershell
curl.exe -X POST http://127.0.0.1:8000/ask `
  -H "Content-Type: application/json" `
  -d '{"question": "What is retrieval?", "top_k": 5}'
```

The response includes:

- `answer`: the generated answer.
- `citations`: source file, chunk ID, and cosine similarity score.
- `retrieved_chunks`: the actual text retrieved and passed to the chat model, together with its source, chunk ID, and similarity score.

Chunk IDs use the stable format `<source>:<index>`.

Other endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `GET` | `/v1/models` | Configured chat model |
| `POST` | `/ingest` | Ingest and synchronize Markdown documents |
| `POST` | `/ask` | Retrieve relevant chunks and generate an answer |

Model provider failures map to:

- `429`: provider rate limit exceeded.
- `502`: provider returned an error.
- `503`: provider unavailable.
- `504`: provider timed out.

A `409` means the stored index is missing metadata or was built with a different embedding model or vector size. Run `POST /ingest` to rebuild it.

## How it works

1. **Chunking**: Documents are split into 1,000-character windows with 150 characters of overlap.
2. **Embedding**: Chunks are embedded in batches of 32 and stored as JSON in SQLite. The index records the embedding model and vector size. `/ask` rejects an index built with a different model instead of silently returning incorrect results.
3. **Retrieval**: The question is embedded, every chunk is scored by cosine similarity in Python, and the top-k chunks above `MIN_RELEVANCE_SCORE` are kept. This is simple and suitable for a small corpus; a vector index would be more appropriate for larger datasets.
4. **Answering**: Retrieved chunks are passed to the chat model as context. The model is instructed to answer using only the supplied context.

## Evaluation

The `evals/` directory contains curated question sets for manually evaluating retrieval and answer quality.

- `acme-engineering-handbook.md`: Domain-specific questions, wording variations, multi-section questions, and unanswerable questions.
- `rag-fundamentals.md`: Basic RAG questions, semantic variations, multi-chunk questions, and unanswerable questions.

Use these question sets with `POST /ask`. Compare the retrieved chunks, citations, and generated answers against the expected results.

The evaluation sets help assess:

- Retrieval relevance.
- Context coverage across multiple chunks.
- Semantic matching beyond exact keywords.
- Whether the model avoids answering questions unsupported by the corpus.

## Project layout

```text
src/docs_rag_eval/
  api/          FastAPI app, routes, and response schemas
  config.py     Environment and .env settings
  db.py         SQLite storage and cosine-similarity search
  ingest.py     Markdown loading, chunking, and incremental sync
  llm.py        OpenAI-compatible embeddings and chat
  models.py     Shared dataclasses
  pipeline.py   Retrieval plus answer generation
  retrieve.py   Top-k retrieval and score filtering

corpus/         Markdown source documents
tests/          Unit and API tests
evals/          Curated question sets for manual evaluation
```

## Notes

- Changing `EMBEDDING_MODEL`, or using a model whose vector size changed under the same name, is detected automatically. The next `/ingest` re-embeds the whole corpus and updates the index metadata. Until then, `/ask` returns `409` instead of silently returning no results.
- Changing the chunking parameters requires deleting `data/rag.db` and running `/ingest` again. Content hashes do not change when only the chunking configuration changes, so unchanged files would otherwise be skipped.
- An empty `corpus/` directory removes all documents from the index.

## Current limitations

- Retrieval uses a linear scan over stored embeddings, suitable for a small corpus.
- Chunking uses fixed character windows rather than semantic boundaries.
- Evaluation is currently manual; automated evaluation metrics are a potential future improvement.
- Only Markdown documents are supported.

## Tests and linting

Run the test suite:

```powershell
uv run pytest
```

Check code quality and formatting:

```powershell
uv run ruff check .
uv run ruff format --check .
```
