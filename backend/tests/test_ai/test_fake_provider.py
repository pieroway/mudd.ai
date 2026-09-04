import pytest
from pydantic import ValidationError

from app.ai.fake import FakeAIProvider
from app.ai.models import InterpretCommandRequest
from app.ai.provider import CommandNotInterpretedError


@pytest.mark.parametrize(
    ("raw_input", "expected_command"),
    [
        (
            "walk toward the docks",
            {"action": "move", "direction": "south"},
        ),
        (
            "look carefully at the torch",
            {"action": "examine", "target": "torch"},
        ),
    ],
)
async def test_default_fixtures_return_deterministic_commands(raw_input, expected_command):
    provider = FakeAIProvider()

    response = await provider.interpret_command(InterpretCommandRequest(raw_input=raw_input))

    assert response.command.model_dump() == expected_command


async def test_fixture_matching_is_case_insensitive_and_records_requests():
    provider = FakeAIProvider()
    request = InterpretCommandRequest(raw_input="Walk Toward The Docks")

    await provider.interpret_command(request)

    assert provider.requests == [request]


async def test_unknown_input_fails_explicitly():
    provider = FakeAIProvider()

    with pytest.raises(CommandNotInterpretedError, match="No fake interpretation fixture"):
        await provider.interpret_command(
            InterpretCommandRequest(raw_input="perform an undocumented action")
        )


async def test_custom_fixtures_are_supported():
    provider = FakeAIProvider(
        fixtures={"study the chest": {"command": {"action": "examine", "target": "chest"}}}
    )

    response = await provider.interpret_command(
        InterpretCommandRequest(raw_input="study the chest")
    )

    assert response.command.model_dump() == {"action": "examine", "target": "chest"}


def test_custom_fixtures_are_schema_validated_at_construction():
    with pytest.raises(ValidationError):
        FakeAIProvider(
            fixtures={"cheat": {"command": {"action": "teleport", "direction": "north"}}}
        )
