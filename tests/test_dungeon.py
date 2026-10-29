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
