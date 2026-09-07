"""Server-owned account permissions and persistent AI presentation preferences."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AccountRecord


async def account_is_admin(
    session_factory: async_sessionmaker[AsyncSession], account_id: str | None
) -> bool:
    async with session_factory() as session:
        return bool(await session.scalar(select(AccountRecord.is_admin).where(
            AccountRecord.id == account_id
        )))


async def narration_allowed(
    session_factory: async_sessionmaker[AsyncSession], account_id: str
) -> bool:
    async with session_factory() as session:
        return bool(await session.scalar(select(AccountRecord.id).where(
            AccountRecord.id == account_id,
            AccountRecord.is_admin.is_(True),
            AccountRecord.ai_narration_enabled.is_(True),
        )))


async def configure_narration(
    session_factory: async_sessionmaker[AsyncSession],
    account_id: str | None,
    arguments: list[str],
    *,
    available: bool,
) -> dict[str, object]:
    async with session_factory() as session:
        async with session.begin():
            account = await session.scalar(select(AccountRecord).where(
                AccountRecord.id == account_id
            ).with_for_update())
            if account is None or not account.is_admin:
                return {"success": False, "output": "The /ai command is available to admin users only."}
            if (len(arguments) != 2 or arguments[0] not in {"narration"}
                    or arguments[1] not in {"on", "off"}):
                return {"success": False, "output": "Usage: /ai narration on|off"}
            enabled = arguments[1] == "on"
            if enabled and not available:
                return {"success": False, "output": "AI narration is disabled on this server."}
            account.ai_narration_enabled = enabled
            return {"success": True, "output": f"AI narration is {arguments[1]} for your account."}


async def set_admin(
    session_factory: async_sessionmaker[AsyncSession], username: str, enabled: bool
) -> None:
    """Local operator operation; never exposed as a player command or HTTP route."""
    async with session_factory() as session:
        async with session.begin():
            account = await session.scalar(select(AccountRecord).where(
                AccountRecord.normalized_username == username.strip().casefold()
            ).with_for_update())
            if account is None:
                raise ValueError("Account not found.")
            account.is_admin = enabled
            if not enabled:
                account.ai_narration_enabled = False
