"""Validate authoritative database invariants after a load-test run."""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select

from app.db import get_session_factory
from app.models import ItemRecord, PlayerRecord, RoomRecord


def item_violations(items: list[ItemRecord]) -> list[str]:
    violations: list[str] = []
    items_by_id = {item.id: item for item in items}

    for item in items:
        locations = sum(
            value is not None
            for value in (item.room_id, item.owner_id, item.container_id)
        )
        if locations != 1:
            violations.append(f"item {item.id!r} has {locations} locations")
        if item.container_id == item.id:
            violations.append(f"item {item.id!r} contains itself")
        if item.container_id is not None:
            container = items_by_id.get(item.container_id)
            if container is None:
                violations.append(f"item {item.id!r} has a missing container")
            elif not container.can_open:
                violations.append(
                    f"item {item.id!r} is inside non-container {container.id!r}"
                )
        if item.fuel_remaining is not None and item.fuel_remaining < 0:
            violations.append(f"item {item.id!r} has negative fuel")
        if item.is_lit and not item.is_light_source:
            violations.append(f"non-light-source item {item.id!r} is lit")
        if item.is_lit and item.fuel_remaining == 0:
            violations.append(f"exhausted light source {item.id!r} is lit")

        visited: set[str] = set()
        current = item
        while current.container_id is not None:
            if current.id in visited:
                violations.append(f"containment cycle includes item {item.id!r}")
                break
            visited.add(current.id)
            parent = items_by_id.get(current.container_id)
            if parent is None:
                break
            current = parent

    return violations


async def check_database() -> list[str]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        items = list((await session.scalars(select(ItemRecord))).all())
        players = list((await session.scalars(select(PlayerRecord))).all())
        room_ids = set((await session.scalars(select(RoomRecord.id))).all())

    violations = item_violations(items)
    normalized_usernames: set[str] = set()
    for player in players:
        if player.current_room_id not in room_ids:
            violations.append(f"player {player.username!r} is in a missing room")
        if player.normalized_username != player.username.strip().casefold():
            violations.append(f"player {player.username!r} has inconsistent normalization")
        if player.normalized_username in normalized_usernames:
            violations.append(
                f"normalized username {player.normalized_username!r} is duplicated"
            )
        normalized_usernames.add(player.normalized_username)
    return violations


async def main() -> int:
    violations = await check_database()
    if violations:
        print(f"Authoritative-state invariant check failed ({len(violations)}):")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("Authoritative-state invariant check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
