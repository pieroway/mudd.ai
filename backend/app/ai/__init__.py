"""AI provider contracts and implementations."""

from app.ai.fake import FakeAIProvider
from app.ai.factory import UnsupportedAIProviderError, create_ai_provider
from app.ai.models import InterpretCommandRequest, InterpretCommandResponse, ProposedCommand
from app.ai.provider import AIProvider, AIProviderError, CommandNotInterpretedError

__all__ = [
    "AIProvider",
    "AIProviderError",
    "CommandNotInterpretedError",
    "FakeAIProvider",
    "InterpretCommandRequest",
    "InterpretCommandResponse",
    "ProposedCommand",
    "UnsupportedAIProviderError",
    "create_ai_provider",
]

