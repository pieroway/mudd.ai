"""Prepare and publish a bounded expansion without mutating the world during AI work."""
import asyncio
import logging
import shlex
from time import monotonic
from collections.abc import Awaitable, Callable
from typing import Any
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, select

from app.ai.neighborhood import NeighborhoodDraft, NeighborhoodRequest, validate_budget, draft_failure
from app.ai.provider import AIProviderError, AIProviderFailure, AIFailureReason
from app.domain.directions import HORIZONTAL, OPPOSITE, resolve_direction
from app.models import ExitRecord, ItemRecord, RoomRecord, WorldProposalRecord
from app.models.game import BuildingRecord, DoorRecord
from app.repositories.world_proposals import WorldProposalRepository
from app.services.ai_usage import reserve_attempt

if TYPE_CHECKING:
    from app.services.world_generation import WorldGenerationService

GENERATE_HELP = '/world generate [around|direction] [--radius 0..2] [--rooms 1..12] [--buildings 0..4] [--theme "brief"]'
logger = logging.getLogger(__name__)

FAILURE_MESSAGES = {
    AIFailureReason.TIMEOUT: 'Generation timed out. Try a smaller neighborhood or check the generation timeout.',
    AIFailureReason.BUSY: 'The AI provider is busy with another request. Wait for it to finish, then try again.',
    AIFailureReason.REQUEST_LIMIT: 'The backend has reached its AI request limit for this process. An operator must review the limit before restarting or reconfiguring it.',
    AIFailureReason.INPUT_LIMIT: 'The generation context exceeds the allowed input size.',
    AIFailureReason.ALLOWANCE: 'Your daily AI allowance and bonus credits are exhausted. The daily allowance resets at 00:00 UTC.',
    AIFailureReason.SESSION: 'Your session is no longer available. Sign in again before generating.',
    AIFailureReason.DISABLED: 'World generation was disabled before the request could be sent.',
    AIFailureReason.AUTH: 'The AI API denied access. Check the API credentials and project permissions.',
    AIFailureReason.RATE_LIMIT: 'The AI API reported a rate or quota limit. Check provider usage and billing; this is separate from your in-game allowance.',
    AIFailureReason.API_REQUEST: 'The AI API rejected the request. Check the configured model and request/schema compatibility.',
    AIFailureReason.API_SERVER: 'The AI API reported a server error. Try again later.',
    AIFailureReason.NETWORK: 'The backend could not communicate with the AI API. Check connectivity and try again later.',
    AIFailureReason.OUTPUT_LIMIT: 'The AI response hit its output-token limit before completing. Try fewer rooms/buildings or review the generation output limit.',
    AIFailureReason.INCOMPLETE: 'The AI API returned an incomplete response. No draft could be validated.',
    AIFailureReason.REFUSAL: 'The AI provider declined to generate this draft. Try a different brief.',
    AIFailureReason.RESPONSE_SIZE: 'The AI response exceeded the allowed response size. Try a smaller neighborhood.',
    AIFailureReason.INVALID_RESPONSE: 'The AI API returned an unreadable or unexpected response.',
    AIFailureReason.INVALID_DRAFT: 'The generated neighborhood failed validation.',
    AIFailureReason.UNAVAILABLE: 'The AI provider is unavailable and supplied no classified failure reason.',
    AIFailureReason.INTERNAL: 'An unexpected internal error interrupted generation. Check the backend diagnostics.',
}


def generation_failure(error: AIProviderFailure, started: float, timeout: float) -> dict[str, Any]:
    elapsed_ms = round((monotonic() - started) * 1000)
    # Never log exception objects/tracebacks, provider bodies, prompts, or account IDs.
    logger.warning('Neighborhood generation failed: reason=%s http_status=%s elapsed_ms=%d detail=%s',
                   error.reason.value, error.http_status, elapsed_ms, error.detail)
    message = FAILURE_MESSAGES[error.reason]
    if error.reason == AIFailureReason.TIMEOUT:
        message += f' Configured timeout: {timeout:g} seconds.'
    if error.http_status is not None:
        message += f' HTTP {error.http_status}.'
    if error.detail:
        message += f' {error.detail}.'
    return {'success': False, 'output': f'{message} No world changes were made. [{error.reason.value}]'}


