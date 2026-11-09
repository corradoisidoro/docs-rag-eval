"""Input and output models for five-metric LLM-as-a-judge evaluations."""

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)


class EvaluationCase(BaseModel):
    """A pipeline answer and its reference material."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    contexts: list[str] = Field(default_factory=list)
    should_answer: bool


class EvaluationInput(BaseModel):
    """Question and reference answer for one evaluation case."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    should_answer: bool
    expected_sources: list[str] = Field(default_factory=list)

    @field_validator("expected_sources")
    @classmethod
    def validate_expected_sources(cls, sources: list[str]) -> list[str]:
        if any(not source.strip() for source in sources):
            raise ValueError("Expected source filenames must not be empty.")
        if len(sources) != len(set(sources)):
            raise ValueError("Expected source filenames must be unique.")
        return sources

    @model_validator(mode="after")
    def validate_expected_sources_for_answerability(self) -> Self:
        if self.should_answer and not self.expected_sources:
            raise ValueError("Answerable cases must specify expected sources.")
        if not self.should_answer and self.expected_sources:
            raise ValueError("Unanswerable cases must not specify expected sources.")
        return self


class JudgeScores(BaseModel):
    """The five normalized LLM-as-a-judge scores."""

    model_config = ConfigDict(extra="forbid")

    answer_correctness: float = Field(ge=0, le=1, allow_inf_nan=False)
    answer_relevancy: float = Field(ge=0, le=1, allow_inf_nan=False)
    faithfulness: float = Field(ge=0, le=1, allow_inf_nan=False)
    context_precision: float = Field(ge=0, le=1, allow_inf_nan=False)
    context_recall: float | None = Field(
        ge=0,
        le=1,
        allow_inf_nan=False,
    )


class JudgeResponse(BaseModel):
    """Raw judge output including per-chunk relevance labels."""

    model_config = ConfigDict(extra="forbid")

    answer_correctness: float = Field(ge=0, le=1, allow_inf_nan=False)
    answer_relevancy: float = Field(ge=0, le=1, allow_inf_nan=False)
    faithfulness: float = Field(ge=0, le=1, allow_inf_nan=False)
    context_recall: float | None = Field(
        ge=0,
        le=1,
        allow_inf_nan=False,
    )
    chunk_relevance: list[StrictBool]


class JudgeAssessment(JudgeScores):
    """The five normalized metric scores returned by the evaluator."""


class EvaluationResult(BaseModel):
    """One evaluated answer and its five scores."""

    model_config = ConfigDict(extra="forbid")

    case: EvaluationCase
    scores: JudgeScores


class EvaluationMetrics(BaseModel):
    """Mean of the five normalized judge metrics across evaluated cases."""

    model_config = ConfigDict(extra="forbid")

    answer_correctness: float = Field(ge=0, le=1, allow_inf_nan=False)
    answer_relevancy: float = Field(ge=0, le=1, allow_inf_nan=False)
    faithfulness: float = Field(ge=0, le=1, allow_inf_nan=False)
    context_precision: float = Field(ge=0, le=1, allow_inf_nan=False)
    context_recall: float | None = Field(
        ge=0,
        le=1,
        allow_inf_nan=False,
    )


class EvaluationReport(BaseModel):
    """Per-case five-metric scores and their aggregate means."""

    model_config = ConfigDict(extra="forbid")

    results: list[EvaluationResult]
    metrics: EvaluationMetrics
