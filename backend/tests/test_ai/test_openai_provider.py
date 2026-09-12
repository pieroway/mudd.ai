import asyncio
import json

import httpx
import pytest

from app.ai.models import InterpretCommandRequest
from app.ai.narration import NarrationRequest
from app.ai.npc import NPCRequest
from app.ai.world import WorldGenerationRequest
from app.ai.neighborhood import NeighborhoodRequest
from app.ai.fake import FakeAIProvider
from app.domain.npc import EDRIC_GOALS, EDRIC_KNOWLEDGE, EDRIC_PERSONALITY
from app.ai.openai import OpenAIProvider, command_schema
from app.ai.provider import AIProviderError
from app.config import Settings


def provider(handler, **overrides):
    settings = Settings(
        _env_file=None, openai_api_key="test-secret", ai_model="test-model", **overrides
    )
    return OpenAIProvider(settings, transport=httpx.MockTransport(handler))


def envelope(text='{"command":{"action":"move","direction":"north"}}'):
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }


def npc_request():
    return NPCRequest(
        name="Edric", personality=EDRIC_PERSONALITY, goals=EDRIC_GOALS,
        knowledge=EDRIC_KNOWLEDGE, relationship="stranger", recent_conversation=[], message="Hello",
    )


async def test_neighborhood_contract_capacity_and_allowance():
    request = NeighborhoodRequest(brief='Quiet', origin_name='Forest', anchor_name='Forest',
        anchor_description='Trees.', direction='north', max_rooms=2, max_buildings=1)
    charges, calls = [], []
    async def reserve():
        charges.append(True)
        return True
    async def allowed():
        return True
    draft = await FakeAIProvider().generate_neighborhood(request, before_dispatch=allowed)
    def handler(http_request):
        body = json.loads(http_request.content)
        calls.append(body)
        assert body['max_output_tokens'] == 8192
        assert body['store'] is False and 'tools' not in body
        assert json.loads(body['input'][0]['content']) == request.model_dump()
        schema = body['text']['format']['schema']
        assert body['text']['format']['name'] == 'mud_neighborhood'
        for model in [schema, *schema['$defs'].values()]:
            assert model['additionalProperties'] is False
            assert set(model['required']) == set(model['properties'])
        return httpx.Response(200, json=envelope(draft.model_dump_json()))
    adapter = provider(handler, ai_command_max_requests=1)
    assert await adapter.generate_neighborhood(request, before_dispatch=reserve) == draft
    with pytest.raises(AIProviderError):
        await adapter.generate_neighborhood(request, before_dispatch=reserve)
    assert len(charges) == len(calls) == 1


async def test_neighborhood_denied_allowance_and_invalid_response():
    request = NeighborhoodRequest(brief='Quiet', origin_name='Forest', anchor_name='Forest',
        anchor_description='Trees.', direction='north', max_rooms=1, max_buildings=0)
    calls = []
    def handler(http_request):
        calls.append(http_request)
        return httpx.Response(200, json=envelope('{"rooms": [], "secret": "PRIVATE"}'))
    async def denied():
        return False
    async def allowed():
        return True
    adapter = provider(handler)
    with pytest.raises(AIProviderError):
        await adapter.generate_neighborhood(request, before_dispatch=denied)
    assert calls == [] and adapter._active == adapter._requests == 0
    with pytest.raises(AIProviderError, match='invalid_draft'):
        await adapter.generate_neighborhood(request, before_dispatch=allowed)
    assert len(calls) == 1 and adapter._active == 0


async def test_world_contract_budget_and_capacity_before_allowance():
    charges = []
    calls = []
    async def reserve():
        charges.append(True)
        return True
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["max_output_tokens"] == 1024
        assert body["store"] is False and "tools" not in body
        assert body["text"]["format"]["name"] == "mud_room"
        assert set(body["text"]["format"]["schema"]["properties"]) == {"name", "description"}
        return httpx.Response(200, json=envelope('{"name":"Glade","description":"Still air."}'))
    adapter = provider(handler, ai_command_max_requests=1)
    request = WorldGenerationRequest(brief="Quiet", source_name="Forest", source_description="Trees.",
                                     direction="north", return_direction="south")
    assert (await adapter.generate_room(request, before_dispatch=reserve)).name == "Glade"
    with pytest.raises(AIProviderError):
        await adapter.generate_room(request, before_dispatch=reserve)
    assert len(charges) == len(calls) == 1


async def test_world_allowance_refusal_does_not_dispatch():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(500)
    async def denied():
        return False
    adapter = provider(handler)
    request = WorldGenerationRequest(brief="Quiet", source_name="Forest", source_description="Trees.",
                                     direction="north", return_direction="south")
    with pytest.raises(AIProviderError):
        await adapter.generate_room(request, before_dispatch=denied)
    assert calls == [] and adapter._active == adapter._requests == 0


async def test_npc_contract_and_shared_request_limit():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["store"] is False
        assert "tools" not in body and "previous_response_id" not in body
        assert json.loads(body["input"][0]["content"]) == npc_request().model_dump()
        assert body["text"]["format"]["name"] == "mud_npc"
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        assert list(body["text"]["format"]["schema"]["properties"]) == ["text"]
        return httpx.Response(200, json=envelope('{"text":"Welcome, traveler."}'))

    adapter = provider(handler, ai_command_max_requests=1)
    assert (await adapter.npc_response(npc_request())).text == "Welcome, traveler."
    with pytest.raises(AIProviderError, match="limit"):
        await adapter.interpret_command(InterpretCommandRequest(raw_input="head north please"))
    assert len(calls) == 1


