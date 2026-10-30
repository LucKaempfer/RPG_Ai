"""Room props: barrels, crates, pots, sacks, buckets, bone piles and
rubble standing along the room walls, so rooms are not empty.

The hero can smash them (swing the weapon, or shoot with a bow / wand,
in the dungeon screen): each takes ``PROP_HP`` hits and leaves crafting
materials (``PROP_MATERIALS``) for the hero's pouch.

Pure data + placement, no drawing (``assets.py`` draws
``objects/props.png``, the dungeon screen blits it).

Props stand only on a room's edge row (the floor cells along its walls),
never on a door or next to one.  Enemies, chests, the spawn point and the
stairs all use interior cells, and every door opens onto the interior,
so props can block movement without ever cutting a room off.

Placement has its own RNG seeded from the floor seed: the same floor
always gets the same props, and the floor's own RNG (enemies, chests,
loot) is left untouched.
"""
import random
from dataclasses import dataclass

from .config import PROPS_PER_ROOM

# Sheet column order in objects/props.png (row 0 standing, row 1 broken).
PROP_KINDS = ("barrel", "crate", "pot", "sack", "bucket", "bones", "rubble")
# Hits a prop takes before it breaks.
PROP_HP = {"barrel": 3, "crate": 2, "pot": 1, "sack": 1, "bucket": 2,
           "bones": 1, "rubble": 3}
# What breaking one gives: material -> (min, max).
PROP_MATERIALS = {
    "barrel": {"wood": (1, 2), "iron": (0, 1)},
    "crate": {"wood": (1, 3)},
    "pot": {"stone": (1, 1)},
    "sack": {"cloth": (1, 2)},
    "bucket": {"iron": (1, 2)},
    "bones": {"bone": (1, 3)},
    "rubble": {"stone": (1, 3)},
}
# How often each kind is picked.
PROP_WEIGHTS = {"barrel": 3, "crate": 3, "pot": 3, "sack": 2, "bucket": 1,
                "bones": 2, "rubble": 2}


@dataclass
class Prop:
    kind: str
    cell: tuple
    broken: bool = False
    hp: int = 0          # hits left; 0 = PROP_HP of the kind

    def __post_init__(self):
        if not self.hp:
            self.hp = PROP_HP[self.kind]

    @property
    def solid(self) -> bool:
        """Standing props block the way; broken ones are just debris."""
        return not self.broken

    def hit(self, damage: int = 1) -> bool:
        """Take a hit; True if this one breaks it."""
        if self.broken:
            return False
        self.hp = max(0, self.hp - damage)
        self.broken = self.hp == 0
        return self.broken


def salvage(prop, rng) -> dict:
    """Materials from a broken prop (material -> count, zeros left out)."""
    out = {}
    for mat, (lo, hi) in PROP_MATERIALS[prop.kind].items():
        n = rng.randint(lo, hi)
        if n:
            out[mat] = n
    return out


def edge_cells(room, doors) -> list:
    """Floor cells along ``room``'s walls that keep clear of its doors
    (a door and the eight cells around it stay free)."""
    r = room.rect
    near_door = {(dx + x, dy + y) for (x, y) in doors
                 for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    cells = []
    for x in range(r.left, r.right):
        for y in range(r.top, r.bottom):
            on_edge = x in (r.left, r.right - 1) or y in (r.top, r.bottom - 1)
            if on_edge and (x, y) not in near_door:
                cells.append((x, y))
    return cells


def place_props(dungeon, seed) -> list:
    """This floor's props: PROPS_PER_ROOM (min, max) per room, plus one
    more per 30 floor cells, on edge cells."""
    rng = random.Random(f"props-{seed}")
    kinds = list(PROP_WEIGHTS)
    weights = [PROP_WEIGHTS[k] for k in kinds]
    props = []
    for room in dungeon.rooms:
        cells = edge_cells(room, room.doors)
        lo, hi = PROPS_PER_ROOM
        count = rng.randint(lo, hi) + room.rect.w * room.rect.h // 30
        for cell in rng.sample(cells, min(count, len(cells))):
            props.append(Prop(rng.choices(kinds, weights)[0], cell))
    return props
