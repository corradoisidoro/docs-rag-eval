import pytest
from pydantic import ValidationError

from docs_rag_eval.config import PROJECT_ROOT, Settings

CONFIG_VALUES = {
    "llm_base_url": "https://provider.test/v1",
    "llm_api_key": "test-key",
    "llm_timeout_seconds": 1.5,
    "llm_reasoning_effort": "",
    "min_relevance_score": 0.25,
    "embedding_model": "embedding-model",
    "chat_model": "chat-model",
    "judge_model": "judge-model",
    "corpus_dir": "fixture-corpus",
    "database_path": "fixture-data/test-database.sqlite",
    "evaluation_dataset": "fixture-data/evaluation-input.json",
    "evaluation_reports": "fixture-data/reports",
    "evaluation_top_k": 3,
    "api_host": "127.0.0.2",
    "api_port": 8765,
}


def test_llm_timeout_seconds_accepts_positive_value():
    settings = Settings(_env_file=None, **CONFIG_VALUES)

    assert settings.llm_timeout_seconds == 1.5


def test_env_example_is_a_valid_configuration_template(monkeypatch):
    for name in CONFIG_VALUES:
        monkeypatch.delenv(name.upper(), raising=False)

    settings = Settings(_env_file=PROJECT_ROOT / ".env.example")

    assert settings.embedding_model
    assert settings.chat_model
    assert settings.judge_model
    assert settings.llm_base_url
    assert settings.evaluation_reports == PROJECT_ROOT / "evals" / "reports"


def test_settings_are_required_and_example_is_not_loaded_implicitly(monkeypatch):
    env_names = [name.upper() for name in CONFIG_VALUES]
    for name in env_names:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "llm_base_url" in str(error.value)
    assert "judge_model" in str(error.value)


def test_environment_variables_override_env_file(tmp_path, monkeypatch):
    for name in CONFIG_VALUES:
        monkeypatch.delenv(name.upper(), raising=False)

    local_file = tmp_path / ".env"
    local_file.write_text(
        "\n".join(f"{name.upper()}={value}" for name, value in CONFIG_VALUES.items()),
        encoding="utf-8",
    )
    monkeypatch.setenv("JUDGE_MODEL", "environment-model")

    settings = Settings(_env_file=local_file)

    assert settings.judge_model == "environment-model"
    assert settings.chat_model == CONFIG_VALUES["chat_model"]


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_llm_timeout_seconds_rejects_invalid_value(value: float):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**CONFIG_VALUES, "llm_timeout_seconds": value})


def test_evaluation_top_k_rejects_values_above_api_limit():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**CONFIG_VALUES, "evaluation_top_k": 21})
