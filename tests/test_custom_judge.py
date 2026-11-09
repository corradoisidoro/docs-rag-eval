import json
import os
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from docs_rag_eval.api.main import create_app
from docs_rag_eval.config import PROJECT_ROOT, Settings, settings
from docs_rag_eval.models import Answer, Chunk, RetrievedChunk
from evals.custom import judge as judge_module
from evals.custom.judge import (
    LocalRagPipeline,
    OpenAICompatibleJudge,
    discover_datasets,
    evaluate_cases,
    load_cases,
    report_path,
)
from evals.custom.metrics import summarize
from evals.custom.schemas import (
    EvaluationCase,
    EvaluationInput,
    JudgeAssessment,
    JudgeResponse,
    JudgeScores,
)


def make_case() -> EvaluationCase:
    return EvaluationCase(
        question="What is RAG?",
        answer="RAG combines retrieval with generation.",
        expected_answer=(
            "RAG retrieves external information and provides it as context to an LLM."
        ),
        contexts=["RAG combines information retrieval with language models."],
        should_answer=True,
    )


class FakeRagPipeline:
    def __init__(self) -> None:
        self.questions: list[str] = []

    def ask(self, question: str) -> Answer:
        self.questions.append(question)
        return Answer(
            question=question,
            answer="RAG retrieves information.",
            citations=[],
            retrieved_chunks=[
                RetrievedChunk(
                    chunk=Chunk(
                        id="rag.md:0",
                        source="rag.md",
                        text="RAG retrieves relevant external information.",
                    ),
                    score=0.9,
                )
            ],
        )


class FakeJudge:
    def __init__(self, assessment: JudgeAssessment) -> None:
        self.assessment = assessment
        self.calls = 0

    def evaluate(self, case: EvaluationCase) -> JudgeAssessment:
        self.calls += 1
        return self.assessment


def test_load_cases_validates_dataset(tmp_path):
    dataset = tmp_path / "cases.json"
    case = EvaluationInput(
        question="What is RAG?",
        expected_answer="RAG retrieves information.",
        should_answer=True,
        expected_sources=["rag-fundamentals.md"],
    )
    dataset.write_text(json.dumps([case.model_dump()]), encoding="utf-8")

    assert load_cases(dataset) == [case]


def test_load_cases_rejects_invalid_case(tmp_path):
    dataset = tmp_path / "cases.json"
    dataset.write_text('[{"question": "missing fields"}]', encoding="utf-8")

    with pytest.raises(ValidationError):
        load_cases(dataset)


