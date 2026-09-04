import logging

import pytest
from starlette.websockets import WebSocketDisconnect

from app.ai.fake import FakeAIProvider
from app.api import websocket as websocket_api


@pytest.mark.parametrize(
    ("command", "expected_action", "secret"),
    [
        ("examine private-keepsake-7419", "examine", "private-keepsake-7419"),
        ("tell Nobody private-message-8527", "tell", "private-message-8527"),
    ],
)
def test_websocket_logs_command_metadata_without_content(
    test_client, caplog, command, expected_action, secret
):
    with caplog.at_level(logging.DEBUG, logger="app.api.websocket"):
        with test_client.websocket_connect("/ws?username=LoggerTest") as websocket:
            websocket.receive_json()
            websocket.send_text(command)
            websocket.receive_json()

    assert secret not in caplog.text
    assert command not in caplog.text
    assert f"action={expected_action}" in caplog.text
    assert f"bytes={len(command.encode('utf-8'))}" in caplog.text
    assert "success=" in caplog.text


def test_websocket_accepts_a_trusted_browser_origin(test_client):
    with test_client.websocket_connect(
        "/ws?username=Trusted",
        headers={"origin": "http://localhost:5173"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "system"


def test_websocket_rejects_an_untrusted_browser_origin(test_client):
    with pytest.raises(WebSocketDisconnect) as denied:
        with test_client.websocket_connect(
            "/ws?username=Untrusted",
            headers={"origin": "https://evil.example"},
        ):
            pass

    assert denied.value.code == 1008


def test_websocket_accepts_a_client_without_an_origin_header(test_client):
    with test_client.websocket_connect("/ws?username=NativeClient") as websocket:
        assert websocket.receive_json()["type"] == "system"


def test_websocket_rejects_an_oversized_command(test_client, monkeypatch):
    monkeypatch.setattr(websocket_api.settings, "max_command_bytes", 4)

    with test_client.websocket_connect("/ws?username=Verbose") as websocket:
        websocket.receive_json()
        websocket.send_text("north")
        assert websocket.receive_json() == {
            "type": "error",
            "text": "Command is too large.",
        }
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()

    assert closed.value.code == 1009


def test_websocket_rate_limits_commands_per_connection(test_client, monkeypatch):
    monkeypatch.setattr(websocket_api.settings, "command_rate_limit", 2)
    monkeypatch.setattr(websocket_api.settings, "command_rate_window_seconds", 60.0)

    with test_client.websocket_connect("/ws?username=Rapid") as websocket:
        websocket.receive_json()
        for _ in range(2):
            websocket.send_text("look")
            assert websocket.receive_json()["success"] is True

        websocket.send_text("look")
        assert websocket.receive_json() == {
            "type": "error",
            "text": "Command rate limit exceeded.",
        }
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()

    assert closed.value.code == 1008


def test_websocket_enforces_the_concurrent_connection_limit(test_client, monkeypatch):
    monkeypatch.setattr(websocket_api.settings, "max_websocket_connections", 1)

    with test_client.websocket_connect("/ws?username=First") as first:
        first.receive_json()
        with pytest.raises(WebSocketDisconnect) as denied:
            with test_client.websocket_connect("/ws?username=Second"):
                pass

    assert denied.value.code == 1013


def test_websocket_rate_limits_connection_attempts_by_source(test_client, monkeypatch):
    websocket_api.connection_attempts.clear()
    monkeypatch.setattr(websocket_api.settings, "connection_attempt_limit", 1)
    monkeypatch.setattr(websocket_api.settings, "connection_attempt_window_seconds", 60.0)

    try:
        with test_client.websocket_connect("/ws?username=FirstAttempt") as first:
            first.receive_json()
        with pytest.raises(WebSocketDisconnect) as denied:
            with test_client.websocket_connect("/ws?username=SecondAttempt"):
                pass
        assert denied.value.code == 1013
    finally:
        websocket_api.connection_attempts.clear()


def test_websocket_connections_have_independent_player_state(test_client):
    with test_client.websocket_connect("/ws?username=Alan") as first:
        first_welcome = first.receive_json()
        assert first_welcome["type"] == "system"
        assert first_welcome["room_name"] == "Town Square"

        with test_client.websocket_connect("/ws?username=Robin") as second:
            second.receive_json()

            first.send_text("north")
            first_move = first.receive_json()
            assert first_move["success"] is True
            assert first_move["room_id"] == "forest"
            assert second.receive_json()["text"] == "Alan leaves to the north."

            second.send_text("look")
            second_look = second.receive_json()
            assert second_look["success"] is True
            assert second_look["room_id"] == "town_square"
            assert "Town Square" in second_look["text"]
            assert second_look["metadata"] == {"command_source": "classic"}


def test_websocket_exposes_ai_interpretation_metadata(test_client, monkeypatch):
    monkeypatch.setattr(websocket_api.game_service, "ai_provider", FakeAIProvider())

    with test_client.websocket_connect("/ws?username=NaturalSpeaker") as websocket:
        websocket.receive_json()
        websocket.send_text("walk toward the docks")
        result = websocket.receive_json()

    assert result["success"] is True
    assert result["room_id"] == "docks"
    assert result["metadata"] == {"command_source": "ai"}


def test_only_one_websocket_player_can_take_a_shared_item(test_client):
    with test_client.websocket_connect("/ws?username=Alan") as first:
        first.receive_json()
        with test_client.websocket_connect("/ws?username=Robin") as second:
            second.receive_json()

            first.send_text("take torch")
            first_result = first.receive_json()
            assert second.receive_json()["text"] == "Alan picks up the torch."
            second.send_text("take torch")
            second_result = second.receive_json()

            assert first_result["success"] is True
            assert first_result["text"] == "You take the torch."
            assert second_result["success"] is False
            assert second_result["text"] == "You do not see a torch here."


def test_duplicate_connected_username_is_rejected(test_client):
    with test_client.websocket_connect("/ws?username=Alan") as first:
        first.receive_json()
        with test_client.websocket_connect("/ws?username=%20ALAN%20") as second:
            error = second.receive_json()

            assert error == {
                "type": "error",
                "text": "That username is already connected.",
            }


def test_players_can_see_and_speak_to_others_in_the_same_room(test_client):
    with test_client.websocket_connect("/ws?username=Alan") as alan:
        alan.receive_json()
        with test_client.websocket_connect("/ws?username=Robin") as robin:
            robin.receive_json()

            alan.send_text("look")
            assert "Also here: Robin." in alan.receive_json()["text"]

            alan.send_text("say Hello, Robin!")
            assert alan.receive_json()["text"] == 'You say, "Hello, Robin!"'
            assert robin.receive_json()["text"] == 'Alan says, "Hello, Robin!"'

            robin.send_text("north")
            robin.receive_json()
            assert alan.receive_json()["text"] == "Robin leaves to the north."
            alan.send_text("say Can you hear me?")
            assert alan.receive_json()["text"] == 'You say, "Can you hear me?"'


def test_movement_output_lists_players_already_in_the_destination(test_client):
    with test_client.websocket_connect("/ws?username=Alan") as alan:
        alan.receive_json()
        with test_client.websocket_connect("/ws?username=Robin") as robin:
            robin.receive_json()

            robin.send_text("north")
            robin.receive_json()
            assert alan.receive_json()["text"] == "Robin leaves to the north."

            alan.send_text("north")
            movement = alan.receive_json()

            assert movement["success"] is True
            assert movement["room_id"] == "forest"
            assert "Also here: Robin." in movement["text"]
            assert robin.receive_json()["text"] == "Alan arrives from the south."


def test_players_can_tell_and_atomically_give_items(test_client):
    with test_client.websocket_connect("/ws?username=Alan") as alan:
        alan.receive_json()
        with test_client.websocket_connect("/ws?username=Robin") as robin:
            robin.receive_json()

            alan.send_text("say to Robin This is private.")
            assert alan.receive_json()["text"] == 'You tell Robin, "This is private."'
            assert robin.receive_json()["text"] == 'Alan tells you, "This is private."'

            alan.send_text("take torch")
            alan.receive_json()
            assert robin.receive_json()["text"] == "Alan picks up the torch."
            alan.send_text("give torch to Robin")
            assert alan.receive_json()["text"] == "You give the torch to Robin."
            assert robin.receive_json()["text"] == "Alan gives you the torch."

            robin.send_text("inventory")
            assert robin.receive_json()["text"] == "Inventory: torch"


def test_telling_yourself_returns_a_random_playful_warning(test_client):
    from app.services.game import SELF_TALK_RESPONSES

    with test_client.websocket_connect("/ws?username=Alan") as alan:
        alan.receive_json()

        alan.send_text("say to Alan Hello, me.")
        say_to_result = alan.receive_json()
        alan.send_text("tell ALAN Still there?")
        tell_result = alan.receive_json()

        assert say_to_result["success"] is False
        assert say_to_result["text"] in SELF_TALK_RESPONSES
        assert tell_result["success"] is False
        assert tell_result["text"] in SELF_TALK_RESPONSES


def test_who_lists_only_connected_players_and_their_rooms(test_client):
    with test_client.websocket_connect("/ws?username=Robin") as robin:
        robin.receive_json()
        robin.send_text("north")
        robin.receive_json()

        with test_client.websocket_connect("/ws?username=Alan") as alan:
            alan.receive_json()
            alan.send_text("who")
            result = alan.receive_json()

            assert result["success"] is True
            assert result["text"] == (
                "Players online (2):\n"
                "- Alan — Town Square\n"
                "- Robin — Forest"
            )
