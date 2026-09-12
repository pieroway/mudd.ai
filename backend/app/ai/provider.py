"""Provider-independent interfaces for command proposals and outcome narration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import StrEnum

from app.ai.models import InterpretCommandRequest, InterpretCommandResponse
from app.ai.narration import NarrationRequest, NarrationResponse
from app.ai.npc import NPCRequest, NPCResponse
from app.ai.world import RoomProposalContent, WorldGenerationRequest
from app.ai.neighborhood import NeighborhoodDraft, NeighborhoodRequest


class AIProviderError(RuntimeError):
    """Base error for an unavailable or invalid AI response."""


class AIFailureReason(StrEnum):
    TIMEOUT = 'timeout'
    BUSY = 'concurrency_limit'
    REQUEST_LIMIT = 'request_limit'
    INPUT_LIMIT = 'input_limit'
    ALLOWANCE = 'account_allowance'
    SESSION = 'session_unavailable'
    DISABLED = 'generation_disabled'
    AUTH = 'api_auth'
    RATE_LIMIT = 'api_rate_or_quota_limit'
    API_REQUEST = 'api_request_rejected'
    API_SERVER = 'api_server_error'
    NETWORK = 'network_error'
    OUTPUT_LIMIT = 'output_token_limit'
    INCOMPLETE = 'incomplete_response'
    REFUSAL = 'provider_refusal'
    RESPONSE_SIZE = 'response_size_limit'
    INVALID_RESPONSE = 'invalid_response'
    INVALID_DRAFT = 'invalid_draft'
    UNAVAILABLE = 'provider_unavailable'
    INTERNAL = 'internal_error'


class AIProviderFailure(AIProviderError):
    """A fixed diagnostic category, never an upstream message or response body."""

    def __init__(self, reason: AIFailureReason, *, http_status: int | None = None,
                 detail: str | None = None):
        self.reason = AIFailureReason(reason)
        self.http_status = http_status if isinstance(http_status, int) and 100 <= http_status <= 599 else None
        self.detail = detail if isinstance(detail, str) and detail in SAFE_DRAFT_DETAILS else None
        super().__init__(f'AI provider unavailable ({self.reason.value}).')


# Only exact, local validation messages may cross the provider boundary.
SAFE_DRAFT_DETAILS = frozenset({
    'Rooms allow at most three sentences', 'Objects allow one sentence', 'Doors allow one sentence',
    'Duplicate or reserved labels', 'Room names must be distinct', 'Unknown building',
    'Connections may only join draft rooms or the anchor', 'Conflicting exit directions',
    'Building entrances require doors', 'Exactly one attachment to the existing world is required',
    'Every room must be reachable from the anchor',
    'Buildings require one to three internally connected rooms',
    'Objects require exactly one location', 'Only portable objects may be placed in a room container',
    'Unknown object room', 'At most four distinctly named objects per room',
    'Draft exceeds requested budget', 'Draft attachment direction does not match',
})


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