def test_load_cases_rejects_unexpected_retrieval_annotations(tmp_path):
    dataset = tmp_path / "cases.json"
    dataset.write_text(
        '[{"question": "question", "expected_answer": "answer", '
        '"should_answer": true, "expected_sources": ["source.md"], '
        '"unexpected_annotation": true}]',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_cases(dataset)


def test_bundled_dataset_cases_and_sources_exist_in_corpus():
    dataset_path = PROJECT_ROOT / "evals" / "datasets" / "test_cases.json"
    corpus_sources = {path.name for path in (PROJECT_ROOT / "corpus").rglob("*.md")}

    cases = load_cases(dataset_path)

    assert len(cases) == 12
    assert all(case.question and case.expected_answer for case in cases)
    assert any(case.should_answer for case in cases)
    assert any(not case.should_answer for case in cases)
    assert all(
        source in corpus_sources for case in cases for source in case.expected_sources
    )
    assert all(
        bool(case.expected_sources) if case.should_answer else not case.expected_sources
        for case in cases
    )


def test_evaluation_input_accepts_answerable_sources():
    case = EvaluationInput(
        question="What is RAG?",
        expected_answer="RAG retrieves information.",
        should_answer=True,
        expected_sources=["rag-fundamentals.md"],
    )

    assert case.expected_sources == ["rag-fundamentals.md"]


def test_evaluation_input_accepts_unanswerable_case_without_sources():
    case = EvaluationInput(
        question="Who is Acme's CEO?",
        expected_answer="The corpus does not say.",
        should_answer=False,
        expected_sources=[],
    )

    assert case.expected_sources == []


def test_evaluation_input_rejects_answerable_case_without_sources():
    with pytest.raises(ValidationError, match="Answerable cases must specify"):
        EvaluationInput(
            question="What is RAG?",
            expected_answer="RAG retrieves information.",
            should_answer=True,
        )


def test_evaluation_input_rejects_unanswerable_case_with_sources():
    with pytest.raises(ValidationError, match="must not specify expected sources"):
        EvaluationInput(
            question="Who is Acme's CEO?",
            expected_answer="The corpus does not say.",
            should_answer=False,
            expected_sources=["acme-engineering-handbook.md"],
        )


def test_evaluation_input_rejects_duplicate_sources():
    with pytest.raises(ValidationError, match="must be unique"):
        EvaluationInput(
            question="What is RAG?",
            expected_answer="RAG retrieves information.",
            should_answer=True,
            expected_sources=["rag-fundamentals.md", "rag-fundamentals.md"],
        )


def test_evaluation_input_rejects_non_string_source_filenames():
    with pytest.raises(ValidationError):
        EvaluationInput(
            question="What is RAG?",
            expected_answer="RAG retrieves information.",
            should_answer=True,
            expected_sources=[42],
        )


@pytest.mark.parametrize("filename", ["", " ", "   "])
def test_evaluation_input_rejects_empty_source_filenames(filename):
    with pytest.raises(ValidationError, match="must not be empty"):
        EvaluationInput(
            question="What is RAG?",
            expected_answer="RAG retrieves information.",
            should_answer=True,
            expected_sources=[filename],
        )


def test_load_cases_preserves_expected_sources(tmp_path):
    dataset = tmp_path / "cases.json"
    dataset.write_text(
        '[{"question": "What is RAG?", '
        '"expected_answer": "RAG retrieves information.", '
        '"should_answer": true, '
        '"expected_sources": ["rag-fundamentals.md"]}]',
        encoding="utf-8",
    )

    cases = load_cases(dataset)

    assert cases[0].expected_sources == ["rag-fundamentals.md"]


def test_discover_datasets_accepts_single_json_file(tmp_path):
    dataset = tmp_path / "cases.json"
    dataset.write_text("[]", encoding="utf-8")

    assert discover_datasets(dataset) == [dataset]


def test_discover_datasets_returns_sorted_json_files_from_directory(tmp_path):
    (tmp_path / "second.json").write_text("[]", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / "first.json").write_text("[]", encoding="utf-8")

    assert discover_datasets(tmp_path) == [
        tmp_path / "first.json",
        tmp_path / "second.json",
    ]


def test_discover_datasets_rejects_empty_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match="No JSON evaluation datasets"):
        discover_datasets(tmp_path)


def test_discover_datasets_rejects_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        discover_datasets(tmp_path / "missing")


def test_report_path_uses_dataset_stem(tmp_path):
    assert report_path(tmp_path / "my-dataset.json", tmp_path / "reports") == (
        tmp_path / "reports" / "my-dataset-report.json"
    )


def patch_judge_cli(monkeypatch, dataset_dir, reports_dir):
    config = settings.model_copy(
        update={
            "evaluation_dataset": dataset_dir,
            "evaluation_reports": reports_dir,
        }
    )
    monkeypatch.setattr(judge_module, "settings", config)
    monkeypatch.setattr(
        judge_module, "OpenAICompatibleModels", lambda **kwargs: object()
    )
    monkeypatch.setattr(judge_module, "SQLiteStore", lambda path: object())
    monkeypatch.setattr(judge_module, "load_documents", lambda path: [])
    monkeypatch.setattr(judge_module, "ingest_documents", lambda **kwargs: None)
    monkeypatch.setattr(
        judge_module,
        "LocalRagPipeline",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        judge_module,
        "OpenAICompatibleJudge",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        judge_module,
        "load_cases",
        lambda path: [path.name],
    )


