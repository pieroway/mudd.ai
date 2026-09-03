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

            second.send_text("look")
            second_look = second.receive_json()
            assert second_look["success"] is True
            assert second_look["room_id"] == "town_square"
            assert "Town Square" in second_look["text"]


def test_only_one_websocket_player_can_take_a_shared_item(test_client):
    with test_client.websocket_connect("/ws?username=Alan") as first:
        first.receive_json()
        with test_client.websocket_connect("/ws?username=Robin") as second:
            second.receive_json()

            first.send_text("take torch")
            first_result = first.receive_json()
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
            alan.send_text("say Can you hear me?")
            assert alan.receive_json()["text"] == 'You say, "Can you hear me?"'


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
