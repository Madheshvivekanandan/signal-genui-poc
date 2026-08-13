"""Settings, and the two things about them that would be silent if wrong.

The comma-separated origins form is what the compose file and the README use, and
the secret has to stay out of every string representation of the object -- a
`Settings` that landed in a log line at DEBUG would leak the key.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


class TestSettings:
    def test_splits_the_comma_separated_origins_form(self) -> None:
        settings = Settings(allowed_origins="http://a.test, http://b.test")

        assert settings.allowed_origins == ["http://a.test", "http://b.test"]

    def test_drops_empty_entries_from_a_trailing_comma(self) -> None:
        settings = Settings(allowed_origins="http://a.test,")

        assert settings.allowed_origins == ["http://a.test"]

    def test_accepts_a_real_list_unchanged(self) -> None:
        assert Settings(allowed_origins=["http://a.test"]).allowed_origins == ["http://a.test"]

    def test_keeps_the_key_out_of_repr(self) -> None:
        settings = Settings(openai_api_key=SecretStr("sk-not-a-real-key"))

        assert "sk-not-a-real-key" not in repr(settings)
        assert "sk-not-a-real-key" not in str(settings.model_dump())

    def test_has_api_key_is_false_for_an_empty_key(self) -> None:
        assert Settings(openai_api_key=SecretStr("")).has_api_key is False

    def test_has_api_key_is_true_once_one_is_set(self) -> None:
        assert Settings(openai_api_key=SecretStr("anything")).has_api_key is True

    def test_rejects_an_empty_model_name(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Settings(openai_model="")


class TestGetSettings:
    def test_is_cached_so_every_layer_sees_the_same_object(self) -> None:
        get_settings.cache_clear()

        assert get_settings() is get_settings()

        get_settings.cache_clear()


class TestConfigureLogging:
    def test_installs_exactly_one_handler(self) -> None:
        import logging

        configure_logging("WARNING")

        assert len(logging.getLogger().handlers) == 1
        assert logging.getLogger().level == logging.WARNING

    def test_falls_back_to_info_on_a_typo_rather_than_refusing_to_boot(self) -> None:
        import logging

        configure_logging("VERBOSE")

        assert logging.getLogger().level == logging.INFO

    def test_records_carry_the_request_id_the_format_string_references(self) -> None:
        import logging

        from app.core.logging import RequestIdFilter, request_id_var

        record = logging.LogRecord("t", logging.INFO, "f", 1, "m", None, None)
        token = request_id_var.set("abc123")
        try:
            assert RequestIdFilter().filter(record) is True
            # The attribute is injected by the filter, so it is not on the stub.
            assert record.request_id == "abc123"  # type: ignore[attr-defined]
        finally:
            request_id_var.reset(token)
