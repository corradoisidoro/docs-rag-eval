import pytest
from pydantic import ValidationError

from evals.custom.metrics import score_context_precision, summarize
from evals.custom.schemas import JudgeScores

METRIC_FIELDS = (
    "answer_correctness",
    "answer_relevancy",
    "faithfulness",
    "context_precision",
    "context_recall",
)


def make_scores(**overrides: float | None) -> JudgeScores:
    values = dict.fromkeys(METRIC_FIELDS, 0.5)
    values.update(overrides)
    return JudgeScores(**values)


@pytest.mark.parametrize("metric", METRIC_FIELDS)
@pytest.mark.parametrize("value", [0.0, 1.0])
def test_each_metric_accepts_normalized_boundaries(metric, value):
    scores = make_scores(**{metric: value})

    assert getattr(scores, metric) == value


@pytest.mark.parametrize("metric", METRIC_FIELDS)
@pytest.mark.parametrize(
    "value",
    [-0.01, 1.01, float("-inf"), float("inf"), float("nan")],
)
def test_each_metric_rejects_out_of_range_or_non_finite_scores(metric, value):
    with pytest.raises(ValidationError):
        make_scores(**{metric: value})


@pytest.mark.parametrize("metric", METRIC_FIELDS)
def test_summary_averages_each_metric_independently(metric):
    summary = summarize(
        [
            make_scores(**{metric: 0.2}),
            make_scores(**{metric: 0.8}),
        ]
    )

    assert getattr(summary, metric) == pytest.approx(0.5)


def test_summary_contains_exactly_the_five_metrics():
    summary = summarize([make_scores()])

    assert set(summary.model_dump()) == set(METRIC_FIELDS)


def test_summary_preserves_single_case_boundary_scores():
    scores = make_scores(
        answer_correctness=0.0,
        answer_relevancy=1.0,
        faithfulness=0.0,
        context_precision=1.0,
        context_recall=0.0,
    )

    assert summarize([scores]).model_dump() == scores.model_dump()


def test_summary_rejects_empty_scores():
    with pytest.raises(ValueError, match="empty evaluation"):
        summarize([])


@pytest.mark.parametrize(
    ("chunk_relevance", "expected"),
    [
        ([], 0.0),
        ([False, False], 0.0),
        ([True, True, True], 1.0),
        ([True, False, True], pytest.approx(5 / 6)),
        ([False, True, False, True], pytest.approx(0.5)),
    ],
)
def test_context_precision_uses_chunk_relevance_and_rank(chunk_relevance, expected):
    assert score_context_precision(chunk_relevance) == expected


def test_context_recall_can_be_null_for_unanswerable_questions():
    scores = make_scores(context_recall=None)

    assert scores.context_recall is None


def test_context_recall_remains_bounded_when_answerable():
    assert make_scores(context_recall=0.0).context_recall == 0.0
    assert make_scores(context_recall=1.0).context_recall == 1.0


def test_summary_averages_only_defined_context_recall_values():
    summary = summarize(
        [
            make_scores(context_recall=0.25),
            make_scores(context_recall=None),
            make_scores(context_recall=0.75),
        ]
    )

    assert summary.context_recall == pytest.approx(0.5)


def test_summary_context_recall_is_null_when_all_cases_are_unanswerable():
    summary = summarize(
        [
            make_scores(context_recall=None),
            make_scores(context_recall=None),
        ]
    )

    assert summary.context_recall is None


def test_judge_scores_reject_unexpected_metric_fields():
    with pytest.raises(ValidationError):
        JudgeScores.model_validate(
            {
                **make_scores().model_dump(),
                "overall": 0.5,
            }
        )