def test_main_processes_all_datasets_and_writes_reports_to_configured_directory(
    tmp_path,
    monkeypatch,
):
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    (dataset_dir / "second.json").write_text("[]", encoding="utf-8")
    (dataset_dir / "first.json").write_text("[]", encoding="utf-8")
    reports_dir = tmp_path / "reports"
    evaluated = []

    class FakeReport:
        def __init__(self, dataset_name: str) -> None:
            self.dataset_name = dataset_name

        def model_dump_json(self, *, indent: int) -> str:
            return json.dumps({"dataset": self.dataset_name})

    def fake_evaluate_cases(cases, rag_pipeline, judge):
        evaluated.extend(cases)
        return FakeReport(cases[0])

    patch_judge_cli(monkeypatch, dataset_dir, reports_dir)
    monkeypatch.setattr(judge_module, "evaluate_cases", fake_evaluate_cases)
    monkeypatch.setattr(judge_module.sys, "argv", ["evals.custom.judge"])

    judge_module.main()

    assert evaluated == ["first.json", "second.json"]
    assert json.loads(
        (reports_dir / "first-report.json").read_text(encoding="utf-8")
    ) == {"dataset": "first.json"}
    assert json.loads(
        (reports_dir / "second-report.json").read_text(encoding="utf-8")
    ) == {"dataset": "second.json"}


def test_main_rejects_file_output_for_multiple_datasets(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    (dataset_dir / "first.json").write_text("[]", encoding="utf-8")
    (dataset_dir / "second.json").write_text("[]", encoding="utf-8")
    patch_judge_cli(monkeypatch, dataset_dir, tmp_path / "reports")
    monkeypatch.setattr(
        judge_module.sys,
        "argv",
        ["evals.custom.judge", "--output", str(tmp_path / "report.json")],
    )

    with pytest.raises(SystemExit, match="2"):
        judge_module.main()


def test_judge_response_rejects_unexpected_metrics():
    with pytest.raises(ValidationError):
        JudgeResponse.model_validate_json(
            '{"answer_correctness": 0.5, "answer_relevancy": 0.5, '
            '"faithfulness": 0.5, "context_recall": 0.5, '
            '"chunk_relevance": [], "abstained": false}'
        )


def test_openai_compatible_judge_requests_structured_json_and_validates_scores(
    monkeypatch,
):
    scores_json = (
        '{"answer_correctness": 0.8, "answer_relevancy": 0.9, '
        '"faithfulness": 0.7, "context_recall": 0.5, '
        '"chunk_relevance": [true]}'
    )

    class FakeCompletions:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=scores_json),
                    )
                ],
            )

    completions = FakeCompletions()
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.chat = fake_client.chat

    monkeypatch.setattr(judge_module, "OpenAI", FakeOpenAI)
    evaluator = OpenAICompatibleJudge(
        base_url=settings.llm_base_url,
        api_key="test",
        model=settings.judge_model,
        timeout=settings.llm_timeout_seconds,
        reasoning_effort="none",
    )

    assessment = evaluator.evaluate(make_case())

    assert assessment == JudgeAssessment(
        answer_correctness=0.8,
        answer_relevancy=0.9,
        faithfulness=0.7,
        context_precision=1.0,
        context_recall=0.5,
    )
    assert completions.kwargs["model"] == settings.judge_model
    response_format = completions.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "judge_response"
    response_schema = response_format["json_schema"]["schema"]
    assert response_schema["properties"]["chunk_relevance"]["minItems"] == 1
    assert response_schema["properties"]["chunk_relevance"]["maxItems"] == 1
    assert response_schema["properties"]["context_recall"]["type"] == "number"
    assert completions.kwargs["extra_body"] == {"reasoning_effort": "none"}
    judge_input = completions.kwargs["messages"][1]["content"]
    assert set(json.loads(judge_input)) == {
        "question",
        "answer",
        "expected_answer",
        "contexts",
        "should_answer",
    }


def test_local_rag_pipeline_calls_pipeline_ask(monkeypatch):
    models = object()
    sqlite_store = object()
    answer = Answer(
        question="What is RAG?",
        answer="RAG retrieves information.",
        citations=[],
        retrieved_chunks=[],
    )
    calls = []

    def fake_ask_pipeline(**kwargs):
        calls.append(kwargs)
        return answer

    monkeypatch.setattr(judge_module, "ask_pipeline", fake_ask_pipeline)
    rag_pipeline = LocalRagPipeline(
        models,
        sqlite_store,
        min_score=0.25,
        top_k=3,
    )

    assert rag_pipeline.ask("What is RAG?") == answer
    assert calls == [
        {
            "question": "What is RAG?",
            "embedder": models,
            "chat_model": models,
            "sqlite_store": sqlite_store,
            "min_score": 0.25,
            "top_k": 3,
        }
    ]


