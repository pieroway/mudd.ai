"""Account ownership and revocable browser sessions, separate from characters."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AccountRecord(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("ai_bonus_credits BETWEEN 0 AND 1000000", name="ck_accounts_ai_bonus_credits"),
        CheckConstraint("NOT is_god OR (is_admin AND normalized_username = 'alan')", name="ck_accounts_god"),
        Index("uq_accounts_single_god", "is_god", unique=True, postgresql_where=text("is_god")),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    normalized_username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    ai_bonus_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    is_god: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    is_moderator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    is_creator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    @property
    def can_create(self) -> bool:
        return self.is_admin or self.is_creator

    @property
    def can_moderate(self) -> bool:
        return self.is_admin or self.is_moderator

    ai_narration_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    player_id: Mapped[str] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), unique=True, nullable=False
    )


class AuthSessionRecord(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )


class RoleChangeRecord(Base):
    __tablename__ = "role_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    target_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(16))
    granted: Mapped[bool] = mapped_column(Boolean)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