def options(raw: str) -> dict[str, Any]:
    tokens = shlex.split(raw)
    result: dict[str, Any] = {'direction': 'around', 'radius': 2, 'rooms': 8, 'buildings': 2,
                              'brief': 'A small, coherent expansion appropriate to the surroundings.'}
    brief: list[str] = []
    used: set[str] = set()
    direction_seen = False
    while tokens:
        token = tokens.pop(0)
        if token.startswith('--'):
            key = token[2:].casefold()
            if key not in {'radius', 'rooms', 'buildings', 'theme'} or key in used or not tokens:
                raise ValueError(GENERATE_HELP)
            used.add(key)
            value = tokens.pop(0)
            result['brief' if key == 'theme' else key] = value if key == 'theme' else int(value)
        elif not brief and not direction_seen and token.casefold() in {'around', *HORIZONTAL, 'n', 'e', 's', 'w', 'left', 'right', 'forward', 'backward', 'backwards'}:
            result['direction'] = token.casefold()
            direction_seen = True
        else:
            brief.append(token)
    if brief:
        if 'theme' in used:
            raise ValueError(GENERATE_HELP)
        result['brief'] = ' '.join(brief)
    if not (0 <= result['radius'] <= 2 and 1 <= result['rooms'] <= 12 and 0 <= result['buildings'] <= 4):
        raise ValueError(GENERATE_HELP)
    return result


async def expansion_anchor(repo, player, settings):
    rooms = {room.id: room for room in (await repo.session.scalars(select(RoomRecord))).all()}
    exits: dict[str, dict[str, str]] = {key: {} for key in rooms}
    for edge in (await repo.session.scalars(select(ExitRecord))).all():
        exits[edge.room_id][edge.direction] = edge.destination_room_id
    direction = settings['direction']
    if direction != 'around':
        direction = resolve_direction(direction, player.facing_direction)
        if direction in exits[player.current_room_id] or rooms[player.current_room_id].building_id:
            raise ValueError('Choose an unused outdoor exit, or use /world generate around.')
        return player.current_room_id, direction
    seen = {player.current_room_id}
    queue = [(player.current_room_id, 0)]
    for key, distance in queue:
        if rooms[key].building_id is None:
            for candidate in ['north', 'east', 'south', 'west']:
                if candidate not in exits[key]:
                    return key, candidate
        if distance < settings['radius']:
            for candidate in ['north', 'east', 'south', 'west']:
                destination = exits[key].get(candidate)
                if destination and destination not in seen and rooms[destination].building_id is None:
                    seen.add(destination)
                    queue.append((destination, distance + 1))
    raise ValueError('No unused outdoor exit within that radius. Move to a frontier or increase --radius (maximum 2).')


