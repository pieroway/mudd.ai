"""Create configured AI providers without coupling them to game services."""

from __future__ import annotations

from app.ai.fake import FakeAIProvider
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
    raise UnsupportedAIProviderError(
        f"AI provider {settings.ai_provider!r} is not implemented for command interpretation."
    )
