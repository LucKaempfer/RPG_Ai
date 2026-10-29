"""Enemies (M4): data-driven types, per-floor scaling, room placement.

Pure data + logic, no drawing (the dungeon and battle screens draw the
sprites named by ``EnemyType.sprite``; ``assets.py`` generates
placeholder sheets for every name in ``ENEMY_NAMES``).

Enemies stand still in rooms (no chasing AI); bumping into one starts a
turn-based battle (``combat.py``).
"""
from dataclasses import dataclass, field

from .dungeon import TILE_SIZE


@dataclass(frozen=True)
class EnemyType:
    name: str
    sprite: str          # enemies/<sprite>.png
    hp: int
    attack: int          # one attack stat; the type below picks how
    defense: int         # reduces the hero's hits of every type
    attack_type: str     # "melee" | "ranged" | "magic" -> hero dp/rdp/mdp
    effect: str = ""     # ailment its hits may cause (see combat.AILMENTS)
    xp: int = 10         # XP for beating it on floor 1
    min_floor: int = 1   # first floor it appears on


# Floor-1 numbers; ``make_enemy`` scales them with the floor.  Tuned so a
# fresh hero (5 in every stat, a level-1 sword, 100 HP) beats a slime in
# about three hits and survives several fights before needing a potion.
ENEMY_TYPES = {
    "slime": EnemyType("Slime", "slime", hp=28, attack=5, defense=2,
                       attack_type="melee", effect="poison", xp=20),
    "bat": EnemyType("Bat", "bat", hp=20, attack=6, defense=1,
                     attack_type="melee", effect="bleeding", xp=18),
    "goblin": EnemyType("Goblin", "goblin", hp=32, attack=6, defense=3,
                        attack_type="ranged", effect="bleeding", xp=30,
                        min_floor=2),
    "skeleton": EnemyType("Skeleton", "skeleton", hp=40, attack=7,
                          defense=4, attack_type="melee", effect="stun",
                          xp=40, min_floor=3),
}
BOSS_TYPE = EnemyType("Dungeon Lord", "boss", hp=60, attack=6, defense=4,
                      attack_type="magic", effect="burning", xp=150)

# Per floor above 1: +20% HP, +1 attack, +1 defense, +30% XP.  The hero
# gains about two levels per floor, so this keeps fights roughly even.
HP_GROWTH, ATTACK_GROWTH, DEFENSE_GROWTH, XP_GROWTH = 0.20, 1, 1, 0.30

# Enemies per room (room 0, the entrance, always stays empty).
MIN_PER_ROOM, MAX_PER_ROOM = 0, 2


@dataclass
class Enemy:
    type: EnemyType
    floor: int
    max_hp: int
    hp: int
    attack: int
    defense: int
    xp: int
    x: float = 0.0       # world pixel centre
    y: float = 0.0
    boss: bool = False
    # Ailment name -> turns left (managed by combat.py).
    statuses: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.type.name

    @property
    def alive(self) -> bool:
        return self.hp > 0


def make_enemy(etype: EnemyType, floor: int, boss=False) -> Enemy:
    up = floor - 1
    hp = round(etype.hp * (1 + HP_GROWTH * up))
    return Enemy(
        type=etype, floor=floor, max_hp=hp, hp=hp,
        attack=etype.attack + ATTACK_GROWTH * up,
        defense=etype.defense + DEFENSE_GROWTH * up,
        xp=round(etype.xp * (1 + XP_GROWTH * up)),
        boss=boss,
    )


def boss_room(dungeon):
    """The room farthest from the entrance (room 0): the boss's lair and,
    once the boss is beaten, the stairs down."""
    ex, ey = dungeon.rooms[0].rect.center
    return max(dungeon.rooms[1:] or dungeon.rooms,
               key=lambda r: (r.rect.centerx - ex) ** 2
                             + (r.rect.centery - ey) ** 2)


def _cell_centre(cell):
    return (cell[0] * TILE_SIZE + TILE_SIZE / 2,
            cell[1] * TILE_SIZE + TILE_SIZE / 2)


def place_enemies(dungeon, floor: int) -> list:
    """Spawn this floor's enemies using the dungeon's own RNG (so the
    seed decides placement too).  One boss in ``boss_room``; up to
    MAX_PER_ROOM regular enemies in every other room except room 0.
    Enemies stand on interior cells (not the walls' edge row, so doors
    stay free) and never share a cell."""
    rng = dungeon.rng
    pool = [t for t in ENEMY_TYPES.values() if t.min_floor <= floor]
    lair = boss_room(dungeon)
    enemies, used = [], set()

    def spot(room):
        r = room.rect
        cells = [(x, y) for x in range(r.left + 1, r.right - 1)
                 for y in range(r.top + 1, r.bottom - 1)
                 if (x, y) not in used]
        cell = rng.choice(cells)
        used.add(cell)
        return _cell_centre(cell)

    boss = make_enemy(BOSS_TYPE, floor, boss=True)
    boss.x, boss.y = _cell_centre(lair.rect.center)
    used.add(lair.rect.center)
    enemies.append(boss)
    for room in dungeon.rooms[1:]:
        if room is lair:
            continue
        for _ in range(rng.randint(MIN_PER_ROOM, MAX_PER_ROOM)):
            e = make_enemy(rng.choice(pool), floor)
            e.x, e.y = spot(room)
            enemies.append(e)
    return enemies
