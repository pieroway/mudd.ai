"""Insert one reviewed room into an existing reciprocal outdoor route."""

import asyncio
import hashlib
import json
import shlex
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import NoResultFound

from app.ai.provider import AIProviderError
from app.ai.world import RoomProposalContent, WorldGenerationRequest
from app.domain.directions import DIRECTIONS, HORIZONTAL, OPPOSITE, resolve_direction
from app.models import ExitRecord, PlayerRecord, RoomRecord, WorldProposalRecord
from app.repositories.world_proposals import WorldProposalRepository
from app.services.ai_usage import reserve_attempt

if TYPE_CHECKING:
    from app.services.world_generation import WorldGenerationService

HELP = '/world insert <direction> --theme "brief" (1 to 400 characters)'


class InsertionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    destination_id: str = Field(min_length=1, max_length=50)
    destination_name: str = Field(min_length=1, max_length=100)


def result(text: str, success: bool = False, **extra: Any) -> dict[str, Any]:
    return {"success": success, "output": text, **extra}


async def route(
    repo: WorldProposalRepository, source_id: str, direction: str
) -> tuple[RoomRecord, RoomRecord, ExitRecord, ExitRecord, str]:
    if direction not in HORIZONTAL:
        raise ValueError("Choose a horizontal direction for street insertion.")
    source, exits, source_hash = await repo.source(source_id)
    if direction not in exits or exits[direction] == source_id:
        raise ValueError("Insertion requires an existing exit to another room.")
    try:
        destination, _, destination_hash = await repo.source(exits[direction])
    except NoResultFound:
        raise ValueError("The destination no longer exists.") from None
    edges = (
        await repo.session.scalars(
            select(ExitRecord)
            .where(ExitRecord.room_id.in_([source_id, destination.id]))
            .execution_options(populate_existing=True)
        )
    ).all()
    forward = next((e for e in edges if e.room_id == source_id and e.direction == direction), None)
    if forward is None or forward.destination_room_id != destination.id:
        raise ValueError("The route changed. Request a new proposal.")
    back = next(
        (e for e in edges if e.room_id == destination.id and e.direction == OPPOSITE[direction]),
        None,
    )
    if back is None or back.destination_room_id != source_id:
        raise ValueError("Insertion requires a matching return exit.")
    if forward.door_id is not None or back.door_id is not None:
        raise ValueError("Routes with doors cannot be inserted into.")
    if source.building_id is not None or destination.building_id is not None:
        raise ValueError("Street insertion requires two outdoor rooms.")
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                source_hash,
                destination_hash,
                direction,
                source.building_id,
                destination.building_id,
                source.conditions,
                destination.conditions,
                forward.door_id,
                back.door_id,
            ]
        ).encode()
    ).hexdigest()
    return source, destination, forward, back, fingerprint


def preview(proposal: WorldProposalRecord, source_name: str) -> str:
    payload = InsertionPayload.model_validate(proposal.payload)
    direction, reverse = proposal.direction, OPPOSITE[proposal.direction]
    return (
        f"Insertion proposal {proposal.id} [{proposal.status}]\n"
        f"Before: {source_name} -> {direction} -> {payload.destination_name}\n"
        f"After: {source_name} -> {direction} -> {proposal.name} -> {direction} -> {payload.destination_name}\n"
        f"Return: {payload.destination_name} -> {reverse} -> {proposal.name} -> {reverse} -> {source_name}\n"
        f"{proposal.description}\n"
        "The existing rooms, objects and occupants are preserved. No objects are generated.\n"
        f"/world approve {proposal.id}\n/world reject {proposal.id}"
    )


