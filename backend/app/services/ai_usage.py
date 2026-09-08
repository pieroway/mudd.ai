"""Reserve before calling AI; never refund an attempt with uncertain upstream cost."""

from sqlalchemy import Date, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_usage import AIUsageRecord
from app.models.auth import AccountRecord


def utc_day():
    # Database time is shared across all backend processes.
    return cast(func.timezone("UTC", func.now()), Date)


async def reserve_attempt(
    factory: async_sessionmaker[AsyncSession], account_id: str, limit: int
) -> bool:
    if limit <= 0:
        return False
    async with factory() as session:
        async with session.begin():
            account = await session.scalar(select(AccountRecord).where(
                AccountRecord.id == account_id,
            ).with_for_update())
            if account is None:
                return False
            day = await session.scalar(select(utc_day()))
            used = await session.scalar(select(AIUsageRecord.attempts).where(
                AIUsageRecord.account_id == account_id, AIUsageRecord.day == day,
            )) or 0
            if used >= limit:
                if account.ai_bonus_credits <= 0:
                    return False
                account.ai_bonus_credits -= 1
            statement = insert(AIUsageRecord).values(account_id=account_id, day=day, attempts=1)
            await session.execute(statement.on_conflict_do_update(
                index_elements=[AIUsageRecord.account_id, AIUsageRecord.day],
                set_={"attempts": AIUsageRecord.attempts + 1},
            ))
            return True


async def usage_status(
    factory: async_sessionmaker[AsyncSession], account_id: str, limit: int
) -> dict[str, int | str]:
    async with factory() as session:
        # One statement keeps daily usage and bonus balance on the same snapshot.
        row = (await session.execute(select(
            func.coalesce(AIUsageRecord.attempts, 0), AccountRecord.ai_bonus_credits, utc_day(),
        ).select_from(AccountRecord).outerjoin(AIUsageRecord, (
            (AIUsageRecord.account_id == AccountRecord.id) & (AIUsageRecord.day == utc_day())
        )).where(AccountRecord.id == account_id))).one_or_none()
    used, bonus, day = row if row else (0, 0, "")
    daily_remaining = max(0, limit - used)
    return {
        "used": used, "limit": limit, "daily_remaining": daily_remaining,
        "bonus_credits": bonus,
        "remaining": daily_remaining + bonus if limit > 0 else 0, "day": str(day),
    }
