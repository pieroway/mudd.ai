"""Admin-reviewed generation, with no transaction spanning provider work."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.provider import AIProvider, AIProviderError
from app.ai.world import RoomProposalContent, WorldGenerationRequest
from app.domain.directions import DIRECTIONS, OPPOSITE, resolve_direction
from app.models.world_proposal import WorldProposalRecord
from app.repositories.world_proposals import WorldProposalRepository
from app.services.ai_usage import reserve_attempt
from app.services import neighborhood

WORLD_HELP = (
    neighborhood.GENERATE_HELP + "\n"
    "/world propose <direction> <brief> (up to 400 characters)\n"
    "/world proposals\n/world preview <proposal-id>\n"
    "/world approve <proposal-id>\n/world reject <proposal-id>"
    "\n/world describe <description> (up to five sentences, 2000 characters)"
)


class GenerationDenied(Exception):
    """Safe local feedback, never populated with upstream text."""


def result(text: str, success: bool = False, **extra: Any) -> dict[str, Any]:
    return {"success": success, "output": text, **extra}


def preview(proposal: WorldProposalRecord, source_name: str) -> str:
    if proposal.schema_version == 2:
        return neighborhood.preview(proposal, source_name)
    return (
        f"Room proposal {proposal.id} [{proposal.status}]\n"
        f"Source: {source_name} ({proposal.source_room_id})\n"
        f"{source_name} -> {proposal.direction} -> {proposal.name}\n"
        f"{proposal.name} -> {OPPOSITE[proposal.direction]} -> {source_name}\n"
        f"{proposal.description}\n"
        "Draft prose adds no interactable objects. Review mood and world consistency.\n"
        f"/world approve {proposal.id}\n/world reject {proposal.id}"
    )


class WorldGenerationService:
    def __init__(self, factory: async_sessionmaker[AsyncSession], provider: AIProvider | None,
                 *, timeout_seconds: float = 5, daily_request_limit: int = 50,
                 neighborhood_timeout_seconds: float = 60):
        self.factory = factory
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.daily_request_limit = daily_request_limit
        self.neighborhood_timeout_seconds = neighborhood_timeout_seconds

    async def execute(self, player_id: str, arguments: list[str], *, account_id: str | None,
                      authorization_check: Callable[[], Awaitable[bool]]) -> dict[str, Any]:
        if account_id is None or not await authorization_check():
            return result("The /world command requires an active admin session.")
        try:
            if arguments[:1] == ["generate"]:
                return await neighborhood.generate(self, player_id, account_id,
                    arguments[1] if len(arguments) == 2 else "", authorization_check)
            if arguments[:1] == ["propose"]:
                return await self._propose(player_id, account_id, arguments, authorization_check)
            async with self.factory() as session, session.begin():
                repo = WorldProposalRepository(session)
                player = await repo.admin_player(account_id, player_id)
                if player is None or not await authorization_check():
                    return result("The /world command is available to admin users only.")
                if arguments[:1] == ["describe"]:
                    if len(arguments) != 2:
                        return result("Usage: /world describe <description> (up to five sentences, 2000 characters).")
                    await repo.lock_world()
                    source, _, _ = await repo.source(player.current_room_id)
                    try:
                        content = RoomProposalContent(name=source.name, description=arguments[1])
                    except ValidationError:
                        return result("Use one to five sentences, up to 2000 characters, without control characters.")
                    if not await authorization_check():
                        return result("Session expired. Please sign in again.")
                    source.description = content.description
                    return result(f"Room description updated: {source.name}\n{source.description}", True,
                                  _world_source=source.id,
                                  _world_notice="This room's description has changed. Use look to read it.")
                if arguments == ["proposals"]:
                    drafts = await repo.recent(account_id)
                    return result("Your latest world proposals:\n" + ("\n".join(
                        f"{p.id} [{p.status}] {p.name}" for p in drafts) or "No proposals yet."), True)
                if len(arguments) != 2 or arguments[0] not in {"preview", "approve", "reject"}:
                    return result("Usage:\n" + WORLD_HELP)
                try:
                    proposal_id = str(UUID(arguments[1]))
                except ValueError:
                    return result("Proposal not found.")
                proposal = await repo.owned(proposal_id, account_id)
                if proposal is None:
                    return result("Proposal not found.")
                action = arguments[0]
                source, _, _ = await repo.source(proposal.source_room_id)
                if action == "preview":
                    return result(preview(proposal, source.name), True, proposal_id=proposal.id)
                if action == "reject":
                    if proposal.status == "rejected":
                        return result("Proposal already rejected.", True)
                    if proposal.status != "pending":
                        return result(f"Cannot reject a {proposal.status} proposal.")
                    proposal.status = "rejected"
                    proposal.decided_at = func.now()  # type: ignore[assignment]
                    return result("Proposal rejected. The world is unchanged.", True)
                if self.provider is None:
                    return result("World generation and approval are currently disabled.")
                if proposal.status == "approved":
                    return result(f"Already approved: {proposal.result_room_id}", True,
                                  room_id=proposal.result_room_id)
                if proposal.status != "pending":
                    return result(f"Proposal is {proposal.status}. Request a new proposal.")
                if proposal.schema_version == 2:
                    return await neighborhood.approve(repo, proposal, player, authorization_check,
                                                       lambda: self.provider is not None)
                if player.current_room_id != proposal.source_room_id:
                    return result("Return to the source room before approving.")
                await repo.lock_world()
                source, exits, fingerprint = await repo.source(proposal.source_room_id)
                if not await authorization_check():
                    return result("Session expired. Please sign in again.")
                if self.provider is None:
                    return result("World generation and approval are currently disabled.")
                if (fingerprint != proposal.source_fingerprint or proposal.direction in exits
                        or await repo.duplicate_name(proposal.name)):
                    proposal.status = "stale"
                    proposal.decided_at = func.now()  # type: ignore[assignment]
                    return result("Proposal is stale: source, exit, or name changed. Request a new proposal.")
                # Revalidate stored content before canonical insertion as well.
                RoomProposalContent(name=proposal.name, description=proposal.description)
                room_id = await repo.publish(proposal)
                return result(f"Approved {proposal.name} ({room_id}). Exit {proposal.direction} is now available.",
                              True, room_id=room_id, _world_source=source.id,
                              _world_direction=proposal.direction)
        except GenerationDenied as error:
            return result(str(error))
        except IntegrityError:
            return result("World conflict; nothing was added. Preview or request a new proposal.")
        except (AIProviderError, TimeoutError, ValueError):
            return result("World generation unavailable or invalid. No room was added; try again later.")

    async def _propose(self, player_id: str, account_id: str, arguments: list[str],
                       authorized: Callable[[], Awaitable[bool]]) -> dict[str, Any]:
        async with self.factory() as session, session.begin():
            repo = WorldProposalRepository(session)
            player = await repo.admin_player(account_id, player_id)
            if player is None or not await authorized():
                return result("The /world command is available to admin users only.")
            if self.provider is None:
                return result("World generation and approval are currently disabled.")
            if len(arguments) != 3 or arguments[1] not in DIRECTIONS:
                return result("Usage:\n" + WORLD_HELP)
            direction = resolve_direction(arguments[1], player.facing_direction)
            source, exits, fingerprint = await repo.source(player.current_room_id)
            if direction in exits:
                return result("That exit is occupied. Choose an unused direction.")
            if await repo.pending_count(account_id) >= 10:
                return result("You have ten pending proposals. Approve or reject one first.")
            request = WorldGenerationRequest(brief=arguments[2], source_name=source.name,
                source_description=source.description, direction=direction, return_direction=OPPOSITE[direction])
            source_id = source.id

        async def before_dispatch() -> bool:
            if not await authorized() or self.provider is None:
                raise GenerationDenied("Admin session or world generation is no longer available.")
            if not await reserve_attempt(self.factory, account_id, self.daily_request_limit):
                raise GenerationDenied("Daily AI allowance exhausted. It resets at 00:00 UTC. Classic commands still work.")
            return True

        provider = self.provider
        if provider is None:
            return result("World generation and approval are currently disabled.")
        try:
            response = await asyncio.wait_for(provider.generate_room(request, before_dispatch=before_dispatch),
                                              timeout=self.timeout_seconds)
        except GenerationDenied:
            raise
        except Exception:
            # Upstream errors must never reach WebSocket exception logs with private context.
            raise AIProviderError("World generation unavailable.") from None
        payload = response.model_dump() if isinstance(response, RoomProposalContent) else response
        content = RoomProposalContent.model_validate(payload)
        async with self.factory() as session, session.begin():
            repo = WorldProposalRepository(session)
            player = await repo.admin_player(account_id, player_id)
            if player is None or not await authorized() or self.provider is None:
                return result("Admin session or world generation is no longer available.")
            if player.current_room_id != source_id:
                return result("You left the source room. Request a new proposal there.")
            _, exits, current = await repo.source(source_id)
            if current != fingerprint or direction in exits:
                return result("The source room changed. Request a new proposal.")
            if await repo.pending_count(account_id) >= 10:
                return result("Another request filled your ten pending proposal slots.")
            if await repo.duplicate_name(content.name):
                return result("A room with that name already exists. Request a new proposal.")
            proposal = WorldProposalRecord(id=str(uuid4()), creator_account_id=account_id,
                source_room_id=source_id, source_fingerprint=fingerprint, direction=direction,
                name=content.name, description=content.description, status="pending")
            session.add(proposal)
            await session.flush()
            return result(preview(proposal, request.source_name), True, proposal_id=proposal.id)