async def generate(
    service: "WorldGenerationService",
    player_id: str,
    account_id: str,
    arguments: str,
    authorized: Callable[[], Awaitable[bool]],
) -> dict[str, Any]:
    try:
        parts = shlex.split(arguments)
        if len(parts) != 3 or parts[0].lower() not in DIRECTIONS or parts[1] != "--theme":
            return result("Usage: " + HELP)
    except ValueError:
        return result("Usage: " + HELP)
    async with service.factory() as session, session.begin():
        repo = WorldProposalRepository(session)
        player = await repo.admin_player(account_id, player_id)
        if player is None or not await authorized():
            return result("The /world command is available to admin users only.")
        if service.provider is None:
            return result("World generation and approval are currently disabled.")
        direction = resolve_direction(parts[0].lower(), player.facing_direction)
        try:
            source, destination, _, _, fingerprint = await route(
                repo, player.current_room_id, direction
            )
        except ValueError as error:
            return result(str(error))
        if await repo.pending_count(account_id) >= 10:
            return result("You have ten pending proposals. Approve or reject one first.")
        request = WorldGenerationRequest(
            brief=parts[2],
            source_name=source.name,
            source_description=source.description,
            direction=direction,
            return_direction=OPPOSITE[direction],
        )
        source_id, destination_id = source.id, destination.id

    async def before_dispatch() -> bool:
        from app.services.world_generation import GenerationDenied

        if not await authorized() or service.provider is None:
            raise GenerationDenied("Admin session or world generation is no longer available.")
        if not await reserve_attempt(service.factory, account_id, service.daily_request_limit):
            raise GenerationDenied("Daily AI allowance exhausted. It resets at 00:00 UTC.")
        return True

    provider = service.provider
    if provider is None:
        return result("World generation and approval are currently disabled.")
    try:
        response = await asyncio.wait_for(
            provider.generate_room(request, before_dispatch=before_dispatch),
            timeout=service.timeout_seconds,
        )
    except Exception as error:
        from app.services.world_generation import GenerationDenied

        if isinstance(error, GenerationDenied):
            raise
        raise AIProviderError("World generation unavailable.") from None
    content = RoomProposalContent.model_validate(
        response.model_dump() if isinstance(response, RoomProposalContent) else response
    )
    async with service.factory() as session, session.begin():
        repo = WorldProposalRepository(session)
        player = await repo.admin_player(account_id, player_id)
        if player is None or not await authorized() or service.provider is None:
            return result("Admin session or world generation is no longer available.")
        if player.current_room_id != source_id:
            return result("You left the source room. Request a new proposal there.")
        try:
            source, destination, _, _, current = await route(repo, source_id, direction)
        except ValueError:
            return result("The route changed. Request a new proposal.")
        if current != fingerprint or destination.id != destination_id:
            return result("The route changed. Request a new proposal.")
        if await repo.pending_count(account_id) >= 10 or await repo.duplicate_name(content.name):
            return result(
                "Pending proposal limit reached or room name already exists. Request a new proposal."
            )
        proposal = WorldProposalRecord(
            id=str(uuid4()),
            creator_account_id=account_id,
            source_room_id=source_id,
            source_fingerprint=fingerprint,
            direction=direction,
            name=content.name,
            description=content.description,
            schema_version=3,
            status="pending",
            payload=InsertionPayload(
                destination_id=destination.id, destination_name=destination.name
            ).model_dump(),
        )
        session.add(proposal)
        await session.flush()
        return result(preview(proposal, source.name), True, proposal_id=proposal.id)


async def approve(
    repo: WorldProposalRepository,
    proposal: WorldProposalRecord,
    player: PlayerRecord,
    authorized: Callable[[], Awaitable[bool]],
    enabled: Callable[[], bool],
) -> dict[str, Any]:
    payload = InsertionPayload.model_validate(proposal.payload)
    RoomProposalContent(name=proposal.name, description=proposal.description)
    if player.current_room_id != proposal.source_room_id:
        return result("Return to the source room before approving.")
    await repo.lock_world()
    if not await authorized() or not enabled():
        return result("Admin session or world generation is no longer available.")
    try:
        source, destination, forward, back, fingerprint = await route(
            repo, proposal.source_room_id, proposal.direction
        )
        stale = (
            fingerprint != proposal.source_fingerprint
            or destination.id != payload.destination_id
            or await repo.duplicate_name(proposal.name)
        )
    except ValueError:
        stale = True
    if stale:
        proposal.status = "stale"
        proposal.decided_at = func.now()  # type: ignore[assignment]
        return result("Proposal is stale: the route or room name changed. Request a new proposal.")
    room_id = str(uuid4())
    repo.session.add(RoomRecord(id=room_id, name=proposal.name, description=proposal.description))
    await repo.session.flush()
    forward.destination_room_id = room_id
    back.destination_room_id = room_id
    repo.session.add_all(
        [
            ExitRecord(
                room_id=room_id,
                direction=OPPOSITE[proposal.direction],
                destination_room_id=source.id,
            ),
            ExitRecord(
                room_id=room_id, direction=proposal.direction, destination_room_id=destination.id
            ),
        ]
    )
    proposal.status = "approved"
    proposal.result_room_id = room_id
    proposal.decided_at = func.now()  # type: ignore[assignment]
    await repo.session.flush()
    return result(
        f"Inserted {proposal.name} between {source.name} and {destination.name}.",
        True,
        room_id=room_id,
        _world_source=source.id,
        _world_notice=f"The {proposal.direction} route now passes through {proposal.name}. Use look to view the room.",
    )
