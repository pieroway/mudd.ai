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


def test_only_one_player_can_take_a_shared_item():
    service = GameService()
    first_player = service.connect_player("connection-1", "Alan")
    second_player = service.connect_player("connection-2", "Robin")

    first_result = service.execute("connection-1", "take torch")
    second_result = service.execute("connection-2", "take torch")

    assert first_result["success"] is True
    assert second_result == {"success": False, "output": "You do not see a torch here."}
    assert first_player.inventory == ["torch"]
    assert second_player.inventory == []


def test_disconnect_returns_carried_items_to_the_room():
    service = GameService()
    service.connect_player("connection-1", "Alan")
    service.execute("connection-1", "take torch")

    service.disconnect_player("connection-1")

    torch = service.world["items"]["torch"]
    assert torch.owned_by is None
    assert torch.room_id == "town_square"
