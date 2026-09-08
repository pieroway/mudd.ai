"""Narrow NPC queries; secrets and unrelated world records are never loaded."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import AccountRecord
from app.models.game import PlayerRecord
from app.models.npc import NPCMemoryRecord, NPCRecord


class NPCRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def present(self, player_id: str, npc_id: str, account_id: str | None) -> bool:
        statement = select(NPCRecord.id).join(
            PlayerRecord, PlayerRecord.current_room_id == NPCRecord.room_id
        ).where(PlayerRecord.id == player_id, NPCRecord.id == npc_id)
        if account_id is not None:
            statement = statement.join(
                AccountRecord, AccountRecord.player_id == PlayerRecord.id
            ).where(AccountRecord.id == account_id)
        return await self.session.scalar(statement) is not None

    async def memory(self, player_id: str, npc_id: str) -> NPCMemoryRecord | None:
        return await self.session.get(NPCMemoryRecord, (npc_id, player_id))

    async def lock_player(self, player_id: str) -> None:
        await self.session.execute(
            select(PlayerRecord.id).where(PlayerRecord.id == player_id).with_for_update()
        )

    async def visible_names(self, room_id: str) -> list[str]:
        return list((await self.session.scalars(
            select(NPCRecord.name).where(NPCRecord.room_id == room_id).order_by(NPCRecord.name)
        )).all())
