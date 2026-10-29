"""Floor generation (``dungeon.py``) and enemy placement (``enemies.py``)."""
from collections import deque

import pytest

from pygame_rpg import enemies as E
from pygame_rpg.dungeon import Dungeon


def floor(seed):
    d = Dungeon()
    d.generate(seed)
    return d


@pytest.mark.parametrize("seed", range(10))
def test_rooms_do_not_overlap(seed):
    rooms = floor(seed).rooms
    for i, a in enumerate(rooms):
        assert not any(a.rect.colliderect(b.rect) for b in rooms[i + 1:])


@pytest.mark.parametrize("seed", range(10))
def test_every_room_is_reachable(seed):
    d = floor(seed)
    start = d.rooms[0].rect.center
    seen, todo = {start}, deque([start])
    while todo:
        x, y = todo.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and d.is_walkable(n):
                seen.add(n)
                todo.append(n)
    assert all(r.rect.center in seen for r in d.rooms)


def test_same_seed_same_floor_and_enemies():
    a, b = floor(42), floor(42)
    assert [r.rect for r in a.rooms] == [r.rect for r in b.rooms]
    assert ([(e.name, e.x, e.y) for e in E.place_enemies(a, 3)]
            == [(e.name, e.x, e.y) for e in E.place_enemies(b, 3)])


@pytest.mark.parametrize("seed", range(10))
def test_one_boss_in_the_lair_and_an_empty_entrance(seed):
    d = floor(seed)
    es = E.place_enemies(d, 1)
    bosses = [e for e in es if e.boss]
    assert len(bosses) == 1
    assert E.boss_room(d).contains(E.cell_of(bosses[0]))
    assert not any(d.rooms[0].contains(E.cell_of(e)) for e in es)


def test_floor_pool_and_scaling():
    assert {t.name for t in E.ENEMY_TYPES.values() if t.min_floor <= 1} == {"Slime", "Bat", "Rat"}
    s1 = E.make_enemy(E.ENEMY_TYPES["slime"], 1)
    s3 = E.make_enemy(E.ENEMY_TYPES["slime"], 3)
    assert s3.max_hp > s1.max_hp and s3.attack == s1.attack + 2


def test_walls_block_sight():
    # Two 5x5 floors side by side with a solid wall column between them,
    # and a one-cell gap (door) at the bottom row.
    d = Dungeon()
    for x in range(0, 11):
        for y in range(0, 5):
            if x != 5 or y == 4:
                d.room_map[(x, y)] = None
    seen = d.visible_from((2, 1), 8)
    assert (4, 1) in seen and (5, 1) in seen        # floor and the wall itself
    assert (7, 1) not in seen and (9, 0) not in seen    # behind the wall
    assert (5, 4) in seen                           # the gap itself


def test_sight_lines_are_clear():
    d = floor(3)
    c = d.rooms[0].rect.center
    seen = d.visible_from(c, 8)
    assert all(d._line_clear(*c, *cell) for cell in seen)


@pytest.mark.parametrize("seed", range(5))
def test_corridors_are_short(seed):
    d = floor(seed)
    corridor = sum(1 for v in d.room_map.values() if v is None)
    assert corridor / len(d.rooms) < 12


def test_doors_block_sight_unless_standing_in_them():
    # Corridor (0..3, 2) -> door (4, 2) -> room x 5..9.
    d = Dungeon()
    for x in range(0, 10):
        d.room_map[(x, 2)] = None
    for x in range(5, 10):
        for y in range(0, 5):
            d.room_map[(x, y)] = None
    d.door_tiles = {(4, 2)}
    from_corridor = d.visible_from((1, 2), 8)
    assert (4, 2) in from_corridor                  # the gate itself
    assert (6, 2) not in from_corridor              # not the room behind it
    in_door = d.visible_from((4, 2), 8)
    assert (1, 2) in in_door and (7, 3) in in_door  # both sides from the doorway
    from_room = d.visible_from((7, 2), 8)
    assert (4, 2) in from_room and (2, 2) not in from_room


def test_gate_faces_the_corridor():
    from pygame_rpg.assets import SEWER_GATE_N, SEWER_GATE_S, SEWER_GATE_W, SEWER_GATE_E
    d = floor(4)
    for door in d.door_tiles:
        tile = d._tile_for(door)
        dx, dy = {SEWER_GATE_N: (0, -1), SEWER_GATE_S: (0, 1),
                  SEWER_GATE_W: (-1, 0), SEWER_GATE_E: (1, 0)}[tile]
        n = (door[0] + dx, door[1] + dy)
        assert n in d.room_map and d.room_map[n] is None


def test_no_peeking_diagonally_past_a_gate():
    # Corridor ends at (3, 2); door (4, 2) in the room's west edge; the
    # room's wall ring is (3, 1) / (3, 3).  (4, 1) / (4, 3) are room floor.
    d = Dungeon()
    for x in range(0, 4):
        d.room_map[(x, 2)] = None
    for x in range(4, 9):
        for y in range(0, 5):
            d.room_map[(x, y)] = None
    d.door_tiles = {(4, 2)}
    seen = d.visible_from((3, 2), 8)
    assert (4, 2) in seen
    assert not any((x, y) in seen for x in range(4, 9) for y in range(0, 5) if (x, y) != (4, 2))
