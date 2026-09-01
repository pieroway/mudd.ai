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
