"""Reserve before calling AI; never refund an attempt with uncertain upstream cost."""

from sqlalchemy import Date, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_usage import AIUsageRecord


def utc_day():
    # Database time is shared across all backend processes.
    return cast(func.timezone("UTC", func.now()), Date)


async def reserve_attempt(
    factory: async_sessionmaker[AsyncSession], account_id: str, limit: int
) -> bool:
    if limit <= 0:
        return False
    statement = insert(AIUsageRecord).values(account_id=account_id, day=utc_day(), attempts=1)
    reservation = statement.on_conflict_do_update(
        index_elements=[AIUsageRecord.account_id, AIUsageRecord.day],
        set_={"attempts": AIUsageRecord.attempts + 1},
        where=AIUsageRecord.attempts < limit,
    ).returning(AIUsageRecord.attempts)
    async with factory() as session:
        async with session.begin():
            return (await session.scalar(reservation)) is not None


async def usage_status(
    factory: async_sessionmaker[AsyncSession], account_id: str, limit: int
) -> dict[str, int | str]:
    async with factory() as session:
        day = await session.scalar(select(utc_day()))
        used = await session.scalar(
            select(AIUsageRecord.attempts).where(
                AIUsageRecord.account_id == account_id, AIUsageRecord.day == day
            )
        )
    used = used or 0
    return {"used": used, "limit": limit, "remaining": max(0, limit - used), "day": str(day)}
