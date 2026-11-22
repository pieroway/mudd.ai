"""Seeded topology and atomic publication for underground maze regions."""

from dataclasses import asdict, dataclass
from math import ceil, isqrt
from random import Random
from secrets import randbits
import shlex
from uuid import uuid4

from app.domain.directions import OPPOSITE
from app.models import ExitRecord, RoomRecord
from app.repositories.world_proposals import WorldProposalRepository
from app.models.game import DoorRecord

HELP = (
    '/world generate maze [--theme abandoned-mine] [--rooms 250] [--levels 5] '
    '[--seed 7421] [--loops 15] [--direction down]'
)

STEPS = {
    "north": (0, -1, 0), "east": (1, 0, 0), "south": (0, 1, 0),
    "west": (-1, 0, 0), "up": (0, 0, 1), "down": (0, 0, -1),
}
THEMES = {
    "abandoned-mine": ("Mine", ("Black slate", "Pale quartz", "Veined granite", "Rust-streaked shale")),
    "natural-caves": ("Cave", ("Banded limestone", "Blue calcite", "Rough dolomite", "White chalk")),
    "catacombs": ("Catacomb", ("Chiseled limestone", "Dark brick", "Grey sandstone", "Cracked marble")),
}
Coord = tuple[int, int, int]
Passage = tuple[Coord, str, Coord]


@dataclass(frozen=True)
class MazeConfig:
    theme: str = "abandoned-mine"
    rooms: int = 250
    levels: int = 5
    seed: int = 0
    loops: int = 15
    direction: str = "down"


def options(raw: str) -> MazeConfig:
    parts = shlex.split(raw)
    values = dict(zip(parts[::2], parts[1::2]))
    allowed = {"--theme", "--rooms", "--levels", "--seed", "--loops", "--direction"}
    if len(parts) != 2 * len(values) or values.keys() - allowed:
        raise ValueError(HELP)
    try:
        config = MazeConfig(
            theme=values.get("--theme", "abandoned-mine"),
            rooms=int(values.get("--rooms", "250")),
            levels=int(values.get("--levels", "5")),
            seed=int(values["--seed"]) if "--seed" in values else randbits(63),
            loops=int(values.get("--loops", "15")),
            direction=values.get("--direction", "down"),
        )
    except ValueError:
        raise ValueError(HELP) from None
    if config.theme not in THEMES:
        raise ValueError("Choose abandoned-mine, natural-caves, or catacombs.")
    if not 1 <= config.rooms <= 500 or not 1 <= config.levels <= min(20, config.rooms):
        raise ValueError("Choose 1–500 rooms and 1–20 levels, with at least one room per level.")
    if not 0 <= config.seed < 2**63 or not 0 <= config.loops <= 100:
        raise ValueError("Choose a non-negative 63-bit seed and a loop percentage from 0 to 100.")
    if config.direction not in STEPS or config.direction == "up":
        raise ValueError("Choose down or a compass direction for the entrance.")
    return config


def topology(config: MazeConfig) -> tuple[list[Coord], list[Passage]]:
    rng = Random(config.seed)
    per_level, extra = divmod(config.rooms, config.levels)
    width = isqrt(ceil(config.rooms / config.levels) - 1) + 1
    cells = [
        (index % width, index // width, -depth)
        for depth in range(config.levels)
        for index in range(per_level + (depth < extra))
    ]
    occupied = set(cells)

    def adjacent(cell: Coord) -> list[Passage]:
        x, y, z = cell
        return [
            (cell, direction, neighbor)
            for direction, (dx, dy, dz) in STEPS.items()
            if (neighbor := (x + dx, y + dy, z + dz)) in occupied
            and (cell != cells[0] or direction != OPPOSITE[config.direction])
            and (neighbor != cells[0] or direction != config.direction)
        ]

    # A horizontal entrance can reserve its outward edge only if the grid
    # extends inward on that axis. Transform the grid before traversal.
    if config.direction in {"west", "north"}:
        cells = [
            (-x if config.direction == "west" else x, -y if config.direction == "north" else y, z)
            for x, y, z in cells
        ]
        occupied = set(cells)
    stack = [cells[0]]
    visited = {cells[0]}
    passages = []
    while stack:
        candidates = [edge for edge in adjacent(stack[-1]) if edge[2] not in visited]
        if not candidates:
            stack.pop()
            continue
        edge = rng.choice(candidates)
        passages.append(edge)
        visited.add(edge[2])
        stack.append(edge[2])
    if visited != occupied:
        raise ValueError("The entrance direction leaves some maze rooms unreachable.")
    used = {frozenset((start, end)) for start, _, end in passages}
    for cell in cells:
        for edge in adjacent(cell):
            start, _, end = edge
            if start < end and frozenset((start, end)) not in used and rng.randrange(100) < config.loops:
                passages.append(edge)
    return cells, passages


async def publish(repo: WorldProposalRepository, source_id: str, config: MazeConfig) -> dict:
    cells, passages = topology(config)
    await repo.lock_world()
    source, exits, _ = await repo.source(source_id)
    if config.direction in exits:
        raise ValueError(f"{source.name} already has an exit {config.direction}.")
    region_id = str(uuid4())
    room_ids = {cell: str(uuid4()) for cell in cells}
    title, materials = THEMES[config.theme]
    rng = Random(config.seed)
    for index, cell in enumerate(cells, 1):
        x, y, z = cell
        material = rng.choice(materials)
        detail = rng.choice((
            "A faint draft stirs the dust.", "Water ticks against the stone.",
            "Cold air holds the smell of wet earth.", "Your footsteps return a dull echo.",
        ))
        repo.session.add(RoomRecord(
            id=room_ids[cell], name=f"{title} Chamber {index}",
            description=f"{material} lines the chamber {abs(z) + 1} levels below ground. {detail}",
            conditions={"maze": {
                "region_id": region_id, "x": x, "y": y, "z": z - 1,
                "version": 1, "config": asdict(config),
            }},
        ))
    await repo.session.flush()
    links = [(source_id, config.direction, room_ids[cells[0]])]
    links.extend((room_ids[start], direction, room_ids[end]) for start, direction, end in passages)
    door_ids = {}
    for index, (start_id, direction, end_id) in enumerate(links):
        if direction in {"up", "down"} and index % 3 == 0:
            door_id = str(uuid4())
            door_ids[index] = door_id
            repo.session.add(DoorRecord(
                id=door_id, name="iron trapdoor", description="An iron trapdoor covers the opening.",
                room_id=start_id, destination_room_id=end_id, is_open=False,
            ))
    await repo.session.flush()
    for index, (start_id, direction, end_id) in enumerate(links):
        repo.session.add_all([
            ExitRecord(room_id=start_id, direction=direction, destination_room_id=end_id, door_id=door_ids.get(index)),
            ExitRecord(room_id=end_id, direction=OPPOSITE[direction], destination_room_id=start_id, door_id=door_ids.get(index)),
        ])
    return {
        "success": True,
        "output": (
            f"Generated {config.rooms} rooms across {config.levels} levels {config.direction} of "
            f"{source.name}. Region {region_id}. Seed {config.seed}."
        ),
        "_world_source": source_id,
        "_world_notice": f"A new passage leads {config.direction}.",
    }
