"""Create configured AI providers without coupling them to game services."""

from __future__ import annotations

from app.ai.fake import FakeAIProvider
from app.ai.openai import OpenAIProvider
from app.ai.provider import AIProvider
from app.config import Settings


class UnsupportedAIProviderError(ValueError):
    """Raised when an enabled provider has no available adapter."""


def create_ai_provider(settings: Settings) -> AIProvider | None:
    """Return the enabled command provider, or no provider when disabled."""
    if not settings.ai_command_interpretation_enabled:
        return None
    if settings.ai_provider == "fake":
        if settings.app_env.casefold() == "production":
            raise UnsupportedAIProviderError(
                "FakeAIProvider is not allowed in production when command "
                "interpretation is enabled."
            )
        return FakeAIProvider()
    if settings.ai_provider == "openai":
        if settings.app_env.casefold() != "development":
            raise UnsupportedAIProviderError("OpenAI command interpretation is development-only.")
        if not settings.openai_api_key.get_secret_value().strip() or not settings.ai_model.strip():
            raise UnsupportedAIProviderError("OpenAI requires OPENAI_API_KEY and explicit AI_MODEL.")
        return OpenAIProvider(settings)
    raise UnsupportedAIProviderError(
        f"AI provider {settings.ai_provider!r} is not implemented for command interpretation."
    )
