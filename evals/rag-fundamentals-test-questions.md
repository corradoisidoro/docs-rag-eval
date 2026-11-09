# Test questions for `rag-fundamentals.md`

Use with `POST /ask`. The corpus is one short file, so every citation has the
same `source` (`rag-fundamentals.md`). Tell chunks apart by `chunk_id`
(`rag-fundamentals.md:0`, `:1`, ...), and check the answer text itself.

## A. Single-fact lookups (should answer)

| # | Question | Expected answer | Section |
|---|---|---|---|
| 1 | What is Retrieval-Augmented Generation? | An architecture that combines information retrieval with language generation | RAG |
| 2 | What are the two main stages of a basic RAG pipeline? | Indexing; retrieval and generation | RAG |
| 3 | Does RAG require retraining the model when the knowledge base changes? | No | RAG |
| 4 | What is an embedding? | A numerical representation of text | Embeddings |
| 5 | Which method is commonly used to measure similarity between embedding vectors? | Cosine similarity | Embeddings |
| 6 | What does the top-k parameter control? | How many of the most relevant chunks are returned | Retrieval |
| 7 | If top-k is 3, what does the system return? | The three chunks with the highest similarity scores | Retrieval |
| 8 | What is document retrieval? | Finding relevant information from a collection of indexed documents | Retrieval |
| 9 | When is each document chunk converted into an embedding? | During ingestion | Embeddings |
| 10 | Where are chunk embeddings stored in a vector-based retrieval system? | In a vector store | Retrieval |

## B. Reworded questions (tests semantic matching, not keywords)

| # | Question | Expected answer |
|---|---|---|
| 11 | What kinds of information can RAG help a model answer questions about? | Private, domain-specific, or frequently updated information |
| 12 | Why can embeddings find results that keyword search misses? | They search by semantic meaning, not only exact keyword matches |
| 13 | How does the system decide which chunks relate to my question? | It compares the question embedding with the stored chunk embeddings |
| 14 | What happens to the retrieved chunks afterwards? | They are passed to the language model as context |
| 15 | Do two sentences with the same meaning get similar vectors? | Yes, texts with similar meanings should have similar embeddings |

## C. Multi-section questions (tests combining chunks)

| # | Question | A good answer combines |
|---|---|---|
| 16 | Walk me through the whole flow from a document to an answer. | Load, split, embed and store; embed the question, compare, retrieve top-k, pass to the model |
| 17 | At which two moments are embeddings created? | Chunks during ingestion; the question during retrieval |
| 18 | How do embeddings, chunks and top-k work together in retrieval? | Chunks are embedded and stored; the question is embedded and compared; top-k limits how many are returned |

## D. Should NOT be answerable (tests the relevance threshold)

The expected reply is "I could not find relevant information in the documents."
or a statement that the context does not contain the answer.

| # | Question | Why it should fail |
|---|---|---|
| 19 | What chunk size should I use? | Chunk size is never specified |
| 20 | Which vector database should I use? | No product is named |
| 21 | What is the formula for cosine similarity? | Only mentioned by name |
| 22 | What is reranking, and should I use it? | Not covered |
| 23 | Which embedding model does this system use? | Not stated in the documents |
| 24 | Who invented RAG? | Not covered |

## Notes

- The text is about 2,300 characters, so it becomes only 3 chunks.
  With `top_k` of 3 or more, nearly every chunk is retrieved for every question,
  so retrieval is barely tested. Use `top_k: 1` for a stricter check.
- This content is general knowledge, so a chat model could answer many of these
  without retrieval. Questions 19–24 are the real test that it is using the
  documents. Pair this file with the Acme handbook for a stronger test.
- If #19–#24 get confident answers, raise `MIN_RELEVANCE_SCORE`. If #1–#18
  return "could not find", lower it.

## Quick check (PowerShell)

```powershell
curl.exe -X POST http://<API_HOST>:<API_PORT>/ingest

curl.exe -X POST http://<API_HOST>:<API_PORT>/ask `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"What does the top-k parameter control?\", \"top_k\": 1}'
```

Replace `<API_HOST>` and `<API_PORT>` with the values from `.env`.
