"""Admin-authorized credit grants, committed atomically with an audit record."""

from collections.abc import Awaitable, Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AccountRecord, AICreditGrantRecord, PlayerRecord

GRANT_USAGE = 'Usage: /ai credits add <username> [units] (default 50; 1-10000). Quote names with spaces.'


async def grant_credits(
    factory: async_sessionmaker[AsyncSession], account_id: str | None, arguments: list[str],
    *, authorization_check: Callable[[], Awaitable[bool]] | None = None,
) -> dict[str, object]:
    async with factory() as session, session.begin():
        # Resolve IDs first, then lock both accounts in a stable order to avoid
        # deadlocks when two admins grant to each other or to themselves.
        target_name = arguments[2] if len(arguments) >= 3 else ""
        target_id = await session.scalar(select(AccountRecord.id).where(
            AccountRecord.normalized_username == target_name.strip().casefold(),
        ))
        ids = [value for value in (account_id, target_id) if value is not None]
        accounts = {account.id: account for account in (await session.scalars(
            select(AccountRecord).where(AccountRecord.id.in_(ids))
            .order_by(AccountRecord.id).with_for_update()
        )).all()}
        admin = accounts.get(account_id or "")
        if admin is None or not admin.is_admin:
            return {"success": False, "output": "The /ai command is available to admin users only."}
        if authorization_check is not None and not await authorization_check():
            return {"success": False, "output": "Session expired. Please sign in again."}
        if len(arguments) not in {3, 4} or arguments[:2] != ["credits", "add"]:
            return {"success": False, "output": GRANT_USAGE}
        raw_units = arguments[3] if len(arguments) == 4 else "50"
        if not raw_units.isascii() or not raw_units.isdecimal() or len(raw_units) > 5:
            return {"success": False, "output": GRANT_USAGE}
        units = int(raw_units)
        if not 1 <= units <= 10000:
            return {"success": False, "output": GRANT_USAGE}
        recipient = accounts.get(target_id or "")
        if recipient is None:
            return {"success": False, "output": "Account not found."}
        if recipient.ai_bonus_credits + units > 1_000_000:
            return {"success": False, "output": "Grant would exceed the account's 1,000,000 bonus-credit limit."}
        recipient.ai_bonus_credits += units
        session.add(AICreditGrantRecord(
            id=str(uuid4()), admin_account_id=admin.id,
            recipient_account_id=recipient.id, units=units,
        ))
        name = await session.scalar(select(PlayerRecord.username).where(
            PlayerRecord.id == recipient.player_id,
        ))
        return {
            "success": True,
            "output": f"Added {units} AI credits to {name}. Bonus balance: {recipient.ai_bonus_credits}.",
            "_credit_recipient_player_id": recipient.player_id,
            "_credit_recipient_account_id": recipient.id,
            "_credit_units": units,
        }
