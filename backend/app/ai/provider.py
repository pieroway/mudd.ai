"""Provider-independent interfaces for command proposals and outcome narration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from app.ai.models import InterpretCommandRequest, InterpretCommandResponse
from app.ai.narration import NarrationRequest, NarrationResponse
from app.ai.npc import NPCRequest, NPCResponse
from app.ai.world import RoomProposalContent, WorldGenerationRequest
from app.ai.neighborhood import NeighborhoodDraft, NeighborhoodRequest


class AIProviderError(RuntimeError):
    """Base error for an unavailable or invalid AI response."""


class CommandNotInterpretedError(AIProviderError):
    """Raised when a provider has no valid interpretation for player input."""


class AIProvider(ABC):
    """Translate player language into a validated, non-authoritative command."""

    async def generate_neighborhood(self, request: NeighborhoodRequest, *,
                                    before_dispatch: Callable[[], Awaitable[bool]]) -> NeighborhoodDraft:
        """Propose a bounded draft after reserving capacity and allowance."""
        raise AIProviderError("Neighborhood generation is unavailable for this provider.")

    @abstractmethod
    async def interpret_command(
        self, request: InterpretCommandRequest
    ) -> InterpretCommandResponse:
        """Propose a command for later validation and execution by the game engine."""
        raise NotImplementedError

    async def narrate_result(self, request: NarrationRequest) -> NarrationResponse:
        """Describe an already committed outcome; never propose or execute actions."""
        raise AIProviderError("Narration is unavailable for this provider.")

    async def npc_response(self, request: NPCRequest) -> NPCResponse:
        """Return dialogue only, using an explicitly authorized context."""
        raise AIProviderError("NPC conversation is unavailable for this provider.")

    async def generate_room(self, request: WorldGenerationRequest, *,
                            before_dispatch: Callable[[], Awaitable[bool]]) -> RoomProposalContent:
        """Check capacity, reserve allowance via callback, then dispatch exactly once."""
        raise AIProviderError("World generation is unavailable for this provider.")
