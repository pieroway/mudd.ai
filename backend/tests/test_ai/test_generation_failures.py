import asyncio
import json

import httpx
import pytest

from app.ai.fake import FakeAIProvider
from app.ai.neighborhood import NeighborhoodRequest
from app.ai.provider import AIFailureReason, AIProviderFailure
from tests.test_ai.test_openai_provider import envelope, provider

SECRET = 'PRIVATE-API-KEY-AND-PLAYER-TEXT'


def request():
    return NeighborhoodRequest(brief=SECRET, origin_name='Forest', anchor_name='Forest',
        anchor_description='Trees.', direction='north', max_rooms=2, max_buildings=1)


async def allowed():
    return True


@pytest.mark.parametrize('status,reason', [
    (400, AIFailureReason.API_REQUEST), (401, AIFailureReason.AUTH),
    (403, AIFailureReason.AUTH), (404, AIFailureReason.API_REQUEST),
    (429, AIFailureReason.RATE_LIMIT), (500, AIFailureReason.API_SERVER),
    (503, AIFailureReason.API_SERVER), (302, AIFailureReason.API_REQUEST),
])
async def test_http_errors_keep_only_status_and_fixed_reason(status, reason, caplog):
    calls, charges = [], []
    async def reserve():
        charges.append(True)
        return True
    def handler(http_request):
        calls.append(http_request)
        return httpx.Response(status, text=SECRET, headers={'location': 'https://example.com/' + SECRET})
    adapter = provider(handler)
    with pytest.raises(AIProviderFailure) as caught:
        await adapter.generate_neighborhood(request(), before_dispatch=reserve)
    assert caught.value.reason == reason
    assert caught.value.http_status == status
    assert SECRET not in str(caught.value) + caplog.text
    assert caught.value.__suppress_context__
    assert len(calls) == len(charges) == 1 and adapter._active == 0


@pytest.mark.parametrize('payload,reason', [
    ({'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}, 'output': []}, AIFailureReason.OUTPUT_LIMIT),
    ({'status': 'incomplete', 'incomplete_details': {'reason': 'content_filter'}, 'output': []}, AIFailureReason.REFUSAL),
    ({'status': 'incomplete', 'incomplete_details': {'reason': SECRET}, 'output': []}, AIFailureReason.INCOMPLETE),
    ({'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant',
       'content': [{'type': 'refusal', 'refusal': SECRET}]}]}, AIFailureReason.REFUSAL),
    ({'status': 'completed', 'output': [None]}, AIFailureReason.INVALID_RESPONSE),
    ({'status': 'incomplete', 'incomplete_details': SECRET}, AIFailureReason.INVALID_RESPONSE),
    (envelope(SECRET), AIFailureReason.INVALID_DRAFT),
])
async def test_response_failure_categories(payload, reason, caplog):
    adapter = provider(lambda _: httpx.Response(200, json=payload))
    with pytest.raises(AIProviderFailure) as caught:
        await adapter.generate_neighborhood(request(), before_dispatch=allowed)
    assert caught.value.reason == reason
    assert SECRET not in str(caught.value) + caplog.text
    assert adapter._active == 0


@pytest.mark.parametrize('failure,reason', [
    (httpx.ReadTimeout(SECRET), AIFailureReason.TIMEOUT),
    (httpx.ConnectError(SECRET), AIFailureReason.NETWORK),
])
async def test_transport_failure_categories(failure, reason):
    def handler(_):
        raise failure
    adapter = provider(handler)
    with pytest.raises(AIProviderFailure) as caught:
        await adapter.generate_neighborhood(request(), before_dispatch=allowed)
    assert caught.value.reason == reason and SECRET not in str(caught.value)
    assert adapter._active == 0


async def test_timeout_busy_and_lifetime_limit_are_distinct_and_capacity_is_released():
    started = asyncio.Event()
    charges = []
    async def reserve():
        charges.append(True)
        return True
    async def handler(_):
        started.set()
        await asyncio.Event().wait()
    adapter = provider(handler, ai_neighborhood_timeout_seconds=0.1, ai_command_max_concurrent=1)
    pending = asyncio.create_task(adapter.generate_neighborhood(request(), before_dispatch=reserve))
    await started.wait()
    with pytest.raises(AIProviderFailure) as busy:
        await adapter.generate_neighborhood(request(), before_dispatch=reserve)
    assert busy.value.reason == AIFailureReason.BUSY
    with pytest.raises(AIProviderFailure) as timeout:
        await pending
    assert timeout.value.reason == AIFailureReason.TIMEOUT
    assert len(charges) == 1 and adapter._active == 0
    adapter._settings.ai_command_max_requests = 1
    with pytest.raises(AIProviderFailure) as limit:
        await adapter.generate_neighborhood(request(), before_dispatch=reserve)
    assert limit.value.reason == AIFailureReason.REQUEST_LIMIT
    assert len(charges) == 1


async def test_callback_failure_keeps_reason_and_does_not_dispatch_or_reserve_capacity():
    calls = []
    def handler(_):
        calls.append(True)
        return httpx.Response(500)
    async def denied():
        raise AIProviderFailure(AIFailureReason.ALLOWANCE)
    adapter = provider(handler)
    with pytest.raises(AIProviderFailure) as caught:
        await adapter.generate_neighborhood(request(), before_dispatch=denied)
    assert caught.value.reason == AIFailureReason.ALLOWANCE
    assert calls == [] and adapter._requests == adapter._active == 0


async def test_response_byte_limit_is_distinct():
    adapter = provider(lambda _: httpx.Response(200, content=b'x' * 65537))
    with pytest.raises(AIProviderFailure) as caught:
        await adapter.generate_neighborhood(request(), before_dispatch=allowed)
    assert caught.value.reason == AIFailureReason.RESPONSE_SIZE


@pytest.mark.parametrize('mutation,detail', [
    ('door', 'Building entrances require doors'),
    ('prose', 'Rooms allow at most three sentences'),
    ('budget', 'Draft exceeds requested budget'),
    ('schema', None),
])
async def test_validation_exposes_only_allowlisted_local_rules(mutation, detail, caplog):
    draft = (await FakeAIProvider().generate_neighborhood(request(), before_dispatch=allowed)).model_dump()
    if mutation == 'door':
        draft['connections'][1]['door'] = None
    elif mutation == 'prose':
        draft['rooms'][0]['description'] = f'{SECRET}. Two. Three. Four.'
    elif mutation == 'schema':
        draft[SECRET] = SECRET
    query = request()
    if mutation == 'budget':
        query = query.model_copy(update={'max_rooms': 1})
    adapter = provider(lambda _: httpx.Response(200, json=envelope(json.dumps(draft))))
    with pytest.raises(AIProviderFailure) as caught:
        await adapter.generate_neighborhood(query, before_dispatch=allowed)
    assert caught.value.reason == AIFailureReason.INVALID_DRAFT
    assert caught.value.detail == detail
    assert SECRET not in str(caught.value) + caplog.text