def test_openai_compatible_judge_rejects_invalid_score_response(monkeypatch):
    class FakeCompletions:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"answer_correctness": 1.1, '
                            '"answer_relevancy": 0.8, "faithfulness": 0.7, '
                            '"context_recall": 0.5, "chunk_relevance": [true]}'
                        )
                    )
                ]
            )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
    )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = fake_client.chat

    monkeypatch.setattr(judge_module, "OpenAI", FakeOpenAI)
    evaluator = OpenAICompatibleJudge(
        base_url=settings.llm_base_url,
        api_key="test",
        model=settings.judge_model,
        timeout=settings.llm_timeout_seconds,
        reasoning_effort="",
    )

    with pytest.raises(ValidationError):
        evaluator.evaluate(make_case())
    assert fake_client.chat.completions.calls == 2


def test_openai_compatible_judge_retries_invalid_scores(monkeypatch):
    responses = iter(
        [
            (
                '{"answer_correctness": -0.1, "answer_relevancy": 0.8, '
                '"faithfulness": 0.7, "context_recall": 0.5, '
                '"chunk_relevance": [true]}'
            ),
            (
                '{"answer_correctness": 0.2, "answer_relevancy": 0.8, '
                '"faithfulness": 0.7, "context_recall": 0.5, '
                '"chunk_relevance": [true]}'
            ),
        ]
    )

    class FakeCompletions:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=next(responses)),
                    )
                ],
            )

    completions = FakeCompletions()
    monkeypatch.setattr(
        judge_module,
        "OpenAI",
        lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    evaluator = OpenAICompatibleJudge(
        base_url=settings.llm_base_url,
        api_key="test",
        model=settings.judge_model,
        timeout=settings.llm_timeout_seconds,
        reasoning_effort="",
    )

    assessment = evaluator.evaluate(make_case())

    assert completions.calls == 2
    assert assessment.answer_correctness == 0.2


@pytest.mark.parametrize(
    ("case", "first_response", "expected_context_precision", "expected_recall"),
    [
        (
            make_case(),
            '{"answer_correctness": 0.8, "answer_relevancy": 0.9, '
            '"faithfulness": 0.7, "context_recall": 0.5, '
            '"chunk_relevance": []}',
            1.0,
            0.5,
        ),
        (
            make_case().model_copy(update={"should_answer": False}),
            '{"answer_correctness": 0.8, "answer_relevancy": 0.9, '
            '"faithfulness": 0.7, "context_recall": 0.5, '
            '"chunk_relevance": [true]}',
            1.0,
            None,
        ),
    ],
)
def test_judge_retries_when_chunk_labels_or_unanswerable_recall_are_invalid(
    monkeypatch,
    case,
    first_response,
    expected_context_precision,
    expected_recall,
):
    correct_recall = "0.5" if case.should_answer else "null"
    response = (
        '{"answer_correctness": 0.8, "answer_relevancy": 0.9, '
        f'"faithfulness": 0.7, "context_recall": {correct_recall}, '
        '"chunk_relevance": [true]}'
    )
    completions = SimpleNamespace(calls=0, response_formats=[])

    def create(**kwargs):
        completions.calls += 1
        completions.response_formats.append(kwargs["response_format"])
        content = first_response if completions.calls == 1 else response
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    monkeypatch.setattr(
        judge_module,
        "OpenAI",
        lambda **kwargs: SimpleNamespace(chat=fake_client.chat),
    )
    evaluator = OpenAICompatibleJudge(
        base_url=settings.llm_base_url,
        api_key="test",
        model=settings.judge_model,
        timeout=settings.llm_timeout_seconds,
        reasoning_effort="",
    )

    assessment = evaluator.evaluate(case)

    assert completions.calls == 2
    assert assessment.context_precision == expected_context_precision
    assert assessment.context_recall == expected_recall
    response_schema = completions.response_formats[0]["json_schema"]["schema"]
    expected_recall_type = "number" if case.should_answer else "null"
    assert response_schema["properties"]["context_recall"]["type"] == (
        expected_recall_type
    )
    assert response_schema["properties"]["chunk_relevance"]["minItems"] == len(
        case.contexts
    )
    assert response_schema["properties"]["chunk_relevance"]["maxItems"] == len(
        case.contexts
    )


@pytest.mark.parametrize(
    "metric",
    ["answer_correctness", "answer_relevancy", "faithfulness", "context_precision"],
)
@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_judge_scores_reject_values_outside_zero_to_one(metric, value):
    with pytest.raises(ValidationError):
        JudgeScores(
            **{
                "answer_correctness": 0.5,
                "answer_relevancy": 0.5,
                "faithfulness": 0.5,
                "context_precision": 0.5,
                "context_recall": 0.5,
                metric: value,
            }
        )


def test_judge_scores_accept_zero_and_one():
    scores = JudgeScores(
        answer_correctness=0.0,
        answer_relevancy=1.0,
        faithfulness=0.0,
        context_precision=1.0,
        context_recall=0.0,
    )

    assert scores.answer_correctness == 0.0
    assert scores.answer_relevancy == 1.0


def test_judge_scores_reject_extra_fields():
    with pytest.raises(ValidationError):
        JudgeScores.model_validate(
            {
                "answer_correctness": 0.5,
                "answer_relevancy": 0.5,
                "faithfulness": 0.5,
                "context_precision": 0.5,
                "context_recall": 0.5,
                "abstained": False,
            }
        )


def test_evaluate_cases_returns_results_and_averages():
    cases = [
        EvaluationInput(
            question="What is RAG?",
            expected_answer="RAG retrieves information.",
            should_answer=True,
            expected_sources=["rag-fundamentals.md"],
        )
        for _ in range(2)
    ]
    scores = JudgeAssessment(
        answer_correctness=0.8,
        answer_relevancy=0.9,
        faithfulness=0.7,
        context_precision=0.6,
        context_recall=0.5,
    )
    judge = FakeJudge(scores)
    rag_client = FakeRagPipeline()

    report = evaluate_cases(cases, rag_client, judge)

    assert judge.calls == 2
    assert rag_client.questions == [case.question for case in cases]
    assert report.metrics.answer_correctness == 0.8
    assert report.metrics.answer_relevancy == 0.9
    assert report.metrics.faithfulness == 0.7
    assert report.metrics.context_precision == 0.6
    assert report.metrics.context_recall == 0.5
    expected_metrics = {
        "answer_correctness",
        "answer_relevancy",
        "faithfulness",
        "context_precision",
        "context_recall",
    }
    assert set(report.metrics.model_dump()) == expected_metrics
    for result, evaluation_input in zip(report.results, cases, strict=True):
        assert result.case.question == evaluation_input.question
        assert result.case.answer == "RAG retrieves information."
        assert result.scores == scores
        assert set(result.scores.model_dump()) == expected_metrics


def test_evaluate_cases_returns_null_context_recall_for_unanswerable_case():
    case = EvaluationInput(
        question="What is the vacation policy?",
        expected_answer="The documents do not specify a vacation policy.",
        should_answer=False,
        expected_sources=[],
    )
    scores = JudgeAssessment(
        answer_correctness=1.0,
        answer_relevancy=1.0,
        faithfulness=1.0,
        context_precision=0.0,
        context_recall=None,
    )

    report = evaluate_cases([case], FakeRagPipeline(), FakeJudge(scores))

    assert report.results[0].case.should_answer is False
    assert report.results[0].scores.context_recall is None
    assert report.metrics.context_recall is None


def test_evaluate_cases_rejects_empty_dataset():
    with pytest.raises(ValueError, match="contains no cases"):
        evaluate_cases(
            [],
            FakeRagPipeline(),
            FakeJudge(
                JudgeAssessment(
                    answer_correctness=0.8,
                    answer_relevancy=0.8,
                    faithfulness=0.8,
                    context_precision=0.8,
                    context_recall=0.8,
                )
            ),
        )


def test_summarize_rejects_empty_scores():
    with pytest.raises(ValueError, match="empty evaluation"):
        summarize([])


@pytest.mark.integration
def test_live_rag_ask_and_judge_use_configured_local_models(tmp_path, monkeypatch):
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        pytest.skip("Copy .env.example to .env to run the live RAG integration test.")

    config_keys = (
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_TIMEOUT_SECONDS",
        "LLM_REASONING_EFFORT",
        "MIN_RELEVANCE_SCORE",
        "EMBEDDING_MODEL",
        "CHAT_MODEL",
        "JUDGE_MODEL",
        "CORPUS_DIR",
        "DATABASE_PATH",
        "EVALUATION_DATASET",
        "EVALUATION_TOP_K",
        "API_HOST",
        "API_PORT",
    )
    for key in config_keys:
        monkeypatch.delenv(key, raising=False)

    live_settings = Settings(
        _env_file=env_file,
        database_path=tmp_path / "live-rag.db",
    )
    host = urlparse(live_settings.llm_base_url).hostname
    if host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("The live integration test only sends data to a local provider.")

    dataset_path = discover_datasets(live_settings.evaluation_dataset)[0]
    dataset_cases = load_cases(dataset_path)
    answerable_cases = [case for case in dataset_cases if case.should_answer]
    unanswerable_case = next(
        (case for case in dataset_cases if not case.should_answer),
        None,
    )
    case_limit = int(os.environ.get("CUSTOM_JUDGE_CASE_LIMIT", "1"))
    if not 1 <= case_limit <= len(answerable_cases):
        raise ValueError(
            "CUSTOM_JUDGE_CASE_LIMIT must be between 1 and "
            f"{len(answerable_cases)} answerable cases."
        )
    cases = answerable_cases[:case_limit]
    if unanswerable_case is not None:
        cases.append(unanswerable_case)

    with TestClient(create_app(live_settings)) as client:
        ingest_response = client.post("/ingest")
        assert ingest_response.status_code == 200, ingest_response.text

        class ApiRagPipeline:
            def ask(self, question: str) -> Answer:
                ask_response = client.post(
                    "/ask",
                    json={
                        "question": question,
                        "top_k": live_settings.evaluation_top_k,
                    },
                )
                assert ask_response.status_code == 200, ask_response.text
                payload = ask_response.json()
                return Answer(
                    question=payload["question"],
                    answer=payload["answer"],
                    citations=[],
                    retrieved_chunks=[
                        RetrievedChunk(
                            chunk=Chunk(
                                id=item["chunk_id"],
                                source=item["source"],
                                text=item["text"],
                            ),
                            score=item["score"],
                        )
                        for item in payload["retrieved_chunks"]
                    ],
                )

        report = evaluate_cases(
            cases,
            ApiRagPipeline(),
            OpenAICompatibleJudge(
                base_url=live_settings.llm_base_url,
                api_key=live_settings.llm_api_key,
                model=live_settings.judge_model,
                timeout=live_settings.llm_timeout_seconds,
                reasoning_effort=live_settings.llm_reasoning_effort,
            ),
        )

    assert all(result.case.answer.strip() for result in report.results)
    assert any(result.case.should_answer for result in report.results)
    assert any(not result.case.should_answer for result in report.results)
    assert all(
        (
            getattr(result.scores, metric) is None
            and metric == "context_recall"
            and not result.case.should_answer
        )
        or (
            getattr(result.scores, metric) is not None
            and 0.0 <= getattr(result.scores, metric) <= 1.0
            and (metric != "context_recall" or result.case.should_answer)
        )
        for result in report.results
        for metric in (
            "answer_correctness",
            "answer_relevancy",
            "faithfulness",
            "context_precision",
            "context_recall",
        )
    )
    print(
        json.dumps(
            {
                "metrics": report.metrics.model_dump(),
                "results": [
                    {
                        "question": result.case.question,
                        "answer": result.case.answer,
                        "scores": result.scores.model_dump(),
                    }
                    for result in report.results
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