@pytest.mark.parametrize("text", [
    '{"text":"ok","inventory":["gold"]}', '{"text":""}',
    json.dumps({"text": "x" * 601}), '{"text":42}', 'not json',
])
async def test_npc_rejects_invalid_provider_text(text):
    adapter = provider(lambda request: httpx.Response(200, json=envelope(text)))
    with pytest.raises(AIProviderError, match="unavailable"):
        await adapter.npc_response(npc_request())


async def test_narration_contract_and_shared_request_limit():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["store"] is False
        assert "tools" not in body and "previous_response_id" not in body
        assert json.loads(body["input"][0]["content"]) == {
            "action": "open", "success": True, "authoritative_text": "You open the chest."
        }
        assert body["text"]["format"]["name"] == "mud_narration"
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        return httpx.Response(200, json=envelope('{"text":"You lift the chest lid."}'))

    adapter = provider(handler, ai_command_max_requests=1)
    result = await adapter.narrate_result(NarrationRequest(
        action="open", success=True, authoritative_text="You open the chest."
    ))
    assert result.text == "You lift the chest lid."
    with pytest.raises(AIProviderError, match="limit"):
        await adapter.interpret_command(InterpretCommandRequest(raw_input="head north please"))
    assert len(calls) == 1


@pytest.mark.parametrize("text", [
    '{"text":"ok","inventory":["gold"]}', '{"text":""}',
    json.dumps({"text": "x" * 2001}), '{"text":42}', 'not json',
])
async def test_narration_rejects_invalid_provider_text(text):
    adapter = provider(lambda request: httpx.Response(200, json=envelope(text)))
    with pytest.raises(AIProviderError, match="unavailable"):
        await adapter.narrate_result(NarrationRequest(
            action="open", success=False, authoritative_text="It is already open."
        ))


async def test_request_privacy_and_validated_proposal():
    def handler(request):
        body = json.loads(request.content)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["authorization"] == "Bearer test-secret"
        assert body["store"] is False
        assert body["input"] == [{"role": "user", "content": "head north please"}]
        assert body["max_output_tokens"] == 512
        assert body["text"]["format"]["strict"] is True
        assert "tools" not in body and "previous_response_id" not in body
        return httpx.Response(200, json=envelope())

    result = await provider(handler).interpret_command(
        InterpretCommandRequest(raw_input="head north please")
    )
    assert result.command.model_dump() == {"action": "move", "direction": "north"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"status": "incomplete", "output": []},
        envelope("not json"),
        envelope('{"command":null}'),
        envelope('{"command":{"action":"move","direction":"teleport"}}'),
        envelope('{"command":{"action":"look","gold":999}}'),
        {
            "status": "completed",
            "output": [{"type": "message", "role": "assistant", "content": [{"type": "refusal"}]}],
        },
        {"status": "completed", "output": [None]},
    ],
)
async def test_untrusted_responses_fail_safely(payload):
    adapter = provider(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(AIProviderError, match="unavailable"):
        await adapter.interpret_command(InterpretCommandRequest(raw_input="secret player text"))


@pytest.mark.parametrize("status", [302, 401, 429, 500])
async def test_http_failures_never_retry_or_expose_response(status, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="secret player text test-secret",
            headers={"location": "https://example.com"},
        )

    with pytest.raises(AIProviderError) as error:
        await provider(handler).interpret_command(
            InterpretCommandRequest(raw_input="secret player text")
        )
    assert len(calls) == 1
    assert "test-secret" not in str(error.value) + caplog.text
    assert "secret player text" not in str(error.value) + caplog.text


async def test_input_and_lifetime_request_limits():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=envelope())

    adapter = provider(handler, ai_command_max_input_bytes=4, ai_command_max_requests=1)
    with pytest.raises(AIProviderError):
        await adapter.interpret_command(InterpretCommandRequest(raw_input="🔥🔥"))
    assert not calls
    await adapter.interpret_command(InterpretCommandRequest(raw_input="go"))
    with pytest.raises(AIProviderError):
        await adapter.interpret_command(InterpretCommandRequest(raw_input="go"))
    assert len(calls) == 1


async def test_timeout_and_concurrency_release_capacity():
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    adapter = provider(handler, ai_command_timeout_seconds=0.05, ai_command_max_concurrent=1)
    task = asyncio.create_task(adapter.interpret_command(InterpretCommandRequest(raw_input="go")))
    await started.wait()
    with pytest.raises(AIProviderError, match="limit"):
        await adapter.interpret_command(InterpretCommandRequest(raw_input="go"))
    with pytest.raises(AIProviderError):
        await task
    assert adapter._active == 0


async def test_response_size_limit():
    adapter = provider(lambda request: httpx.Response(200, content=b"x" * 65537))
    with pytest.raises(AIProviderError):
        await adapter.interpret_command(InterpretCommandRequest(raw_input="go"))


def test_wire_schema_uses_supported_union_and_required_fields():
    schema = command_schema()

    def check(node):
        if isinstance(node, dict):
            assert "oneOf" not in node and "discriminator" not in node and "default" not in node
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(schema)
