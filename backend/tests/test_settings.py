from pathlib import Path

import pytest
from pydantic import ValidationError

from trl.settings import CHECKOUT, Settings


def test_published_variable_names_and_empty_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRL_DB", "")
    monkeypatch.setenv("TRL_MODEL", "ollama")
    monkeypatch.setenv("TRL_OPERATOR_MODEL", "")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    settings = Settings()
    assert settings.database == CHECKOUT / ".local" / "state" / "transit.sqlite"
    assert settings.database.is_absolute()
    assert settings.model == "ollama"
    assert settings.operator_model is None
    assert settings.ollama_base_url == "http://ollama:11434"


def test_unknown_model_backend_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRL_MODEL", "hosted")
    with pytest.raises(ValidationError):
        Settings()


def test_paths_come_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRL_DB", str(tmp_path / "runs.sqlite"))
    monkeypatch.setenv("TRL_DATA", str(tmp_path))
    settings = Settings()
    assert settings.database == tmp_path / "runs.sqlite"
    assert settings.data == tmp_path
