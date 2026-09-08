"""Private dialogue with optimistic memory updates and no AI-held game locks."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.npc import ConversationTurn, NPCRequest, NPCResponse
from app.ai.provider import AIProvider
from app.domain.npc import (
    EDRIC_GOALS, EDRIC_ID, EDRIC_KNOWLEDGE, EDRIC_PERSONALITY, relationship_for,
)
from app.models.npc import NPCMemoryRecord
from app.repositories.npc import NPCRepository
from app.services.ai_usage import reserve_attempt


class NPCService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], provider: AIProvider | None,
        *, timeout_seconds: float = 5.0, daily_request_limit: int = 50,
    ):
        self.session_factory = session_factory
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.daily_request_limit = daily_request_limit

    async def talk(
        self, player_id: str, target: str | None, message: str | None, *,
        account_id: str | None, authorization_check: Callable[[], Awaitable[bool]],
    ) -> dict[str, Any]:
        def failure(text: str) -> dict[str, Any]:
            return {"success": False, "output": text}

        if not target or not message or len(message) > 400:
            return failure("Usage: talk <npc> <message> (1-400 characters).")
        if self.provider is None:
            return failure("NPC conversations are currently unavailable.")
        if target.casefold() != EDRIC_ID:
            return failure("That NPC is not here.")
        try:
            if not await authorization_check():
                return failure("Session expired. Please sign in again.")
            async with self.session_factory() as session:
                repository = NPCRepository(session)
                if not await repository.present(player_id, EDRIC_ID, account_id):
                    return failure("Edric is not here. Visit the Inn to talk to him.")
                memory = await repository.memory(player_id, EDRIC_ID)
                version = memory.interactions if memory else 0
                recent = [ConversationTurn(
                    player_text=memory.player_text, npc_text=memory.npc_text,
                )] if memory else []
            context = {
                "name": "Edric", "personality": EDRIC_PERSONALITY,
                "goals": EDRIC_GOALS, "knowledge": EDRIC_KNOWLEDGE,
                "relationship": relationship_for(version), "message": message,
            }
            try:
                request = NPCRequest.model_validate({**context, "recent_conversation": recent})
            except ValidationError:
                # Unicode-heavy history must not permanently prevent future conversations.
                request = NPCRequest.model_validate({**context, "recent_conversation": []})
            if not await authorization_check():
                return failure("Session expired. Please sign in again.")
            if account_id is not None and not await reserve_attempt(
                self.session_factory, account_id, self.daily_request_limit,
            ):
                return failure("Daily AI allowance exhausted. It resets at 00:00 UTC. Classic commands still work.")
            response = await asyncio.wait_for(
                self.provider.npc_response(request.model_copy(deep=True)),
                timeout=self.timeout_seconds,
            )
            payload = response.model_dump() if isinstance(response, NPCResponse) else response
            validated = NPCResponse.model_validate(payload)
            if not await authorization_check():
                return failure("Session expired. Please sign in again.")
            async with self.session_factory() as session, session.begin():
                repository = NPCRepository(session)
                # Serializes updates against player movement and concurrent replies,
                # including the first interaction where no memory row exists yet.
                await repository.lock_player(player_id)
                if not await authorization_check():
                    return failure("Session expired. Please sign in again.")
                if not await repository.present(player_id, EDRIC_ID, account_id):
                    return failure("The conversation ended because you are no longer with Edric.")
                current = await repository.memory(player_id, EDRIC_ID)
                if (current.interactions if current else 0) != version:
                    return failure("Another conversation finished first. Please try again.")
                if current is None:
                    current = NPCMemoryRecord(npc_id=EDRIC_ID, player_id=player_id)
                    session.add(current)
                current.interactions = version + 1
                current.player_text = message
                current.npc_text = validated.text
            return {
                "success": True,
                "output": f'[NPC] Edric tells you privately, "{validated.text}"',
            }
        except Exception:
            # Do not log player dialogue, provider content, or credentials.
            # Cancellation propagates, and no failed response is remembered.
            return failure("Edric cannot reply right now. Please try again later.")
