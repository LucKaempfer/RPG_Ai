"""Room props: placement rules, blocking, and reachability."""
from collections import deque

import pygame
import pytest

from pygame_rpg.dungeon import Dungeon
from pygame_rpg.enemies import place_enemies, cell_of
from pygame_rpg.player import Player
from pygame_rpg.props import place_props, PROP_KINDS


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()


def _floor(seed):
    d = Dungeon()
    d.generate(seed)
    return d


@pytest.mark.parametrize("seed", range(25))
def test_props_stay_on_edges_away_from_doors(seed):
    d = _floor(seed)
    props = place_props(d, seed)
    assert props and all(p.kind in PROP_KINDS for p in props)
    cells = [p.cell for p in props]
    assert len(cells) == len(set(cells))
    for p in props:
        room = d.get_room_at(p.cell)
        assert room is not None and p.cell not in d.door_tiles
        r = room.rect
        assert p.cell[0] in (r.left, r.right - 1) or p.cell[1] in (r.top, r.bottom - 1)
        for door in d.door_tiles:
            assert max(abs(door[0] - p.cell[0]), abs(door[1] - p.cell[1])) > 1
    enemy_cells = {cell_of(e) for e in place_enemies(d, 1)}
    assert not enemy_cells & set(cells)


@pytest.mark.parametrize("seed", range(25))
def test_props_never_cut_off_the_way(seed):
    """Every corridor, door and room interior stays reachable (at most a
    room corner can end up boxed in behind two props)."""
    d = _floor(seed)
    solid = {p.cell for p in place_props(d, seed)}
    start = d.rooms[0].rect.center
    seen, todo = {start}, deque([start])
    while todo:
        x, y = todo.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if d.is_walkable(n) and n not in solid and n not in seen:
                seen.add(n)
                todo.append(n)
    corners = {(x, y) for room in d.rooms
               for x in (room.rect.left, room.rect.right - 1)
               for y in (room.rect.top, room.rect.bottom - 1)}
    assert set(d.room_map) - solid - corners <= seen


def test_props_are_seeded():
    a, b = place_props(_floor(5), 5), place_props(_floor(5), 5)
    assert [(p.kind, p.cell) for p in a] == [(p.kind, p.cell) for p in b]


def test_props_block_the_hero(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen, TILE_SIZE
    d = DungeonScreen(display, Player(name="Bumper"), seed=4)
    prop = d.props[0]
    x, y = d._centre(prop.cell)
    assert not d._fits(x, y)
    prop.broken = True
    assert d._fits(x, y) or not d.dungeon.is_walkable(prop.cell)
    d.draw(display)
