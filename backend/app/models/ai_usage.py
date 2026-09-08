"""Daily account request counters, independent of runtime processes."""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, func
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


class AICreditGrantRecord(Base):
    __tablename__ = "ai_credit_grants"
    __table_args__ = (
        CheckConstraint("units BETWEEN 1 AND 10000", name="ck_ai_credit_grant_units"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    admin_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True,
    )
    recipient_account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
