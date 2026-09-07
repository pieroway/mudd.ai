"""Provider-independent interfaces for command proposals and outcome narration."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.models import InterpretCommandRequest, InterpretCommandResponse
from app.ai.narration import NarrationRequest, NarrationResponse


class AIProviderError(RuntimeError):
    """Base error for an unavailable or invalid AI response."""


class CommandNotInterpretedError(AIProviderError):
    """Raised when a provider has no valid interpretation for player input."""


class AIProvider(ABC):
    """Translate player language into a validated, non-authoritative command."""

    @abstractmethod
    async def interpret_command(
        self, request: InterpretCommandRequest
    ) -> InterpretCommandResponse:
        """Propose a command for later validation and execution by the game engine."""
        raise NotImplementedError

    async def narrate_result(self, request: NarrationRequest) -> NarrationResponse:
        """Describe an already committed outcome; never propose or execute actions."""
        raise AIProviderError("Narration is unavailable for this provider.")
