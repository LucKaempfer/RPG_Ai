"""Special rooms: one room per floor for each kind in SPECIAL_KINDS (a
shop with a merchant, a forge with an anvil, a healing fountain).  A
special room is safe: no enemies, no chests and no props, just its
keeper (the merchant, the anvil, the fountain) standing near the top
wall.

The fountain can be used once per floor, for one of two gifts: fill a
flask (a Health Potion of the floor's tier, like the shop sells) or
drink (heal FOUNTAIN_HEAL_PERCENT of max HP).

Picked with their own RNG seeded from the floor seed, never the
entrance or the boss's lair.
"""
import random

from .config import FOUNTAIN_HEAL_PERCENT
from .enemies import boss_room
from .items import item_by_id

# Order matters: on a floor with too few rooms the last kinds are left out.
SPECIAL_KINDS = ("shop", "anvil", "fountain")


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


# -- the healing fountain ---------------------------------------------------
def fountain_potion(floor: int):
    """The flask the fountain fills: a Health Potion of the floor's tier
    (I on floor 1 ... IV from floor 4 on), the same one the shop sells."""
    tier = max(1, min(4, floor))
    return item_by_id("potion" if tier == 1 else f"potion_{tier}")


def fountain_heal(player) -> int:
    """HP that drinking would restore: FOUNTAIN_HEAL_PERCENT of max HP,
    capped by what is missing."""
    amount = max(1, player.max_hp * FOUNTAIN_HEAL_PERCENT // 100)
    return min(amount, player.max_hp - player.current_hp)
