from types import SimpleNamespace

from docs_rag_eval.llm import OpenAICompatibleModels


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="answer")),
            ]
        )


def make_models(
    reasoning_effort: str,
) -> tuple[OpenAICompatibleModels, FakeCompletions]:
    models = OpenAICompatibleModels(
        base_url="http://localhost:1/v1",
        api_key="test",
        chat_model="test-model",
        embedding_model="test-embedding",
        timeout=1.0,
        reasoning_effort=reasoning_effort,
    )
    completions = FakeCompletions()
    models.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    return models, completions


def test_generate_forwards_reasoning_effort():
    models, completions = make_models("none")

    assert models.generate("question", "context") == "answer"
    assert completions.kwargs["extra_body"] == {"reasoning_effort": "none"}


def test_generate_omits_reasoning_effort_when_empty():
    models, completions = make_models("")

    models.generate("question", "context")

    assert completions.kwargs["extra_body"] is None


def test_generate_puts_question_and_context_in_the_prompt():
    models, completions = make_models("")

    models.generate("What is X?", "X is a letter.")

    user_message = completions.kwargs["messages"][-1]["content"]
    assert "What is X?" in user_message
    assert "X is a letter." in user_message


def test_embed_forwards_model_and_texts():
    models = OpenAICompatibleModels(
        base_url="http://localhost:1/v1",
        api_key="test",
        chat_model="test-model",
        embedding_model="test-embedding",
        timeout=1.0,
        reasoning_effort="",
    )

    class FakeEmbeddings:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                data=[
                    SimpleNamespace(embedding=[1.0, 0.0]),
                    SimpleNamespace(embedding=[0.0, 1.0]),
                ]
            )

    embeddings = FakeEmbeddings()
    models.client = SimpleNamespace(
        embeddings=embeddings,
    )

    result = models.embed(["first text", "second text"])

    assert embeddings.kwargs == {
        "model": "test-embedding",
        "input": ["first text", "second text"],
    }
    assert result == [[1.0, 0.0], [0.0, 1.0]]


def test_generate_returns_empty_string_when_response_content_is_none():
    models, completions = make_models("")

    completions.create = lambda **kwargs: SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=None)),
        ]
    )

    assert models.generate("question", "context") == ""
