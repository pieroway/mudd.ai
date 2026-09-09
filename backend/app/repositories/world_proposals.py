"""Database access and serialized canonical world writes for room proposals."""

import hashlib
import json
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.directions import OPPOSITE
from app.models import AccountRecord, ExitRecord, PlayerRecord, RoomRecord
from app.models.world_proposal import WorldProposalRecord


class WorldProposalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def admin_player(self, account_id: str, player_id: str) -> PlayerRecord | None:
        account = await self.session.scalar(select(AccountRecord).where(
            AccountRecord.id == account_id).with_for_update())
        if account is None or not account.is_admin or account.player_id != player_id:
            return None
        return (await self.session.scalars(select(PlayerRecord).where(
            PlayerRecord.id == player_id).with_for_update())).one_or_none()

    async def pending_count(self, account_id: str) -> int:
        return await self.session.scalar(select(func.count()).select_from(WorldProposalRecord).where(
            WorldProposalRecord.creator_account_id == account_id,
            WorldProposalRecord.status == "pending")) or 0

    async def source(self, room_id: str) -> tuple[RoomRecord, dict[str, str], str]:
        room = (await self.session.scalars(select(RoomRecord).where(RoomRecord.id == room_id)
                                          .execution_options(populate_existing=True))).one()
        rows = (await self.session.execute(select(ExitRecord.direction, ExitRecord.destination_room_id)
                                          .where(ExitRecord.room_id == room_id))).all()
        exits = {direction: destination for direction, destination in rows}
        fingerprint = hashlib.sha256(json.dumps(
            [room.id, room.name, room.description, exits], sort_keys=True,
        ).encode("utf-8")).hexdigest()
        return room, exits, fingerprint

    async def duplicate_name(self, name: str) -> bool:
        # Use Python casefold for the same Unicode semantics on every database locale.
        names = await self.session.scalars(select(RoomRecord.name))
        return any(candidate.strip().casefold() == name.casefold() for candidate in names)

    async def owned(self, proposal_id: str, account_id: str) -> WorldProposalRecord | None:
        return (await self.session.scalars(select(WorldProposalRecord).where(
            WorldProposalRecord.id == proposal_id,
            WorldProposalRecord.creator_account_id == account_id).with_for_update())).one_or_none()

    async def recent(self, account_id: str) -> list[WorldProposalRecord]:
        return list((await self.session.scalars(select(WorldProposalRecord).where(
            WorldProposalRecord.creator_account_id == account_id).order_by(
                WorldProposalRecord.created_at.desc(), WorldProposalRecord.id.desc()).limit(20))).all())

    async def lock_world(self) -> None:
        # All future canonical room editing must use this transaction-scoped lock.
        await self.session.execute(text("SELECT pg_advisory_xact_lock(50615001)"))

    async def publish(self, proposal: WorldProposalRecord) -> str:
        room_id = str(uuid4())
        self.session.add(RoomRecord(id=room_id, name=proposal.name, description=proposal.description))
        await self.session.flush()
        self.session.add_all([
            ExitRecord(room_id=proposal.source_room_id, direction=proposal.direction,
                       destination_room_id=room_id),
            ExitRecord(room_id=room_id, direction=OPPOSITE[proposal.direction],
                       destination_room_id=proposal.source_room_id),
        ])
        proposal.status = "approved"
        proposal.result_room_id = room_id
        proposal.decided_at = func.now()  # type: ignore[assignment]
        await self.session.flush()
        return room_id
