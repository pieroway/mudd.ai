"""Resolve moderation recipients against live sessions and world exits."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.directions import HORIZONTAL
from app.models import AccountRecord, ExitRecord, PlayerRecord


async def moderate(
    factory: async_sessionmaker[AsyncSession], actor_id: str | None, session_id: str,
    active_sessions: dict[str, str], arguments: list[str],
) -> dict[str, Any]:
    usage = "Usage: /mod warn <player> <message>, /mod boot <player> <reason>, or /mod announce <message>."
    async with factory() as session, session.begin():
        actor = await session.get(AccountRecord, actor_id) if actor_id else None
        if actor is None or not actor.can_moderate:
            return {"success": False, "output": "Moderation requires moderator access."}
        if len(arguments) < 2:
            return {"success": False, "output": usage}
        action = arguments[0]
        sender = await session.get(PlayerRecord, actor.player_id)
        if sender is None:
            return {"success": False, "output": "The moderator's character is unavailable."}
        if action == "announce":
            adjacent = select(ExitRecord.destination_room_id).where(
                ExitRecord.room_id == sender.current_room_id, ExitRecord.direction.in_(HORIZONTAL))
            recipients = set(await session.scalars(select(PlayerRecord.id).where(
                PlayerRecord.id.in_(active_sessions.values()),
                (PlayerRecord.current_room_id == sender.current_room_id)
                | PlayerRecord.current_room_id.in_(adjacent),
            )))
            message = f"Area announcement from {sender.username}: {' '.join(arguments[1:])}"
            return {"success": True, "output": message, "events": [
                {"session_id": sid, "text": message}
                for sid, player_id in active_sessions.items()
                if sid != session_id and player_id in recipients
            ]}
        if action not in {"warn", "boot"} or len(arguments) < 3:
            return {"success": False, "output": usage}
        target = await session.scalar(select(AccountRecord).where(
            AccountRecord.normalized_username == arguments[1].casefold()))
        if target is not None and target.is_god:
            return {"success": False, "output": "The God account is protected."}
        if target is not None and target.is_admin and not actor.is_admin:
            return {"success": False, "output": "Only admins can moderate an admin account."}
        recipient = next((sid for sid, pid in active_sessions.items()
                          if target is not None and target.player_id == pid and sid != session_id), None)
        if recipient is None:
            return {"success": False, "output": "That player is not connected or is your own account."}
        message = " ".join(arguments[2:])
        notice = (f"You were disconnected by {sender.username}: {message}" if action == "boot"
                  else f"Moderation warning from {sender.username}: {message}")
        return {"success": True, "output": f"{'Boot' if action == 'boot' else 'Warning'} sent to {arguments[1]}.",
                "events": [{"session_id": recipient, "text": notice, "boot": action == "boot"}]}
