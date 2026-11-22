"""Optional narration after command results and multiplayer events are delivered."""

import asyncio
import logging
from hashlib import sha256
from secrets import choice
from time import monotonic
from collections.abc import Awaitable, Callable
from weakref import WeakValueDictionary

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.narration import NarrationRequest, NarrationResponse
from app.ai.provider import AIProvider, AIProviderFailure, AIFailureReason
from pydantic import ValidationError
from app.services.ai_usage import reserve_attempt
from app.services.ai_preferences import narration_allowed
from app.models import NarrationLibraryRecord

logger = logging.getLogger(__name__)


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
        self._outcome_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()

    async def narrate(
        self,
        request: NarrationRequest,
        *,
        account_id: str | None = None,
        authorization_check: Callable[[], Awaitable[bool]] | None = None,
    ) -> str | None:
        started = monotonic()
        async def allowed() -> bool:
            return (authorization_check is None or await authorization_check()) and (
                account_id is None or await narration_allowed(self.session_factory, account_id)
            )

        try:
            if not await allowed():
                return None
            key = sha256(request.model_dump_json().encode("utf-8")).hexdigest()
            lock = self._outcome_locks.setdefault(key, asyncio.Lock())
            async with lock:
                async with self.session_factory() as session:
                    saved = await session.get(NarrationLibraryRecord, key)
                if saved is not None:
                    return choice(saved.flourishes) if await allowed() else None
                if self.provider is None or not await allowed():
                    return None
                if account_id is not None and not await reserve_attempt(
                    self.session_factory, account_id, self.daily_request_limit
                ):
                    return None
                response = await asyncio.wait_for(
                    self.provider.narrate_result(request.model_copy(deep=True)),
                    timeout=self.timeout_seconds,
                )
                payload = response.model_dump() if isinstance(response, NarrationResponse) else response
                validated = NarrationResponse.model_validate(payload)
                if not await allowed():
                    return None
                flourishes = list(dict.fromkeys(validated.flourishes))
                async with self.session_factory() as session, session.begin():
                    await session.execute(insert(NarrationLibraryRecord).values(
                        outcome_key=key, flourishes=flourishes,
                    ).on_conflict_do_nothing())
                    stored = await session.get(NarrationLibraryRecord, key)
                    if stored is not None:
                        flourishes = stored.flourishes
                return choice(flourishes) if await allowed() else None
        except Exception as error:
            # Presentation failure must not turn a committed action into an error or
            # leak prompts, provider bodies, or credentials. Cancellation still propagates.
            reason = (error.reason.value if isinstance(error, AIProviderFailure) else
                      AIFailureReason.TIMEOUT.value if isinstance(error, TimeoutError) else
                      AIFailureReason.INVALID_RESPONSE.value if isinstance(error, ValidationError) else
                      AIFailureReason.INTERNAL.value)
            logger.warning(
                'AI narration failed: action=%s reason=%s http_status=%s elapsed_ms=%d',
                request.action, reason,
                error.http_status if isinstance(error, AIProviderFailure) else None,
                round((monotonic() - started) * 1000),
            )
            return None
