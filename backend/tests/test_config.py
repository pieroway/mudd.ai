import pytest
from pydantic import ValidationError

from app.config import Settings


def test_trusted_origins_are_trimmed_and_matched_exactly():
    settings = Settings(
        _env_file=None,
        trusted_origins="https://mud.example, http://localhost:5173 ",
    )

    assert settings.allowed_origins == ["https://mud.example", "http://localhost:5173"]
    assert settings.allows_origin("https://mud.example") is True
    assert settings.allows_origin("https://sub.mud.example") is False
    assert settings.allows_origin(None) is True


def test_wildcard_trusted_origin_is_rejected():
    with pytest.raises(ValidationError, match="exact origins"):
        Settings(_env_file=None, trusted_origins="*")


def test_websocket_limits_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_command_bytes=0)


def test_ai_command_timeout_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_command_timeout_seconds=0)