async def generate(service: 'WorldGenerationService', player_id: str, account_id: str, raw: str,
                   authorized: Callable[[], Awaitable[bool]]) -> dict[str, Any]:
    def response(message: str, success: bool = False, **extra: Any) -> dict[str, Any]:
        return {'success': success, 'output': message, **extra}
    try:
        async with service.factory() as session, session.begin():
            repo = WorldProposalRepository(session)
            player = await repo.admin_player(account_id, player_id)
            if player is None or not await authorized():
                return response('The /world command is available to admin users only.')
            if service.provider is None:
                return response('World generation is currently disabled.')
            settings = options(raw)
            if await repo.pending_count(account_id) >= 10:
                return response('You have ten pending proposals. Accept or reject one first.')
            source_id, direction = await expansion_anchor(repo, player, settings)
            source, _, fingerprint = await repo.source(source_id)
            origin, _, origin_fingerprint = await repo.source(player.current_room_id)
            origin_id = origin.id
            request = NeighborhoodRequest(brief=settings['brief'], origin_name=origin.name,
                anchor_name=source.name, anchor_description=source.description, direction=direction,
                max_rooms=settings['rooms'], max_buildings=settings['buildings'])

        async def before_dispatch():
            if not await authorized():
                raise AIProviderFailure(AIFailureReason.SESSION)
            if service.provider is None:
                raise AIProviderFailure(AIFailureReason.DISABLED)
            if not await reserve_attempt(service.factory, account_id, service.daily_request_limit):
                raise AIProviderFailure(AIFailureReason.ALLOWANCE)
            return True

        started = monotonic()
        try:
            async with asyncio.timeout(service.neighborhood_timeout_seconds):
                draft = await service.provider.generate_neighborhood(request, before_dispatch=before_dispatch)
            draft = NeighborhoodDraft.model_validate(draft.model_dump() if isinstance(draft, NeighborhoodDraft) else draft)
            validate_budget(draft, request)
        except TimeoutError:
            return generation_failure(AIProviderFailure(AIFailureReason.TIMEOUT), started, service.neighborhood_timeout_seconds)
        except AIProviderFailure as error:
            return generation_failure(error, started, service.neighborhood_timeout_seconds)
        except ValueError as error:
            return generation_failure(draft_failure(error), started, service.neighborhood_timeout_seconds)
        except AIProviderError:
            return generation_failure(AIProviderFailure(AIFailureReason.UNAVAILABLE), started, service.neighborhood_timeout_seconds)
        except Exception:
            return generation_failure(AIProviderFailure(AIFailureReason.INTERNAL), started, service.neighborhood_timeout_seconds)
        async with service.factory() as session, session.begin():
            repo = WorldProposalRepository(session)
            player = await repo.admin_player(account_id, player_id)
            if player is None or not await authorized() or service.provider is None:
                return response('Admin session or generation is no longer available.')
            if player.current_room_id != origin_id:
                return response('You left the generation origin. Request a new proposal there.')
            _, exits, current = await repo.source(source_id)
            _, _, current_origin = await repo.source(origin_id)
            if current != fingerprint or current_origin != origin_fingerprint or direction in exits:
                return response('The surrounding world changed. Request a new proposal.')
            if await repo.pending_count(account_id) >= 10:
                return response('Another request filled your pending proposal slots.')
            if any([await repo.duplicate_name(room.name) for room in draft.rooms]):
                return response('A proposed room name already exists. Generate another draft.')
            proposal = WorldProposalRecord(id=str(uuid4()), creator_account_id=account_id,
                source_room_id=source_id, source_fingerprint=fingerprint, direction=direction,
                name=f'Expansion near {request.origin_name}'[:100], description=request.brief,
                schema_version=2, status='pending', payload={'content': draft.model_dump(),
                    'request': request.model_dump(), 'origin_id': origin_id,
                    'origin_fingerprint': origin_fingerprint, 'generate_command': raw})
            session.add(proposal)
            await session.flush()
            return response(preview(proposal, request.anchor_name), True, proposal_id=proposal.id)
    except (ValueError, ValidationError, AIProviderError):
        return response('Invalid generation options or draft. ' + GENERATE_HELP)


def stored_draft(proposal):
    payload = proposal.payload
    if not isinstance(payload, dict) or not {'content', 'request', 'origin_id', 'origin_fingerprint'} <= payload.keys():
        raise ValueError('Invalid stored draft')
    draft = NeighborhoodDraft.model_validate(payload['content'])
    request = NeighborhoodRequest.model_validate(payload['request'])
    validate_budget(draft, request)
    if request.direction != proposal.direction:
        raise ValueError('Stored attachment changed')
    return payload, draft, request


