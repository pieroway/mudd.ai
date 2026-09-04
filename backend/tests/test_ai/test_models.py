import pytest
from pydantic import ValidationError

from app.ai.models import InterpretCommandRequest, InterpretCommandResponse


def test_interpretation_request_accepts_non_empty_player_input():
    request = InterpretCommandRequest(raw_input="walk toward the docks")

    assert request.raw_input == "walk toward the docks"


def test_interpretation_request_rejects_blank_input():
    with pytest.raises(ValidationError):
        InterpretCommandRequest(raw_input="   ")


def test_interpretation_response_accepts_move_with_direction():
    response = InterpretCommandResponse.model_validate(
        {"command": {"action": "move", "direction": "south"}}
    )

    assert response.command.action == "move"
    assert response.command.direction == "south"


def test_interpretation_response_accepts_target_action():
    response = InterpretCommandResponse.model_validate(
        {"command": {"action": "examine", "target": "brass lantern"}}
    )

    assert response.command.action == "examine"
    assert response.command.target == "brass lantern"


@pytest.mark.parametrize(
    "payload",
    [
        {"command": {"action": "teleport", "direction": "north"}},
        {"command": {"action": "move"}},
        {"command": {"action": "look", "target": "hidden door"}},
        {"command": {"action": "take", "target": ""}},
        {"command": {"action": "take", "target": "torch", "success": True}},
        {"command": {"action": "tell", "target_player": "alan"}},
        {"command": {"action": "take_from", "target": "coin"}},
        {"command": {"action": "who", "page": 0}},
        {"command": {"action": "help"}, "authoritative": True},
    ],
)
def test_interpretation_response_rejects_invalid_commands(payload):
    with pytest.raises(ValidationError):
        InterpretCommandResponse.model_validate(payload)


def test_validated_command_serializes_to_parser_compatible_shape():
    response = InterpretCommandResponse.model_validate(
        {
            "command": {
                "action": "give",
                "target": "torch",
                "target_player": "mira",
            }
        }
    )

    assert response.command.model_dump() == {
        "action": "give",
        "target": "torch",
        "target_player": "mira",
    }
