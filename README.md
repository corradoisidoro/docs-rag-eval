# docs-rag-eval

[![CI](https://github.com/corradoisidoro/docs-rag-eval/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/corradoisidoro/docs-rag-eval/actions/workflows/ci.yml)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-4B8BBE?logo=pytest&logoColor=white)](https://github.com/corradoisidoro/docs-rag-eval/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**A hands-on project exploring how to evaluate Retrieval-Augmented Generation (RAG) systems using a custom LLM-as-a-Judge.**

This project is licensed under the [MIT License](LICENSE).

The focus of this project is not to build a production-ready RAG platform or demonstrate the most sophisticated retrieval architecture. Instead, it is to understand how a RAG system behaves, evaluate the quality of its outputs, and investigate whether those evaluations can be trusted.

A lightweight RAG application provides the system under evaluation. The main focus is the evaluation methodology: measuring answer quality, assessing retrieved context, and understanding the strengths and limitations of LLM-based judgments.

## Why this project exists

A RAG system retrieves information from an external knowledge source and passes that information to a language model to generate an answer.

But how do we know whether the result is good?

A generated answer can sound convincing while being factually incorrect. It can be correct but unsupported by the retrieved context. The retriever can return relevant information alongside unnecessary or irrelevant chunks.

Evaluating these behaviours requires looking beyond the generated answer alone.

This project explores four fundamental questions:

1. **Is the answer correct?** Does it agree with the expected answer?
2. **Is the answer relevant?** Does it address the question being asked?
3. **Is the answer grounded?** Are its claims supported by the retrieved context?
4. **Is the retrieved context useful?** Does it contain the information needed to answer, without being dominated by irrelevant information?

These questions form the basis of the project's evaluation methodology.

### Metric references

The metric selection and evaluation concepts in this project are informed by established LLM and RAG evaluation frameworks.

The following documentation provides useful background and reference material:

- **[Ragas – Metrics](https://docs.ragas.io/en/v0.1.21/concepts/metrics/index.html)**: Reference for RAG evaluation metrics, including Faithfulness, Answer Relevance, Context Precision and Context Recall.
- **[DeepEval – Answer Relevancy](https://deepeval.com/docs/metrics-answer-relevancy)**: Reference for evaluating whether generated answers address the user's question using an LLM-as-a-Judge.

These references help explain the underlying evaluation concepts and provide points of comparison for the custom implementation.

The metrics implemented in this project have their own definitions, prompts and scoring logic. Similar metric names do not necessarily imply identical evaluation methodologies or results.

## Evaluation approach: LLM-as-a-Judge

Evaluating generated answers is not always as simple as comparing two strings or applying a deterministic formula. The same question can have multiple valid answers, expressed in different ways.

This project uses **LLM-as-a-Judge**: a separate language model evaluates the output of the RAG pipeline and produces structured judgments that can be measured and analysed.

Rather than starting with an evaluation framework, this project implements a custom LLM-as-a-Judge in Python.

The goal is to understand and control the evaluation process:

- Define what each metric measures.
- Design the judge instructions and evaluation criteria.
- Validate structured judge responses.
- Calculate scores using explicit scoring logic.
- Inspect individual judgments and their rationales.
- Understand the limitations and variability of model-generated scores.

Building a custom evaluator also avoids introducing a framework dependency into the initial implementation. The trade-off is that the evaluation logic, validation and maintenance remain the project's responsibility.

### Why build a custom evaluator?

Evaluation frameworks such as [DeepEval](https://deepeval.com/), [RAGAS](https://docs.ragas.io/) and [Langfuse](https://langfuse.com/) provide useful tools for evaluating and monitoring LLM applications.

However, using a framework does not remove the need to understand what is being evaluated or how its metrics are calculated.

This project takes a learning-oriented approach:

- Understand the evaluation methodology before adopting an abstraction.
- Maintain control over judge prompts, scoring criteria and response validation.
- Understand how individual scores are produced.
- Avoid introducing a framework dependency for the initial implementation.
- Retain the flexibility to compare the custom implementation against established frameworks.

The objective is not to demonstrate that a custom evaluator is universally better than an existing framework. It is to understand the underlying evaluation process and make informed engineering decisions.

## Evaluation methodology

The custom evaluator currently uses five metrics, selected to assess both answer quality and retrieval quality.

### Answer quality

| Metric | Purpose |
| --- | --- |
| `answer_correctness` | Evaluates factual agreement with the expected answer, giving partial credit for supported correct facts and penalising missing or incorrect facts. For unanswerable questions, an appropriate abstention is rewarded. |
| `answer_relevancy` | Evaluates how directly and completely the generated answer addresses the question, independently of factual correctness. |
| `faithfulness` | Evaluates whether the factual claims in the generated answer are supported by the retrieved context. Unsupported or contradicted claims lower the score. |

### Retrieval quality

| Metric | Purpose |
| --- | --- |
| `context_precision` | Evaluates whether retrieved chunks contain useful information, rewarding relevant chunks that appear higher in the retrieval order. |
| `context_recall` | Evaluates whether the retrieved context contains the information needed to produce the expected answer. It is not applicable to unanswerable questions. |

These metrics were selected because they cover different aspects of RAG quality rather than attempting to represent system quality with a single score.

They are complementary, not interchangeable. For example, a correct answer does not necessarily demonstrate faithfulness: the model might produce a correct fact that was not present in the retrieved context.

The custom metrics are inspired by established RAG evaluation concepts. Their definitions and implementations are specific to this project and should not automatically be considered identical to metrics provided by external frameworks.

### Understanding and validating the judge

A score is only useful when we understand what it represents and how it was produced.

LLM-as-a-Judge introduces its own evaluation problem: the judge can make mistakes, interpret criteria inconsistently, or produce different scores across runs.

For that reason, generated scores should not be treated as ground truth.

An important part of this project is to investigate alignment between LLM judgments and human evaluations:

1. Build representative evaluation datasets.
2. Have human evaluators rate a sample of answers and retrieved contexts.
3. Compare human scores with judge scores.
4. Review disagreements and identify their causes.
5. Refine judge instructions and scoring criteria.
6. Repeat evaluations to assess consistency.

The long-term objective is not simply to produce more metrics, but to understand how trustworthy those metrics are.

### Further evaluation with DeepEval

A planned extension is to introduce [DeepEval](https://deepeval.com/) as an additional evaluation framework.

The intention is not to replace the custom evaluator. Instead, DeepEval will provide another evaluation approach that can be compared against the project's own implementation.

The comparison will help investigate:

- Differences in metric definitions and evaluation criteria.
- Differences in scoring behaviour and results.
- The strengths and limitations of a custom implementation compared with an established framework.

DeepEval metrics will be selected based on their relevance to the existing evaluation methodology. Metrics with similar names will not automatically be assumed to have identical definitions or implementations.

The custom evaluator will remain the primary implementation, while DeepEval will serve as an additional validation and comparison tool.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- An OpenAI-compatible API. The example configuration targets a local [Ollama](https://ollama.com/) instance.

Pull the models configured by `EMBEDDING_MODEL`, `CHAT_MODEL`, and `JUDGE_MODEL` in `.env.example`:

```powershell
Get-Content .env.example | Select-String '^(EMBEDDING_MODEL|CHAT_MODEL|JUDGE_MODEL)='
```

Use `ollama pull <model-name>` for each value.

## Setup

```powershell
uv sync
copy .env.example .env
```

On macOS or Linux, use `cp .env.example .env` instead.

The application requires configuration from environment variables or `.env`; it never loads `.env.example` automatically. Copy `.env.example` to `.env` and customize its values. Environment variables take precedence over `.env`. Relative paths are resolved from the project root.

### Configuration

| Variable | Configuration source | Purpose |
| --- | --- | --- |
| `LLM_BASE_URL` | `.env` | OpenAI-compatible model API base URL |
| `LLM_API_KEY` | `.env` | API key |
| `LLM_TIMEOUT_SECONDS` | `.env` | Request timeout |
| `LLM_REASONING_EFFORT` | `.env` | Optional reasoning-effort value sent to the provider |
| `CHAT_MODEL` | `.env` | Chat model |
| `JUDGE_MODEL` | `.env` | Separate model used by the LLM-as-a-Judge |
| `EMBEDDING_MODEL` | `.env` | Embedding model |
| `MIN_RELEVANCE_SCORE` | `.env` | Minimum cosine similarity for a chunk to be used |
| `DATABASE_PATH` | `.env` | SQLite database file |
| `CORPUS_DIR` | `.env` | Directory containing Markdown files |
| `EVALUATION_DATASET` | `.env` | JSON dataset file or directory of JSON datasets |
| `EVALUATION_REPORTS` | `.env` | Directory for generated per-dataset judge reports |
| `EVALUATION_TOP_K` | `.env` | Number of chunks retrieved and used for evaluation |
| `API_HOST` | `.env` | API bind address |
| `API_PORT` | `.env` | API port |

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

The API listens at the configured `API_HOST` and `API_PORT`. Interactive API documentation is available at `/docs`.

## Usage

### Ingest documents

Sync the index with the Markdown files in `corpus/`:

```powershell
curl.exe -X POST http://<API_HOST>:<API_PORT>/ingest
```

Ingestion is incremental:

- New and changed files (detected by content hash) are re-chunked and re-embedded.
- Unchanged files are skipped.
- Files removed from `corpus/` are removed from the index.
- All changes are applied in one transaction, so a failed embedding leaves the previous index untouched.

### Ask a question

```powershell
curl.exe -X POST http://<API_HOST>:<API_PORT>/ask `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"What is retrieval?\"}'
```

Replace `API_HOST` and `API_PORT` with the values from `.env`.

If `top_k` is omitted, the API uses `EVALUATION_TOP_K` from `.env`.

The response includes:

- `answer`: the generated answer.
- `citations`: source file, chunk ID, and cosine similarity score.
- `retrieved_chunks`: the actual text retrieved and passed to the chat model, together with its source, chunk ID, and similarity score.

Chunk IDs use the stable format `<source>:<index>`.

### API endpoints

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

## How the RAG application works

The RAG application is intentionally lightweight. Its purpose is to provide a working pipeline whose retrieval and generated answers can be evaluated.

1. **Chunking:** Documents are split into 1,000-character windows with 150 characters of overlap.
2. **Embedding:** Chunks are embedded in batches of 32 and stored as JSON in SQLite. The index records the embedding model and vector size. `/ask` rejects an index built with a different model instead of silently returning incorrect results.
3. **Retrieval:** The question is embedded, every chunk is scored by cosine similarity in Python, and the top-k chunks above `MIN_RELEVANCE_SCORE` are kept. This is simple and suitable for a small corpus; a vector index would be more appropriate for larger datasets.
4. **Answering:** Retrieved chunks are passed to the chat model as context. The model is instructed to answer using only the supplied context.

## Running the custom evaluation

The Markdown question sets in `evals/` can be used to manually check retrieval and answer quality with `POST /ask`.

For automated answer and retrieval-context scoring, run the custom LLM-as-a-Judge against a JSON dataset:

```powershell
uv run python -m evals.custom.judge
```

By default, the runner reads `EVALUATION_DATASET`.

### Evaluation dataset

Each evaluation case contains four fields:

| Field | Purpose |
| --- | --- |
| `question` | The question sent to the RAG pipeline. |
| `expected_answer` | The reference answer used by the judge. |
| `should_answer` | Whether the corpus is expected to contain an answer. |
| `expected_sources` | Source document filenames expected to be retrieved for answerable questions. |

Answerable cases must list at least one expected source. Unanswerable cases must use an empty list. Filenames must be unique and correspond to Markdown documents in `corpus/`.

Example answerable case:

```json
{
  "question": "What is retrieval-augmented generation?",
  "expected_answer": "RAG retrieves relevant source material and uses it to ground a generated answer.",
  "should_answer": true,
  "expected_sources": ["rag-fundamentals.md"]
}
```

An unanswerable case has no expected source:

```json
{
  "question": "Who is Acme's chief executive officer?",
  "expected_answer": "The supplied documents do not identify Acme's chief executive officer, so the system should abstain.",
  "should_answer": false,
  "expected_sources": []
}
```

### Evaluation execution

The runner syncs the configured corpus into the configured SQLite database, runs the RAG pipeline in process for every question, and evaluates each answer with a separate judge-model request. No API server is required.

By default, `EVALUATION_DATASET` points to a directory; the runner processes every top-level `*.json` dataset in sorted filename order and writes one report per dataset to `EVALUATION_REPORTS`:

```powershell
uv run python -m evals.custom.judge
```

For example, `rag_test_cases.json` produces `evals/reports/rag_test_cases-report.json`. The reports directory is created automatically, and generated JSON reports there are excluded from Git.

A new run overwrites the report for the same dataset.

Command-line options:

- `--dataset <path>` overrides the configured dataset file or directory.
- `--output <path>` overrides the reports directory. When evaluating a single dataset, a `.json` output path can specify the exact report filename.

### Judge configuration

The judge uses the configured OpenAI-compatible endpoint (`LLM_BASE_URL` and `LLM_API_KEY`) and `JUDGE_MODEL`, separate from the RAG `CHAT_MODEL` by default.

Change `JUDGE_MODEL` to select another judge model.

The report includes each answer, its retrieved contexts, its five metric scores, and the aggregate metric means.

### Metrics and scoring

| Metric | What it evaluates |
| --- | --- |
| `answer_correctness` | Factual agreement with `expected_answer`, giving partial credit for supported correct facts and penalising missing or incorrect facts. For unanswerable questions, an appropriate abstention is rewarded. |
| `answer_relevancy` | How directly and completely the answer addresses the question, independently of factual correctness. |
| `faithfulness` | How much of the answer's factual content is supported by the retrieved contexts; unsupported or contradicted claims lower the score. |
| `context_precision` | Whether each retrieved chunk contains information useful to answering the question, with higher-ranked relevant chunks rewarded more. |
| `context_recall` | Whether the retrieved context contains the information needed to answer, measured against the expected answer. It is `null` when `should_answer` is `false`. |

Every numeric score is finite and normalized to **0.0–1.0**.

The request uses a context-specific JSON Schema to constrain the number of chunk labels and the allowed `context_recall` type. Pydantic models validate the judge response and report, including score bounds.

The evaluator also checks that:

- `context_recall` is `null` only for unanswerable cases.
- There is one relevance label per retrieved chunk.

For `context_precision`, the judge labels each retrieved chunk in retrieval order; the evaluator calculates average precision from those labels.

For example, relevance labels `[true, false, true]` produce:

```text
(1/1 + 2/3) / 2 = 0.83
```

A relevant chunk near the top therefore contributes more than one near the bottom.

These per-chunk labels are intermediate data, not an additional reported metric.

If all questions are unanswerable, aggregate `context_recall` is `null`; otherwise, it averages only answerable cases.

### Judge response validation

The evaluator retries once when judge output:

- Contains invalid JSON.
- Violates the Pydantic schema.
- Fails answerability checks.
- Fails chunk-count checks.

If the retry is also invalid, the evaluator fails the evaluation instead of silently substituting a score.

### Example evaluation result

One-question result:

| Metric | Score |
| --- | ---: |
| `answer_correctness` | 0.50 |
| `answer_relevancy` | 1.00 |
| `faithfulness` | 0.80 |
| `context_precision` | 1.00 |
| `context_recall` | 1.00 |

These are sample judge scores for "What is RAG?"; LLM judgments may vary between runs.

The metrics object contains exactly these five scores; there are no additional aggregate or per-case metrics.

Per-case metrics are model judgments, not a substitute for human review. Before using them as release gates, compare the judge against human-rated examples, review disagreements, and maintain a representative, versioned dataset as the corpus changes.

### Expected sources and future retrieval metrics

`expected_sources` currently serves as dataset reference metadata only.

The evaluator does not yet calculate deterministic source-level retrieval metrics such as:

- Source precision.
- Source recall.
- Reciprocal rank.

Its report contains only the five LLM-as-a-Judge metrics listed above.

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
evals/          Curated question sets and custom automated evaluation
```

## Notes

- Changing `EMBEDDING_MODEL`, or using a model whose vector size changed under the same name, is detected automatically. The next `/ingest` re-embeds the whole corpus and updates the index metadata. Until then, `/ask` returns `409` instead of silently returning no results.
- Changing the chunking parameters requires deleting the configured SQLite database and running `/ingest` again. Content hashes do not change when only the chunking configuration changes, so unchanged files would otherwise be skipped.
- An empty `corpus/` directory removes all documents from the index.

## Current limitations

- Retrieval uses a linear scan over stored embeddings, suitable for a small corpus.
- Chunking uses fixed character windows rather than semantic boundaries.
- LLM-as-a-Judge scores are model-generated estimates and should be reviewed alongside manual checks.
- Judge scores may vary between runs.
- Human alignment and systematic correlation analysis remain areas for further development.
- Only Markdown documents are supported.
- DeepEval integration is planned but not yet implemented.
- Deterministic source-level retrieval metrics are not yet implemented.

## Tests and linting

Run the unit and non-integration tests:

```powershell
uv run pytest -m "not integration" -q
```

Run the live RAG-and-judge integration test separately:

```powershell
uv run pytest -m integration -q
```

The integration test requires a `.env` configured for a local OpenAI-compatible provider, available embedding/chat/judge models, and the configured corpus.

It uses a temporary SQLite database and reads only one dataset: the configured file, or the first `*.json` file in the configured dataset directory in sorted filename order.

That dataset must contain at least one answerable and one unanswerable case. By default, the test evaluates the first answerable case and the first unanswerable case. Set `CUSTOM_JUDGE_CASE_LIMIT` to evaluate more answerable cases; the first unanswerable case is still included.

If `.env` is absent or the configured endpoint is not local, pytest skips the integration test. Consequently, running only the non-integration command intentionally deselects this live test; run the integration command to exercise the actual configured models.

Run the complete test suite (including the integration test when its prerequisites are available):

```powershell
uv run pytest
```

Check code quality and formatting:

```powershell
uv run ruff check .
uv run ruff format --check .
```

---

## Project philosophy

> **Don't just collect evaluation scores. Understand what they measure, how they are produced, and whether they can be trusted.**