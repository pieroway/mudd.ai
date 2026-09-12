import logging
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.websockets import WebSocketDisconnect

from app.ai.fake import FakeAIProvider
from app.api import websocket as websocket_api
from app.db import get_session_factory
from app.services.ai_preferences import set_admin


def test_admin_grants_refresh_only_recipient_and_support_self(game_client):
    game_client.admin_usernames.add("creditadmin")
    with game_client.websocket_connect("/ws?username=CreditAdmin") as admin:
        assert admin.receive_json()["ai_usage"]["remaining"] == 50
        with game_client.websocket_connect("/ws?username=Recipient") as recipient:
            recipient.receive_json()
            with game_client.websocket_connect("/ws?username=Bystander") as bystander:
                bystander.receive_json()
                admin.send_text("/ai credits add Recipient 75")
                assert "Added 75 AI credits" in admin.receive_json()["text"]
                notice = recipient.receive_json()
                assert notice["ai_usage"]["bonus_credits"] == 75
                assert notice["ai_usage"]["remaining"] == 125
                bystander.send_text("look")
                assert bystander.receive_json()["ai_usage"]["bonus_credits"] == 0
                recipient.send_text("/ai credits add Recipient")
                assert not recipient.receive_json()["success"]
                admin.send_text("/ai credits add CreditAdmin")
                result = admin.receive_json()
                assert result["success"] and result["ai_usage"]["bonus_credits"] == 50
                assert result["ai_usage"]["used"] == 0
    with game_client.websocket_connect("/ws?username=Recipient") as recipient:
        assert recipient.receive_json()["ai_usage"]["bonus_credits"] == 75


def test_npc_dialogue_is_private_and_memory_survives_reconnect(game_client, monkeypatch):
    provider = FakeAIProvider()
    monkeypatch.setattr(websocket_api.game_service.npc_service, "provider", provider)
    with game_client.websocket_connect("/ws?username=Visitor") as first:
        first.receive_json()
        first.send_text("east")
        assert "NPCs here: Edric" in first.receive_json()["text"]
        with game_client.websocket_connect("/ws?username=Bystander") as second:
            second.receive_json()
            second.send_text("east")
            second.receive_json()
            assert "Bystander arrives" in first.receive_json()["text"]
            first.send_text("talk edric private-keepsake-7419")
            reply = first.receive_json()
            assert reply["type"] == "game_output" and reply["success"]
            assert "[NPC] Edric" in reply["text"]
            assert reply["state"]["room_id"] == "inn"
            assert reply["ai_usage"]["remaining"] == 49
            second.send_text("look")
            # FIFO: any leaked dialogue would arrive before this look result.
            assert "NPCs here: Edric" in second.receive_json()["text"]
            second.send_text("talk edric hello")
            assert "Welcome, traveler" in second.receive_json()["text"]
            assert provider.npc_requests[-1].recent_conversation == []
    with game_client.websocket_connect("/ws?username=Visitor") as reconnected:
        reconnected.receive_json()
        reconnected.send_text("talk edric remember me?")
        assert "private-keepsake-7419" in reconnected.receive_json()["text"]


def test_narration_follows_authoritative_output_and_preserves_inventory(game_client, monkeypatch):
    provider = FakeAIProvider()
    monkeypatch.setattr(websocket_api.game_service, "narration_enabled", True)
    monkeypatch.setattr(websocket_api.narration_service, "provider", provider)
    monkeypatch.setattr(websocket_api.narration_service, "daily_request_limit", 1)
    monkeypatch.setattr(websocket_api.settings, "ai_daily_request_limit", 1)
    game_client.admin_usernames.add("narratortest")
    with game_client.websocket_connect("/ws?username=NarratorTest") as websocket:
        websocket.receive_json()
        websocket.send_text("/ai narration on")
        assert websocket.receive_json()["success"] is True
        websocket.send_text("take torch")
        result = websocket.receive_json()
        assert result["type"] == "game_output"
        assert result["text"] == "You take the torch."
        assert result["state"]["inventory"] == [{"id": "torch", "name": "torch"}]
        narration = websocket.receive_json()
        assert narration["type"] == "narration"
        assert narration["text"] == "You gather up the torch."
        assert "state" not in narration and "success" not in narration
        assert narration["ai_usage"]["remaining"] == 0
        websocket.send_text("drop torch")
        assert websocket.receive_json()["state"]["inventory"] == []
        assert websocket.receive_json()["text"] is None
        assert len(provider.narration_requests) == 1


def test_narration_does_not_receive_other_players_or_private_speech(game_client, monkeypatch):
    provider = FakeAIProvider()
    monkeypatch.setattr(websocket_api.game_service, "narration_enabled", True)
    monkeypatch.setattr(websocket_api.narration_service, "provider", provider)
    game_client.admin_usernames.add("hiddenidentity")
    with game_client.websocket_connect("/ws?username=HiddenIdentity") as first:
        first.receive_json()
        first.send_text("/ai narration on")
        assert first.receive_json()["success"] is True
        with game_client.websocket_connect("/ws?username=SecondIdentity") as second:
            second.receive_json()
            first.send_text("look")
            assert "SecondIdentity" in first.receive_json()["text"]
            first.receive_json()
            assert "SecondIdentity" not in provider.narration_requests[0].authoritative_text
            first.send_text("tell SecondIdentity private-speech")
            assert "private-speech" in first.receive_json()["text"]
            assert "private-speech" in second.receive_json()["text"]
            first.send_text("inventory")
            assert first.receive_json()["type"] == "game_output"
            assert len(provider.narration_requests) == 1


