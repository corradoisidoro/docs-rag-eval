"""Aggregation of the five normalized LLM-as-a-judge metrics."""

from statistics import fmean

from evals.custom.schemas import EvaluationMetrics, JudgeScores


def score_context_precision(chunk_relevance: list[bool]) -> float:
    """Calculate average precision over chunk-level relevance labels in rank order."""
    relevant_count = sum(chunk_relevance)
    if not relevant_count:
        return 0.0

    relevant_seen = 0
    precision_sum = 0.0
    for rank, is_relevant in enumerate(chunk_relevance, start=1):
        if is_relevant:
            relevant_seen += 1
            precision_sum += relevant_seen / rank

    return precision_sum / relevant_count


def summarize(scores: list[JudgeScores]) -> EvaluationMetrics:
    """Return the mean score for each metric, excluding null context recall."""
    if not scores:
        raise ValueError("Cannot summarize an empty evaluation.")

    context_recalls = [
        score.context_recall for score in scores if score.context_recall is not None
    ]
    return EvaluationMetrics(
        answer_correctness=fmean(score.answer_correctness for score in scores),
        answer_relevancy=fmean(score.answer_relevancy for score in scores),
        faithfulness=fmean(score.faithfulness for score in scores),
        context_precision=fmean(score.context_precision for score in scores),
        context_recall=fmean(context_recalls) if context_recalls else None,
    )
