import asyncio
import json

import httpx
import pytest

from app.ai.models import InterpretCommandRequest
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
