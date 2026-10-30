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


def _facing_prop(d):
    """Stand the hero on the interior cell next to a prop, facing it."""
    from pygame_rpg.gui import dungeon_screen as D
    for prop in d.props:
        for facing, (dx, dy) in D.FACING_STEP.items():
            stand = (prop.cell[0] - dx, prop.cell[1] - dy)
            room = d.dungeon.get_room_at(prop.cell)
            r = room.rect
            if (r.left < stand[0] < r.right - 1 and r.top < stand[1] < r.bottom - 1):
                d.x, d.y = d._centre(stand)
                d.facing = facing
                return prop
    raise AssertionError("no prop with a free interior neighbour")


def test_hits_break_a_prop_into_materials(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    from pygame_rpg.props import PROP_HP, PROP_MATERIALS
    from pygame_rpg import savegame as S
    p = Player(name="Smasher")
    d = DungeonScreen(display, p, seed=6)
    prop = _facing_prop(d)
    for i in range(PROP_HP[prop.kind]):
        assert not prop.broken
        d.attack()
        d.attack()                     # still cooling down: no extra hit
        d.step(0, 0, 0.5)
        d.draw(display)
    assert prop.broken and d._fits(*d._centre(prop.cell))
    got = sum(p.materials.values())
    lows = sum(lo for lo, _ in PROP_MATERIALS[prop.kind].values())
    assert got >= lows
    d.attack()                          # broken props take no more hits
    assert sum(p.materials.values()) == got
    # The broken prop stays broken in the run save; materials are saved.
    S.save_player(p)
    run = d.to_run()
    again = DungeonScreen(display, S.load_player("Smasher"), run=run)
    assert again.props[d.props.index(prop)].broken
    assert again.player.materials == p.materials


def test_a_bow_shoots_props_from_afar(display, saves):
    from pygame_rpg import items as I
    from pygame_rpg.gui.dungeon_screen import DungeonScreen, FACING_STEP
    p = Player(name="Archer")
    bow = I.item_by_id("bow")
    p.inventory.append(bow)
    p.equip(bow)
    d = DungeonScreen(display, p, seed=6)
    prop = _facing_prop(d)
    dx, dy = FACING_STEP[d.facing]
    d.x -= dx * 64                      # two more tiles back
    d.y -= dy * 64
    if not d._fits(d.x, d.y):
        pytest.skip("no room to step back on this seed")
    hp = prop.hp
    d.attack()
    assert d.shots
    for _ in range(30):
        d.step(0, 0, 1 / 60)
        d.draw(display)
    assert not d.shots and prop.hp == hp - 1


def test_shots_stop_at_walls(display, saves):
    from pygame_rpg import items as I
    from pygame_rpg.gui.dungeon_screen import DungeonScreen, HERO_DIR_UP
    p = Player(name="Wand")
    wand = I.item_by_id("fiery_wand")
    p.inventory.append(wand)
    p.equip(wand)
    d = DungeonScreen(display, p, seed=2)
    d.prop_at.clear()
    d.facing = HERO_DIR_UP
    d.attack()
    for _ in range(120):
        d.step(0, 0, 1 / 60)
    assert not d.shots
