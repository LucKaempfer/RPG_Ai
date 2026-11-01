"""Corridor traps: tripwires that loose arrows from the walls, fire pits
that flare up in a rhythm, and spike plates, so the walk between rooms
is not a free stroll.

Pure data, timing and placement, no drawing (the dungeon screen draws
them and moves the arrows).

Kinds:

* ``tripwire``: a thin wire across the corridor.  Walking into it
  clicks, and after ``ARROW_DELAY`` seconds arrows fly out of slots in
  one wall, across the wire's cell and the cells either side of it.  Keep
  walking and you are past the volley; stop or turn back and you are hit.
  A spent wire stays cut.  A melee swing at a wire you can see cuts it
  safely (disarms it).
* ``firepit``: a grate that cycles cold -> smoking (a warning) -> burning.
  Standing on it while it burns hurts every ``FIRE_TICK`` seconds.  Each
  pit runs on its own beat, so time your dash.
* ``spikes``: a pressure plate.  Stepping on it arms it; ``SPIKE_DELAY``
  seconds later spikes shoot up and hurt whoever still stands there, then
  sink back after ``SPIKE_UP``.  It re-arms.

Traps only go on straight corridor cells (floor on two opposite sides,
wall on the other two), never next to a door, a room or another trap,
so a trap never blocks the way: every one can be walked over.  Traps
wound but never kill (they leave the hero at 1 HP at worst): the fights
are where a run ends.

Placement has its own RNG seeded from the floor seed, like props: the same
floor always gets the same traps, and the floor's own RNG is untouched.
"""
import random
from dataclasses import dataclass, field

from .config import (TRAPS_PER_FLOOR, TRAPS_PER_EXTRA_FLOOR, TRAPS_MAX,
                     TRAP_DAMAGE, TRAP_DAMAGE_PER_FLOOR, TRAP_ARMOUR_DIV)

TRAP_KINDS = ("tripwire", "firepit", "spikes")
TRAP_WEIGHTS = {"tripwire": 4, "firepit": 3, "spikes": 3}
# Seconds from the click to the volley, and how many cells it covers
# either side of the wire.
ARROW_DELAY = 0.45
ARROW_SPREAD = 1
# Fire pit cycle in seconds: cold, then smoking (warning), then burning.
FIRE_COLD, FIRE_WARN, FIRE_BURN = 1.3, 0.6, 1.0
FIRE_CYCLE = FIRE_COLD + FIRE_WARN + FIRE_BURN
FIRE_TICK = 0.5
# Spike plate: delay after stepping on it, then seconds the spikes stay up.
SPIKE_DELAY = 0.35
SPIKE_UP = 0.8
# Traps keep this many tiles (Chebyshev) between each other.
TRAP_SPACING = 4


@dataclass
class Trap:
    kind: str
    cell: tuple
    # Corridor direction: "h" (runs east-west) or "v" (north-south).
    axis: str = "h"
    # Tripwire: the wall arrows come from, as a step (dx, dy) from the
    # corridor into that wall.
    side: tuple = (0, -1)
    phase: float = 0.0     # fire pit: seconds into its cycle at t = 0
    spent: bool = False    # tripwire: fired or cut
    # Runtime timers (not saved).
    timer: float = field(default=0.0, compare=False)   # countdown to a volley / spikes
    up: float = field(default=0.0, compare=False)      # spikes: seconds still up
    tick: float = field(default=0.0, compare=False)    # fire: seconds to next burn
    state: str = field(default="cold", compare=False)  # fire: last state seen

    # -- fire pits --------------------------------------------------
    def fire_state(self, t: float) -> str:
        """"cold", "warn" or "burn" at play time ``t``."""
        p = (t + self.phase) % FIRE_CYCLE
        if p < FIRE_COLD:
            return "cold"
        if p < FIRE_COLD + FIRE_WARN:
            return "warn"
        return "burn"

    # -- tripwires --------------------------------------------------
    def volley_cells(self) -> list:
        """The corridor cells the volley crosses (wire cell first)."""
        x, y = self.cell
        dx, dy = (1, 0) if self.axis == "h" else (0, 1)
        cells = [self.cell]
        for k in range(1, ARROW_SPREAD + 1):
            cells += [(x + dx * k, y + dy * k), (x - dx * k, y - dy * k)]
        return cells

    @property
    def armed(self) -> bool:
        return not self.spent


def trap_damage(kind: str, floor: int, defense: int) -> int:
    """HP one hit of ``kind`` takes on ``floor`` from a hero with
    ``defense`` (armour soaks a little), at least 1."""
    base = TRAP_DAMAGE[kind] + TRAP_DAMAGE_PER_FLOOR[kind] * (floor - 1)
    return max(1, base - defense // TRAP_ARMOUR_DIV)


def _straight(dungeon, cell):
    """"h" / "v" if ``cell`` is in a straight one-tile corridor, else None."""
    x, y = cell
    walk = dungeon.is_walkable
    room_map = dungeon.room_map
    if room_map.get(cell, 0) is not None:      # a room cell, or wall
        return None
    e, w = walk((x + 1, y)), walk((x - 1, y))
    n, s = walk((x, y - 1)), walk((x, y + 1))
    if e and w and not n and not s:
        return "h"
    if n and s and not e and not w:
        return "v"
    return None


def trap_cells(dungeon) -> list:
    """Corridor cells a trap may go on: straight, with plain corridor
    (no room, no door) all around within two tiles along the corridor."""
    out = []
    for cell, room in dungeon.room_map.items():
        if room is not None:
            continue
        axis = _straight(dungeon, cell)
        if axis is None:
            continue
        x, y = cell
        dx, dy = (1, 0) if axis == "h" else (0, 1)
        ok = all(dungeon.room_map.get((x + dx * k, y + dy * k), 0) is None
                 and _straight(dungeon, (x + dx * k, y + dy * k)) == axis
                 for k in (-2, -1, 1, 2))
        if ok:
            out.append((cell, axis))
    out.sort()
    return out


def place_traps(dungeon, seed, floor) -> list:
    """This floor's traps: TRAPS_PER_FLOOR + TRAPS_PER_EXTRA_FLOOR per
    floor above 1 (at most TRAPS_MAX), spaced TRAP_SPACING apart."""
    rng = random.Random(f"traps-{seed}")
    want = min(TRAPS_MAX, TRAPS_PER_FLOOR + TRAPS_PER_EXTRA_FLOOR * (floor - 1))
    options = trap_cells(dungeon)
    rng.shuffle(options)
    kinds = list(TRAP_WEIGHTS)
    weights = [TRAP_WEIGHTS[k] for k in kinds]
    traps = []
    for cell, axis in options:
        if len(traps) >= want:
            break
        if any(max(abs(cell[0] - t.cell[0]), abs(cell[1] - t.cell[1]))
               < TRAP_SPACING for t in traps):
            continue
        kind = rng.choices(kinds, weights)[0]
        side = rng.choice(((0, -1), (0, 1)) if axis == "h" else ((-1, 0), (1, 0)))
        traps.append(Trap(kind, cell, axis=axis, side=side,
                          phase=rng.uniform(0, FIRE_CYCLE)))
    return traps