def preview(proposal, source_name: str) -> str:
    _, draft, request = stored_draft(proposal)
    buildings = {b.key: b.name for b in draft.buildings}
    names = {r.key: r.name for r in draft.rooms}
    names['anchor'] = source_name
    object_names = {obj.key: obj.name for obj in draft.objects}
    lines = [f'Neighborhood proposal {proposal.id} [{proposal.status}]',
             f'Origin: {request.origin_name}. Attachment: {source_name}, {request.direction}.',
             f'Brief: {request.brief}',
             f'{len(draft.rooms)} rooms, {len(draft.buildings)} buildings, '
             f'{sum(edge.door is not None for edge in draft.connections)} doors, {len(draft.objects)} objects.']
    for room in draft.rooms:
        lines.extend([f'{room.name} ({buildings.get(room.building, "outdoors")}): {room.description}'])
    for edge in draft.connections:
        lines.append(f'{names[edge.source]} -> {edge.direction} -> {names[edge.destination]} (return: {OPPOSITE[edge.direction]})')
        if edge.door:
            lines.append(f'  Door: {edge.door.name} (closed). {edge.door.description}')
    for obj in draft.objects:
        location = f'in {object_names[obj.container]}' if obj.container else f'at {names[obj.room]}'
        kind = 'container, fixed, closed' if obj.kind == 'container' else obj.kind
        lines.append(f'  {obj.name} ({kind}, {location}): {obj.description}')
    lines.extend(['Draft only. Review every room, connection, and object before publishing.',
                  f'/world approve {proposal.id}', f'/world reject {proposal.id}'])
    return '\n'.join(lines)


async def approve(repo, proposal, player, authorized, enabled) -> dict[str, Any]:
    payload, draft, _ = stored_draft(proposal)
    if player.current_room_id != payload['origin_id']:
        return {'success': False, 'output': 'Return to the generation origin before accepting.'}
    await repo.lock_world()
    _, exits, fingerprint = await repo.source(proposal.source_room_id)
    _, _, origin_fingerprint = await repo.source(payload['origin_id'])
    if not await authorized():
        return {'success': False, 'output': 'Session expired. Please sign in again.'}
    if not enabled():
        return {'success': False, 'output': 'World generation and approval are currently disabled.'}
    if (fingerprint != proposal.source_fingerprint or proposal.direction in exits
            or origin_fingerprint != payload['origin_fingerprint']
            or any([await repo.duplicate_name(room.name) for room in draft.rooms])):
        proposal.status = 'stale'
        proposal.decided_at = func.now()
        return {'success': False, 'output': 'Proposal needs regeneration: the source, exits, or names changed.'}
    session = repo.session
    buildings = {building.key: str(uuid4()) for building in draft.buildings}
    rooms = {room.key: str(uuid4()) for room in draft.rooms}
    rooms['anchor'] = proposal.source_room_id
    objects = {obj.key: str(uuid4()) for obj in draft.objects}
    session.add_all([BuildingRecord(id=buildings[b.key], name=b.name) for b in draft.buildings])
    await session.flush()
    session.add_all([RoomRecord(id=rooms[r.key], name=r.name, description=r.description,
                               building_id=buildings.get(r.building)) for r in draft.rooms])
    await session.flush()
    for edge in draft.connections:
        door_id = None
        if edge.door:
            door_id = str(uuid4())
            session.add(DoorRecord(id=door_id, name=edge.door.name, description=edge.door.description,
                room_id=rooms[edge.source], destination_room_id=rooms[edge.destination], is_open=False))
            await session.flush()
        session.add_all([
            ExitRecord(room_id=rooms[edge.source], direction=edge.direction,
                       destination_room_id=rooms[edge.destination], door_id=door_id),
            ExitRecord(room_id=rooms[edge.destination], direction=OPPOSITE[edge.direction],
                       destination_room_id=rooms[edge.source], door_id=door_id)])
    for contained in [False, True]:
        for obj in draft.objects:
            if (obj.container is not None) == contained:
                session.add(ItemRecord(id=objects[obj.key], name=obj.name, description=obj.description,
                    room_id=rooms.get(obj.room), container_id=objects.get(obj.container),
                    portable=obj.kind == 'portable', can_open=obj.kind == 'container'))
        await session.flush()
    proposal.status = 'approved'
    proposal.decided_at = func.now()
    proposal.result_room_id = rooms[next(edge.destination for edge in draft.connections if edge.source == 'anchor')]
    await session.flush()
    return {'success': True, 'output': f'Accepted {proposal.name}. {len(draft.rooms)} rooms added.',
            'proposal_id': proposal.id, 'room_id': proposal.result_room_id, '_world_source': proposal.source_room_id,
            '_world_notice': 'New places are available nearby. Use look to see the exits.'}