@pytest.fixture
def game_client(test_client):
    """Authenticate each test character through HTTP, retaining independent cookies."""
    tokens = {}

    class GameClient:
        admin_usernames = set()

        def websocket_connect(self, url, **kwargs):
            username = parse_qs(urlparse(url).query)["username"][0].strip()
            normalized = username.casefold()
            if normalized not in tokens:
                test_client.cookies.clear()
                response = test_client.post(
                    "/auth/register",
                    json={"username": username, "password": "A long test-only passphrase1!"},
                    headers={"origin": "http://localhost:5173"},
                )
                assert response.status_code == 201
                tokens[normalized] = test_client.cookies.get("mud_session")
                if normalized in self.admin_usernames:
                    test_client.portal.call(set_admin, get_session_factory(), username, True)
            headers = dict(kwargs.pop("headers", {}))
            headers["cookie"] = f"mud_session={tokens[normalized]}"
            return test_client.websocket_connect(url, headers=headers, **kwargs)

    return GameClient()


@pytest.mark.parametrize(
    ("command", "expected_action", "secret"),
    [
        ("examine private-keepsake-7419", "examine", "private-keepsake-7419"),
        ("tell Nobody private-message-8527", "tell", "private-message-8527"),
    ],
)
def test_websocket_logs_command_metadata_without_content(
    game_client, caplog, command, expected_action, secret
):
    with caplog.at_level(logging.DEBUG, logger="app.api.websocket"):
        with game_client.websocket_connect("/ws?username=LoggerTest") as websocket:
            websocket.receive_json()
            websocket.send_text(command)
            websocket.receive_json()

    assert secret not in caplog.text
    assert command not in caplog.text
    assert f"action={expected_action}" in caplog.text
    assert f"bytes={len(command.encode('utf-8'))}" in caplog.text
    assert "success=" in caplog.text


