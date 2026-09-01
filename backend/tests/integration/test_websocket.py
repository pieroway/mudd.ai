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

