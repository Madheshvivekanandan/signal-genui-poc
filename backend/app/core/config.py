"""Every environment value this service reads, in one typed place.

Nothing else in the package calls `os.getenv`. That is the point: the previous
arrangement read `OPENAI_MODEL` at import time in the agent and `ALLOWED_ORIGINS`
at import time in the app module, which meant the configuration was fixed by
import order and could not be varied in a test without reloading modules.

`get_settings` is cached, so the environment is read once per process, and a test
can clear the cache to substitute its own.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment or `backend/.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # `SecretStr` so the key cannot reach a log line or a traceback by accident:
    # its repr is `**********`, and reading it takes an explicit
    # `get_secret_value()` call that is easy to grep for.
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = Field(default="gpt-4o-mini", min_length=1)

    # nginx proxies /api in the container build, so the browser only ever makes
    # same-origin requests. This is for the dev server on :5173 and for curl.
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    log_level: str = Field(default="INFO")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept the comma-separated form the compose file and README use.

        Pydantic would otherwise expect JSON for a list-valued setting, and
        `ALLOWED_ORIGINS=http://localhost:5173` is what every deployment of this
        service actually sets.
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def has_api_key(self) -> bool:
        """Whether a key is configured at all, for the health probe and fallbacks."""
        return bool(self.openai_api_key.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process-wide settings, read once.

    Cached rather than constructed per call so that a request does not re-read the
    filesystem, and so every layer sees the same values.
    """
    return Settings()
