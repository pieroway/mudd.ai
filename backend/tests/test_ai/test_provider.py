import pytest

from app.ai.models import InterpretCommandRequest, InterpretCommandResponse
from app.ai.provider import AIProvider


class IncompleteProvider(AIProvider):
    pass


class StubProvider(AIProvider):
    async def interpret_command(
        self, request: InterpretCommandRequest
    ) -> InterpretCommandResponse:
        assert request.raw_input == "head toward the forest"
        return InterpretCommandResponse.model_validate(
            {"command": {"action": "move", "direction": "north"}}
        )


def test_provider_requires_command_interpretation_implementation():
    with pytest.raises(TypeError, match="interpret_command"):
        IncompleteProvider()


async def test_provider_contract_uses_typed_request_and_response():
    provider = StubProvider()

    response = await provider.interpret_command(
        InterpretCommandRequest(raw_input="head toward the forest")
    )

    assert response.command.action == "move"
    assert response.command.direction == "north"
