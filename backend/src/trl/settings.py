"""Read every runtime setting from one validated place."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repository root when running from a checkout. Containers set TRL_DATA and TRL_DB.
CHECKOUT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = "qwen3.5:4b-q4_K_M"


class Settings(BaseSettings):
    """Environment variables keep their published names for compatibility."""

    # An empty variable, as in a copied .env.example, keeps the default.
    model_config = SettingsConfigDict(
        extra="ignore", frozen=True, populate_by_name=True, env_ignore_empty=True
    )

    database: Path = Field(
        default=CHECKOUT / ".local" / "state" / "transit.sqlite", validation_alias="TRL_DB"
    )
    data: Path = Field(default=CHECKOUT / "data", validation_alias="TRL_DATA")
    model: Literal["replay", "ollama"] = Field(default="replay", validation_alias="TRL_MODEL")
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default=DEFAULT_MODEL, validation_alias="TRL_OLLAMA_MODEL")
    operator_model: str | None = Field(default=None, validation_alias="TRL_OPERATOR_MODEL")
    otel_endpoint: str | None = Field(default=None, validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
