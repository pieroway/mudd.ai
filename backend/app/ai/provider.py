"""Provider-independent interface for AI command interpretation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.models import InterpretCommandRequest, InterpretCommandResponse


class AIProvider(ABC):
    """Translate player language into a validated, non-authoritative command."""

    @abstractmethod
    async def interpret_command(
        self, request: InterpretCommandRequest
    ) -> InterpretCommandResponse:
        """Propose a command for later validation and execution by the game engine."""
        raise NotImplementedError
