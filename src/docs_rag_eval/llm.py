from typing import Protocol

from openai import OpenAI

SYSTEM_PROMPT = (
    "Answer the question using only the supplied context. "
    "If the context does not contain the answer, say so."
)


class Embedder(Protocol):
    embedding_model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChatModel(Protocol):
    def generate(self, question: str, context: str) -> str: ...


class OpenAICompatibleModels:
    """Embeddings and chat through any OpenAI-compatible API (e.g. Ollama)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        timeout: float = 120.0,
        reasoning_effort: str | None = None,
    ) -> None:
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.reasoning_effort = reasoning_effort

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def generate(self, question: str, context: str) -> str:
        # Sent only when configured, so providers that reject it still work.
        extra_body = (
            {"reasoning_effort": self.reasoning_effort}
            if self.reasoning_effort
            else None
        )

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion:\n{question}",
                },
            ],
            extra_body=extra_body,
        )
        return response.choices[0].message.content or ""
