"""Special rooms: one room per floor for each kind in SPECIAL_KINDS (a
shop with a merchant).  A special room is safe: no enemies, no chests
and no props, just its keeper standing near the top wall.

Picked with their own RNG seeded from the floor seed, never the
entrance or the boss's lair.
"""
import random

from .enemies import boss_room

SPECIAL_KINDS = ("shop",)


def special_rooms(dungeon, seed) -> dict:
    """Kind -> Room for this floor (fewer kinds if there are too few
    rooms)."""
    rng = random.Random(f"special-{seed}")
    lair = boss_room(dungeon)
    free = [r for r in dungeon.rooms[1:] if r is not lair]
    picked = rng.sample(free, min(len(SPECIAL_KINDS), len(free)))
    return dict(zip(SPECIAL_KINDS, picked))


def keeper_cell(room) -> tuple:
    """Where the room's keeper (merchant) stands: an interior cell near
    the top wall, clear of the doors, so the way through stays open."""
    r = room.rect
    near_door = {(x + dx, y + dy) for (x, y) in room.doors
                 for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    cells = [(x, y) for y in range(r.top + 1, r.bottom - 1)
             for x in range(r.left + 1, r.right - 1)]
    for cell in sorted(cells, key=lambda c: (c[1], abs(c[0] - r.centerx))):
        if cell not in near_door and cell != r.center:
            return cell
    return r.center
