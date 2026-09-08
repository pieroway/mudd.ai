"""Optional narration after command results and multiplayer events are delivered."""

import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.narration import NarrationRequest, NarrationResponse
from app.ai.provider import AIProvider
from app.services.ai_usage import reserve_attempt
from app.services.ai_preferences import narration_allowed


class NarrationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: AIProvider | None,
        *,
        timeout_seconds: float = 5.0,
        daily_request_limit: int = 50,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.daily_request_limit = daily_request_limit

    async def narrate(
        self,
        request: NarrationRequest,
        *,
        account_id: str | None = None,
        authorization_check: Callable[[], Awaitable[bool]] | None = None,
    ) -> str | None:
        if self.provider is None:
            return None
        try:
            if authorization_check is not None and not await authorization_check():
                return None
            if account_id is not None and not await narration_allowed(self.session_factory, account_id):
                return None
            if account_id is not None and not await reserve_attempt(
                self.session_factory, account_id, self.daily_request_limit
            ):
                return None
            response = await asyncio.wait_for(
                self.provider.narrate_result(request.model_copy(deep=True)),
                timeout=self.timeout_seconds,
            )
            # Revalidate even provider-created models that bypassed normal construction.
            payload = response.model_dump() if isinstance(response, NarrationResponse) else response
            validated = NarrationResponse.model_validate(payload)
            if account_id is not None and not await narration_allowed(self.session_factory, account_id):
                return None
            if authorization_check is not None and not await authorization_check():
                return None
            return validated.text
        except Exception:
            # Presentation failure must not turn a committed action into an error or
            # leak prompts, provider bodies, or credentials. Cancellation still propagates.
            return None
