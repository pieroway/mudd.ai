import pytest
from sqlalchemy import select

from app.ai.fake import FakeAIProvider
from app.ai.narration import NarrationRequest, NarrationResponse
from app.models import AccountRecord
from app.services.ai_preferences import narration_allowed, set_admin
from app.services.ai_usage import usage_status
from app.services.auth import register_account
from app.services.game import GameService
from app.services.narration import NarrationService


async def connect(session_factory, name="Alan", *, admin=False):
    identity = await register_account(name, "Password1!")
    if admin:
        await set_admin(session_factory, name, True)
    provider = FakeAIProvider()
    game = GameService(session_factory, ai_provider=provider, narration_enabled=True)
    await game.connect_player(name, name, player_id=identity.player_id)
    return identity, provider, game


async def test_new_accounts_default_to_non_admin_and_narration_off(session_factory):
    identity, _, game = await connect(session_factory)
    async with session_factory() as session:
        account = await session.get(AccountRecord, identity.account_id)
        assert account.is_admin is False
        assert account.ai_narration_enabled is False
    assert not await narration_allowed(session_factory, identity.account_id)
    assert "_narration_request" not in await game.execute("Alan", "look", account_id=identity.account_id)


async def test_help_includes_admin_commands_only_for_current_admins(session_factory):
    identity, _, game = await connect(session_factory)
    assert "/ai" not in (await game.execute("Alan", "help", account_id=identity.account_id))["output"]
    await set_admin(session_factory, "Alan", True)
    assert "Admin only:" in (
        await game.execute("Alan", "help", account_id=identity.account_id)
    )["output"]
    assert "ai narration on|off" in (
        await game.execute("Alan", "help", account_id=identity.account_id)
    )["output"]
    await set_admin(session_factory, "Alan", False)
    assert "/ai" not in (await game.execute("Alan", "help", account_id=identity.account_id))["output"]


@pytest.mark.parametrize("command", ["/ai", "/ai narration on", "/AI narration off", "/ai other"])
async def test_entire_ai_namespace_is_admin_only_and_never_sent_to_provider(session_factory, command):
    identity, provider, game = await connect(session_factory)
    result = await game.execute("Alan", command, account_id=identity.account_id)
    assert result["success"] is False
    assert result["output"] == "The /ai command is available to admin users only."
    assert not provider.requests
    assert (await usage_status(session_factory, identity.account_id, 20))["used"] == 0


async def test_admin_preference_is_persistent_and_account_scoped(session_factory):
    identity, provider, game = await connect(session_factory, admin=True)
    other, _, _ = await connect(session_factory, "Kim", admin=True)
    assert not await narration_allowed(session_factory, identity.account_id)
    result = await game.execute("Alan", " /AI NaRrAtIoN ON ", account_id=identity.account_id)
    assert result["success"] is True
    assert result["output"] == "AI narration is on for your account."
    assert not await narration_allowed(session_factory, other.account_id)
    restarted = GameService(session_factory, narration_enabled=True)
    await restarted.connect_player("new", "Alan", player_id=identity.player_id)
    assert "_narration_request" in await restarted.execute("new", "look", account_id=identity.account_id)
    result = await restarted.execute("new", "/ai narration off", account_id=identity.account_id)
    assert result["output"] == "AI narration is off for your account."
    assert "_narration_request" not in await restarted.execute("new", "look", account_id=identity.account_id)
    assert not provider.requests


@pytest.mark.parametrize("command", [
    "/ai", "/ai narration", "/ai narration maybe", "/ai narration on Kim", "/ai naration on"
])
async def test_admin_invalid_syntax_preserves_preference(session_factory, command):
    identity, provider, game = await connect(session_factory, admin=True)
    result = await game.execute("Alan", command, account_id=identity.account_id)
    assert not result["success"]
    assert result["output"] == "Usage: /ai narration on|off"
    assert not await narration_allowed(session_factory, identity.account_id)
    assert not provider.requests


async def test_server_switch_and_revoked_session_cannot_be_bypassed(session_factory):
    identity, _, game = await connect(session_factory, admin=True)
    game.narration_enabled = False
    assert not (await game.execute("Alan", "/ai narration on", account_id=identity.account_id))["success"]
    assert not await narration_allowed(session_factory, identity.account_id)
    game.narration_enabled = True

    async def revoked():
        return False

    result = await game.execute("Alan", "/ai narration on", account_id=identity.account_id,
                                authorization_check=revoked)
    assert not result["success"]
    assert not await narration_allowed(session_factory, identity.account_id)


async def test_admin_revocation_stops_narration_and_resets_preference(session_factory):
    identity, _, game = await connect(session_factory, admin=True)
    await game.execute("Alan", "/ai narration on", account_id=identity.account_id)

    class RevokingProvider(FakeAIProvider):
        async def narrate_result(self, request):
            await set_admin(session_factory, "Alan", False)
            return NarrationResponse(text="This must not be delivered.")

    narrator = NarrationService(session_factory, RevokingProvider())
    request = NarrationRequest(action="look", success=True, authoritative_text="Town Square")
    assert await narrator.narrate(request, account_id=identity.account_id) is None
    assert not await narration_allowed(session_factory, identity.account_id)
    assert not (await game.execute("Alan", "/ai narration on", account_id=identity.account_id))["success"]
    await set_admin(session_factory, "Alan", True)
    assert not await narration_allowed(session_factory, identity.account_id)


async def test_off_accounts_do_not_consume_narration_allowance(session_factory):
    identity, provider, _ = await connect(session_factory, admin=True)
    narrator = NarrationService(session_factory, provider)
    request = NarrationRequest(action="look", success=True, authoritative_text="Town Square")
    assert await narrator.narrate(request, account_id=identity.account_id) is None
    assert not provider.narration_requests
    assert (await usage_status(session_factory, identity.account_id, 20))["used"] == 0


async def test_operator_requires_existing_account_and_normalizes_name(session_factory):
    with pytest.raises(ValueError, match="Account not found"):
        await set_admin(session_factory, "Nobody", True)
    identity, _, _ = await connect(session_factory)
    await set_admin(session_factory, " ALAN ", True)
    async with session_factory() as session:
        account = await session.scalar(select(AccountRecord).where(AccountRecord.id == identity.account_id))
        assert account.is_admin is True
