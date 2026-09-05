from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.models import PlayerRecord

PASSWORD = "A long test-only passphrase1!"
ORIGIN = {"origin": "http://localhost:5173"}


@pytest.mark.parametrize("password", ["Abcdef1!", "a" * 126 + "1!"])
def test_password_policy_accepts_boundaries(password):
    from app.services.auth import validate_password

    validate_password(password)


@pytest.mark.parametrize(
    "password", ["Abcde1!", "a" * 127 + "1!", "abcdefgh!", "abcdefgh1", "abcdef1 "]
)
def test_password_policy_rejects_invalid_passwords(password):
    from app.services.auth import validate_password

    with pytest.raises(ValueError):
        validate_password(password)


def register(client, username="Alice"):
    return client.post(
        "/auth/register", json={"username": username, "password": PASSWORD}, headers=ORIGIN
    )


def test_registration_login_logout_and_cookie_flags(test_client):
    response = register(test_client)
    assert response.status_code == 201
    assert response.json()["username"] == "Alice"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert test_client.get("/auth/me").status_code == 200
    assert test_client.post("/auth/logout", headers=ORIGIN).status_code == 204
    assert test_client.get("/auth/me").status_code == 401
    assert (
        test_client.post(
            "/auth/login", json={"username": " alice ", "password": PASSWORD}, headers=ORIGIN
        ).status_code
        == 200
    )


def test_wrong_password_and_unknown_user_have_identical_errors(test_client):
    register(test_client)
    results = [
        test_client.post(
            "/auth/login", json={"username": name, "password": "wrong"}, headers=ORIGIN
        )
        for name in ("Alice", "Nobody")
    ]
    assert all(result.status_code == 401 for result in results)
    assert results[0].json() == results[1].json()


def test_untrusted_origin_and_missing_origin_cannot_submit_credentials(test_client):
    for headers in ({"origin": "https://evil.example"}, {}):
        assert (
            test_client.post(
                "/auth/register", json={"username": "Alice", "password": PASSWORD}, headers=headers
            ).status_code
            == 403
        )


def test_password_validation_does_not_echo_credentials(test_client):
    response = test_client.post(
        "/auth/register", json={"username": "Alice", "password": "short-secret"}, headers=ORIGIN
    )
    assert response.status_code == 400
    assert "short-secret" not in response.text


def test_username_query_cannot_impersonate_another_character(test_client):
    register(test_client)
    with test_client.websocket_connect("/ws?username=Victim", headers=ORIGIN) as ws:
        ws.receive_json()
        ws.send_text("who")
        output = ws.receive_json()["text"]
        assert "Alice" in output and "Victim" not in output


def test_unauthenticated_websocket_is_rejected(test_client):
    with pytest.raises(WebSocketDisconnect) as error:
        with test_client.websocket_connect("/ws?username=Alice", headers=ORIGIN):
            pass
    assert error.value.code == 1008


def test_logout_revokes_existing_socket(test_client):
    register(test_client)
    with test_client.websocket_connect("/ws", headers=ORIGIN) as ws:
        ws.receive_json()
        test_client.post("/auth/logout", headers=ORIGIN)
        ws.send_text("north")
        assert ws.receive_json()["type"] == "error"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


async def test_legacy_character_is_reserved(test_client, session_factory):
    async with session_factory() as session:
        async with session.begin():
            session.add(
                PlayerRecord(
                    id="legacy",
                    username="Legacy",
                    normalized_username="legacy",
                    current_room_id="forest",
                )
            )
    assert register(test_client, "Legacy").status_code == 409
    async with session_factory() as session:
        assert (await session.get(PlayerRecord, "legacy")).current_room_id == "forest"


async def test_hashes_and_expired_sessions(test_client, session_factory):
    from app.models.auth import AccountRecord, AuthSessionRecord

    register(test_client)
    async with session_factory() as session:
        async with session.begin():
            account = (await session.scalars(select(AccountRecord))).one()
            assert account.password_hash.startswith("$argon2id$")
            assert PASSWORD not in account.password_hash
            auth_session = (await session.scalars(select(AuthSessionRecord))).one()
            assert auth_session.token_hash != test_client.cookies.get("mud_session")
            auth_session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert test_client.get("/auth/me").status_code == 401


def test_auth_rate_limit(test_client, monkeypatch):
    from app.api import auth

    monkeypatch.setattr(auth.settings, "auth_attempt_limit", 2)
    for _ in range(2):
        assert (
            test_client.post(
                "/auth/login", json={"username": "Nobody", "password": PASSWORD}, headers=ORIGIN
            ).status_code
            == 401
        )
    assert (
        test_client.post(
            "/auth/login", json={"username": "Nobody", "password": PASSWORD}, headers=ORIGIN
        ).status_code
        == 429
    )


def test_duplicate_registration_is_case_insensitive(test_client):
    assert register(test_client).status_code == 201
    assert register(test_client, "ALICE").status_code == 409


async def test_operator_links_legacy_character_without_changing_state(session_factory):
    from app.services.auth import register_account, authenticate, NameUnavailableError

    async with session_factory() as session:
        async with session.begin():
            session.add(
                PlayerRecord(
                    id="legacy",
                    username="Legacy",
                    normalized_username="legacy",
                    current_room_id="forest",
                )
            )
    identity = await register_account("Legacy", PASSWORD, legacy=True)
    assert identity.player_id == "legacy"
    assert await authenticate("legacy", PASSWORD) == identity
    with pytest.raises(NameUnavailableError):
        await register_account("Legacy", "Another long password1!", legacy=True)
    async with session_factory() as session:
        assert (await session.get(PlayerRecord, "legacy")).current_room_id == "forest"


async def test_concurrent_registration_cannot_share_character():
    import asyncio
    from app.services.auth import register_account, Identity, NameUnavailableError

    results = await asyncio.gather(
        register_account("Alice", PASSWORD),
        register_account("ALICE", PASSWORD),
        return_exceptions=True,
    )
    assert sum(isinstance(result, Identity) for result in results) == 1
    assert sum(isinstance(result, NameUnavailableError) for result in results) == 1


def test_login_rotates_previous_token(test_client):
    register(test_client)
    old_token = test_client.cookies.get("mud_session")
    test_client.post(
        "/auth/login", json={"username": "Alice", "password": PASSWORD}, headers=ORIGIN
    )
    assert test_client.cookies.get("mud_session") != old_token
    assert (
        test_client.get("/auth/me", headers={"cookie": f"mud_session={old_token}"}).status_code
        == 401
    )


async def test_authorization_rechecked_after_ai_interpretation(session_factory):
    from app.ai.fake import FakeAIProvider
    from app.services.game import GameService

    service = GameService(session_factory, ai_provider=FakeAIProvider())
    player = await service.connect_player("test", "Alice")

    async def revoked():
        return False

    result = await service.execute("test", "walk toward the docks", authorization_check=revoked)
    assert result["success"] is False
    async with session_factory() as session:
        assert (await session.get(PlayerRecord, player.id)).current_room_id == "town_square"


def test_production_cookies_are_secure(test_client, monkeypatch):
    from app.api import auth

    monkeypatch.setattr(auth.settings, "app_env", "production")
    assert "Secure" in register(test_client).headers["set-cookie"]