def test_websocket_accepts_a_trusted_browser_origin(game_client):
    with game_client.websocket_connect(
        "/ws?username=Trusted",
        headers={"origin": "http://localhost:5173"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "system"


def test_websocket_rejects_an_untrusted_browser_origin(game_client):
    with pytest.raises(WebSocketDisconnect) as denied:
        with game_client.websocket_connect(
            "/ws?username=Untrusted",
            headers={"origin": "https://evil.example"},
        ):
            pass

    assert denied.value.code == 1008


def test_websocket_accepts_a_client_without_an_origin_header(game_client):
    with game_client.websocket_connect("/ws?username=NativeClient") as websocket:
        assert websocket.receive_json()["type"] == "system"


def test_websocket_rejects_an_oversized_command(game_client, monkeypatch):
    monkeypatch.setattr(websocket_api.settings, "max_command_bytes", 4)

    with game_client.websocket_connect("/ws?username=Verbose") as websocket:
        websocket.receive_json()
        websocket.send_text("north")
        assert websocket.receive_json() == {
            "type": "error",
            "text": "Command is too large.",
        }
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()

    assert closed.value.code == 1009


def test_websocket_rate_limits_commands_per_connection(game_client, monkeypatch):
    monkeypatch.setattr(websocket_api.settings, "command_rate_limit", 2)
    monkeypatch.setattr(websocket_api.settings, "command_rate_window_seconds", 60.0)

    with game_client.websocket_connect("/ws?username=Rapid") as websocket:
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


def test_websocket_enforces_the_concurrent_connection_limit(game_client, monkeypatch):
    monkeypatch.setattr(websocket_api.settings, "max_websocket_connections", 1)

    with game_client.websocket_connect("/ws?username=First") as first:
        first.receive_json()
        with pytest.raises(WebSocketDisconnect) as denied:
            with game_client.websocket_connect("/ws?username=Second"):
                pass

    assert denied.value.code == 1013


def test_websocket_rate_limits_connection_attempts_by_source(game_client, monkeypatch):
    websocket_api.connection_attempts.clear()
    monkeypatch.setattr(websocket_api.settings, "connection_attempt_limit", 1)
    monkeypatch.setattr(websocket_api.settings, "connection_attempt_window_seconds", 60.0)

    try:
        with game_client.websocket_connect("/ws?username=FirstAttempt") as first:
            first.receive_json()
        with pytest.raises(WebSocketDisconnect) as denied:
            with game_client.websocket_connect("/ws?username=SecondAttempt"):
                pass
        assert denied.value.code == 1013
    finally:
        websocket_api.connection_attempts.clear()


def test_websocket_connections_have_independent_player_state(game_client):
    with game_client.websocket_connect("/ws?username=Alan") as first:
        first_welcome = first.receive_json()
        assert first_welcome["type"] == "system"
        assert first_welcome["room_name"] == "Town Square"

        with game_client.websocket_connect("/ws?username=Robin") as second:
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


def test_websocket_exposes_ai_interpretation_metadata(game_client, monkeypatch):
    monkeypatch.setattr(websocket_api.game_service, "ai_provider", FakeAIProvider())

    with game_client.websocket_connect("/ws?username=NaturalSpeaker") as websocket:
        websocket.receive_json()
        websocket.send_text("walk toward the docks")
        result = websocket.receive_json()

    assert result["success"] is True
    assert result["room_id"] == "docks"
    assert result["metadata"] == {"command_source": "ai"}


def test_only_one_websocket_player_can_take_a_shared_item(game_client):
    with game_client.websocket_connect("/ws?username=Alan") as first:
        first.receive_json()
        with game_client.websocket_connect("/ws?username=Robin") as second:
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


def test_duplicate_connected_username_is_rejected(game_client):
    with game_client.websocket_connect("/ws?username=Alan") as first:
        first.receive_json()
        with game_client.websocket_connect("/ws?username=%20ALAN%20") as second:
            error = second.receive_json()

            assert error == {
                "type": "error",
                "text": "That username is already connected.",
            }


def test_players_can_see_and_speak_to_others_in_the_same_room(game_client):
    with game_client.websocket_connect("/ws?username=Alan") as alan:
        alan.receive_json()
        with game_client.websocket_connect("/ws?username=Robin") as robin:
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


def test_movement_output_lists_players_already_in_the_destination(game_client):
    with game_client.websocket_connect("/ws?username=Alan") as alan:
        alan.receive_json()
        with game_client.websocket_connect("/ws?username=Robin") as robin:
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


def test_client_state_tracks_inventory_failures_movement_and_reconnect(game_client):
    with game_client.websocket_connect("/ws?username=PanelPlayer") as socket:
        state = socket.receive_json()["state"]
        assert state == {"room_id": "town_square", "room_name": "Town Square", "inventory": [],
                         "map": {"rooms": [{"id": "town_square", "name": "Town Square"}], "exits": []}}
        socket.send_text("take torch")
        held = socket.receive_json()["state"]
        assert held["inventory"] == [{"id": "torch", "name": "torch"}]
        socket.send_text("take sword")
        failed = socket.receive_json()
        assert failed["success"] is False
        assert failed["state"] == held
        socket.send_text("north")
        assert socket.receive_json()["state"]["room_name"] == "Forest"
    with game_client.websocket_connect("/ws?username=PanelPlayer") as socket:
        state = socket.receive_json()["state"]
        assert state["room_name"] == "Forest"
        assert state["inventory"] == held["inventory"]
        socket.send_text("drop torch")
        assert socket.receive_json()["state"]["inventory"] == []


def test_players_can_tell_and_atomically_give_items(game_client):
    with game_client.websocket_connect("/ws?username=Alan") as alan:
        alan.receive_json()
        with game_client.websocket_connect("/ws?username=Robin") as robin:
            robin.receive_json()

            alan.send_text("say to Robin This is private.")
            assert alan.receive_json()["text"] == 'You tell Robin, "This is private."'
            assert robin.receive_json()["text"] == 'Alan tells you, "This is private."'

            alan.send_text("take torch")
            alan.receive_json()
            assert robin.receive_json()["text"] == "Alan picks up the torch."
            alan.send_text("give torch to Robin")
            sender = alan.receive_json()
            recipient = robin.receive_json()
            assert sender["text"] == "You give the torch to Robin."
            assert sender["state"]["inventory"] == []
            assert recipient["text"] == "Alan gives you the torch."
            assert recipient["state"]["inventory"] == [{"id": "torch", "name": "torch"}]

            robin.send_text("inventory")
            assert robin.receive_json()["text"] == "Inventory: torch"


def test_telling_yourself_returns_a_random_playful_warning(game_client):
    from app.services.game import SELF_TALK_RESPONSES

    with game_client.websocket_connect("/ws?username=Alan") as alan:
        alan.receive_json()

        alan.send_text("say to Alan Hello, me.")
        say_to_result = alan.receive_json()
        alan.send_text("tell ALAN Still there?")
        tell_result = alan.receive_json()

        assert say_to_result["success"] is False
        assert say_to_result["text"] in SELF_TALK_RESPONSES
        assert tell_result["success"] is False
        assert tell_result["text"] in SELF_TALK_RESPONSES


def test_who_lists_only_connected_players_and_their_rooms(game_client):
    with game_client.websocket_connect("/ws?username=Robin") as robin:
        robin.receive_json()
        robin.send_text("north")
        robin.receive_json()

        with game_client.websocket_connect("/ws?username=Alan") as alan:
            alan.receive_json()
            alan.send_text("who")
            result = alan.receive_json()

            assert result["success"] is True
            assert result["text"] == (
                "Players online (2):\n" "- Alan — Town Square\n" "- Robin — Forest"
            )
