import pytest
from pydantic import ValidationError

from docs_rag_eval.config import Settings


def test_llm_timeout_seconds_accepts_positive_value():
    settings = Settings(llm_timeout_seconds=1.5)

    assert settings.llm_timeout_seconds == 1.5


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_llm_timeout_seconds_rejects_invalid_value(value: float):
    with pytest.raises(ValidationError):
        Settings(llm_timeout_seconds=value)
