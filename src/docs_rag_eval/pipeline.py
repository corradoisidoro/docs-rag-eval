from docs_rag_eval.db import SQLiteStore
from docs_rag_eval.llm import ChatModel, Embedder
from docs_rag_eval.models import Answer, Citation
from docs_rag_eval.retrieve import retrieve

NOT_FOUND_ANSWER = "I could not find relevant information in the documents."
ABSTENTION_PREFIXES = (
    "i could not find relevant information",
    "i couldn't find relevant information",
    "the provided context does not contain",
    "the provided context doesn't contain",
    "the context does not contain",
    "the context doesn't contain",
    "the supplied context does not contain",
    "the supplied context doesn't contain",
    "the documents do not contain",
    "the documents don't contain",
    "the provided documents do not contain",
    "the provided documents don't contain",
    "i don't have enough information",
    "there is not enough information in the context",
    "there isn't enough information in the context",
)


def _is_abstention(answer: str) -> bool:
    normalized = answer.strip().casefold()
    return normalized.startswith(ABSTENTION_PREFIXES)


def ask(
    question: str,
    embedder: Embedder,
    chat_model: ChatModel,
    sqlite_store: SQLiteStore,
    *,
    min_score: float,
    top_k: int,
) -> Answer:
    """Retrieve relevant chunks and answer the question from them."""
    retrieved = retrieve(
        question,
        embedder,
        sqlite_store,
        min_score=min_score,
        top_k=top_k,
    )

    if not retrieved:
        return Answer(
            question=question,
            answer=NOT_FOUND_ANSWER,
            citations=[],
            retrieved_chunks=[],
        )

    context = "\n\n".join(item.chunk.text for item in retrieved)
    answer = chat_model.generate(question=question, context=context)

    if _is_abstention(answer):
        return Answer(
            question=question,
            answer=answer,
            citations=[],
            retrieved_chunks=retrieved,
        )

    citations = [
        Citation(source=item.chunk.source, chunk_id=item.chunk.id, score=item.score)
        for item in retrieved
    ]

    return Answer(
        question=question,
        answer=answer,
        citations=citations,
        retrieved_chunks=retrieved,
    )
