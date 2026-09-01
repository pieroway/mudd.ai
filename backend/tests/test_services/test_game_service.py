from app.services.game import GameService


def test_connected_players_have_independent_positions():
    service = GameService()
    first_player = service.connect_player("connection-1", "Alan")
    second_player = service.connect_player("connection-2", "Robin")

    result = service.execute("connection-1", "north")

    assert result["success"] is True
    assert first_player.current_room_id == "forest"
    assert second_player.current_room_id == "town_square"


def test_disconnect_removes_player_session():
    service = GameService()
    service.connect_player("connection-1", "Alan")

    service.disconnect_player("connection-1")

    assert "connection-1" not in service.world["players"]

