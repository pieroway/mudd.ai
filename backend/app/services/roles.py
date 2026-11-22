"""Account role assignment and authorization."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.auth import AccountRecord, RoleChangeRecord


ROLE_FIELDS = {"admin": "is_admin", "moderator": "is_moderator", "creator": "is_creator"}


async def bootstrap_god(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session, session.begin():
        account = await session.scalar(select(AccountRecord).where(
            AccountRecord.normalized_username == "alan").with_for_update())
        if account is None:
            raise ValueError("The existing Alan account was not found.")
        if not account.is_god:
            account.is_admin = True
            account.is_god = True
            session.add(RoleChangeRecord(target_id=account.id, role="god", granted=True))


async def change_role(
    factory: async_sessionmaker[AsyncSession], actor_id: str | None, username: str,
    role: str | None, granted: bool,
) -> str:
    async with factory() as session, session.begin():
        rows = await session.scalars(select(AccountRecord).where(or_(
            AccountRecord.id == actor_id,
            AccountRecord.normalized_username == username.strip().casefold(),
        )).order_by(AccountRecord.id).with_for_update())
        accounts = list(rows)
        actor = next((account for account in accounts if account.id == actor_id), None)
        if actor_id is not None and (actor is None or not actor.is_admin):
            raise ValueError("Role management requires admin access.")
        target = next((account for account in accounts
                       if account.normalized_username == username.strip().casefold()), None)
        if target is None:
            raise ValueError("Account not found.")
        if role is None:
            roles = ["god", *ROLE_FIELDS] if target.is_god else [
                name for name, field in ROLE_FIELDS.items() if getattr(target, field)]
            return "Assigned roles: " + (", ".join(roles) if roles else "player") + "."
        if target.is_god:
            raise ValueError("The God account is protected.")
        if role not in ROLE_FIELDS:
            raise ValueError("Choose moderator, creator, or admin.")
        if role == "admin" and actor_id is not None and (actor is None or not actor.is_god):
            raise ValueError("Only God can change admin access in game.")
        field = ROLE_FIELDS[role]
        if getattr(target, field) != granted:
            setattr(target, field, granted)
            if role == "admin" and not granted:
                target.ai_narration_enabled = False
            session.add(RoleChangeRecord(actor_id=actor_id, target_id=target.id, role=role, granted=granted))
        return f"{role.capitalize()} access is {'on' if granted else 'off'} for {target.normalized_username}."


async def role_command(
    factory: async_sessionmaker[AsyncSession], actor_id: str | None, arguments: list[str],
) -> dict[str, object]:
    if actor_id is None:
        return {"success": False, "output": "Role management requires admin access."}
    match arguments:
        case ["list", username]:
            role, granted = None, False
        case [("grant" | "revoke") as action, username, requested_role]:
            role, granted = requested_role.casefold(), action == "grant"
        case _:
            return {"success": False, "output": "Usage: /role list <username> or /role grant|revoke <username> <role>."}
    try:
        output = await change_role(factory, actor_id, username, role, granted)
    except ValueError as error:
        return {"success": False, "output": str(error)}
    return {"success": True, "output": output}
