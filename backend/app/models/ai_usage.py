"""Daily account request counters, independent of runtime processes."""

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AIUsageRecord(Base):
    __tablename__ = "ai_daily_usage"
    __table_args__ = (CheckConstraint("attempts >= 0", name="ck_ai_usage_nonnegative"),)

    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
