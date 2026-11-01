"""Minibosses: one guarded room per floor with a named, tougher foe.

Each story floor (1-LORE_FLOORS) has its own miniboss, tied into the
story: the Gutter Matron who leads the rats down, one of Sergeant
Brenn's drowned watchmen, the goblin who takes the little king's pay,
Lord Aldric's gnawed steward and the swarm that carries the crown's
voice.  Beating one leaves a writing behind (``lore.MINIBOSS_LORE``)
that is read on the spot and filed in the journal.  Deeper floors get
a nameless Deep Warden.

The room is picked with its own RNG seeded from the floor seed, so
floors, enemies, chests, props and writings stay where they were and
old runs still load: never the entrance, the boss's lair or a special
room (shop, forge, ...).  The room's normal enemies stay as the
miniboss's guards.  The miniboss stands on a free interior cell near
the room's centre, placed after everything else so nothing else moves.

Pure data + placement, no drawing.
"""
import random
from dataclasses import replace

from .enemies import EnemyType, boss_room, make_enemy, _cell_centre

# Floor-1 numbers, scaled by ``make_enemy`` like any enemy: tougher than
# a normal foe, softer than the Rat King on the same floor.
MINIBOSSES = {
    1: EnemyType("Gutter Matron", "rat", hp=46, attack=6, defense=2,
                 attack_type="melee", effect="poison", xp=60,
                 intro="The Gutter Matron rises from a nest of chewed paper!"),
    2: EnemyType("Drowned Watchman", "skeleton", hp=50, attack=6, defense=3,
                 attack_type="melee", effect="stun", xp=60,
                 intro="A drowned watchman of the Drain Watch stands his post!"),
    3: EnemyType("Gnashtooth the Tithe-Taker", "goblin", hp=48, attack=7,
                 defense=3, attack_type="ranged", effect="bleeding", xp=60,
                 intro="Gnashtooth guards the wet ways for the little king!"),
    4: EnemyType("The Gnawed Steward", "skeleton", hp=54, attack=7, defense=4,
                 attack_type="melee", effect="bleeding", xp=60,
                 intro="The Gnawed Steward still keeps his lord's doors!"),
    5: EnemyType("The Whispering Swarm", "bat", hp=52, attack=7, defense=3,
                 attack_type="magic", effect="stun", xp=60,
                 intro="The Whispering Swarm speaks with the crown's voice!"),
}
# Past the story floors: one nameless warden, its look cycling by floor.
DEEP_SPRITES = ("slime", "skeleton", "goblin", "bat", "rat")
DEEP_WARDEN = EnemyType("Deep Warden", "slime", hp=50, attack=7, defense=3,
                        attack_type="melee", effect="poison", xp=60,
                        intro="A Deep Warden blocks the way!")


def miniboss_type(floor: int) -> EnemyType:
    if floor in MINIBOSSES:
        return MINIBOSSES[floor]
    return replace(DEEP_WARDEN, sprite=DEEP_SPRITES[floor % len(DEEP_SPRITES)])


def miniboss_room(dungeon, seed, taken=()):
    """The room the miniboss guards (None when the floor is too small):
    never the entrance, the boss's lair or a room in ``taken``."""
    lair = boss_room(dungeon)
    free = [r for r in dungeon.rooms[1:] if r is not lair and r not in taken]
    if not free:
        return None
    return random.Random(f"miniboss-{seed}").choice(free)


def miniboss_cell(room, blocked=()) -> tuple:
    """A free interior cell of ``room`` (not on a door's neighbours or a
    ``blocked`` cell), as near the centre as possible."""
    r = room.rect
    blocked = set(blocked)
    near_door = {(x + dx, y + dy) for (x, y) in room.doors
                 for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    cells = [(x, y) for x in range(r.left + 1, r.right - 1)
             for y in range(r.top + 1, r.bottom - 1)
             if (x, y) not in blocked and (x, y) not in near_door]
    if not cells:
        return r.center
    cx, cy = r.center
    return min(cells, key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cy) ** 2, c))


def make_miniboss(floor: int, room, blocked=()):
    """The floor's miniboss, standing in ``room``."""
    e = make_enemy(miniboss_type(floor), floor)
    e.miniboss = True
    e.x, e.y = _cell_centre(miniboss_cell(room, blocked))
    return e
