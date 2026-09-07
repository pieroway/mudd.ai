"""Deterministic AI provider for development and automated tests."""

from __future__ import annotations

from collections.abc import Mapping

from app.ai.models import InterpretCommandRequest, InterpretCommandResponse
from app.ai.narration import NarrationRequest, NarrationResponse
from app.ai.provider import AIProvider, CommandNotInterpretedError


DEFAULT_COMMAND_FIXTURES: dict[str, dict[str, object]] = {
    "walk toward the docks": {
        "command": {"action": "move", "direction": "south"},
    },
    "look carefully at the torch": {
        "command": {"action": "examine", "target": "torch"},
    },
}


class FakeAIProvider(AIProvider):
    """Return validated responses from explicit, normalized phrase fixtures."""

    def __init__(self, fixtures: Mapping[str, dict[str, object]] | None = None) -> None:
        fixture_payloads = DEFAULT_COMMAND_FIXTURES if fixtures is None else fixtures
        self._fixtures = {
            phrase.strip().casefold(): InterpretCommandResponse.model_validate(payload)
            for phrase, payload in fixture_payloads.items()
        }
        self.requests: list[InterpretCommandRequest] = []
        self.narration_requests: list[NarrationRequest] = []

    async def narrate_result(self, request: NarrationRequest) -> NarrationResponse:
        self.narration_requests.append(request.model_copy(deep=True))
        fixtures = {
            "You take the torch.": "You gather up the torch.",
            "You open the chest.": "You lift the chest's lid, opening it.",
            "You close the chest.": "You lower the chest's lid, closing it.",
        }
        return NarrationResponse(
            text=fixtures.get(request.authoritative_text, request.authoritative_text)
        )

    async def interpret_command(
        self, request: InterpretCommandRequest
    ) -> InterpretCommandResponse:
        self.requests.append(request.model_copy(deep=True))
        response = self._fixtures.get(request.raw_input.casefold())
        if response is None:
            raise CommandNotInterpretedError(
                f"No fake interpretation fixture for: {request.raw_input!r}"
            )
        return response.model_copy(deep=True)
