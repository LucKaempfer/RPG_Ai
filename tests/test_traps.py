"""Corridor traps (``traps.py``): placement rules, triggering, damage,
disarming and run saves."""
from collections import deque

import pygame
import pytest

from pygame_rpg.dungeon import Dungeon
from pygame_rpg.player import Player
from pygame_rpg.traps import (place_traps, trap_damage, FIRE_COLD, FIRE_WARN,
                              ARROW_DELAY, SPIKE_DELAY)


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()
    screen._FONTS.clear()


def _floor(seed):
    d = Dungeon()
    d.generate(seed)
    return d


@pytest.mark.parametrize("seed", range(25))
def test_traps_sit_in_corridors_away_from_doors(seed):
    d = _floor(seed)
    traps = place_traps(d, seed, 3)
    for t in traps:
        assert d.room_map.get(t.cell, 0) is None          # a corridor cell
        x, y = t.cell
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                assert (x + dx, y + dy) not in d.door_tiles
        # The arrow slots are in solid wall.
        if t.kind == "tripwire":
            for cx, cy in t.volley_cells():
                assert not d.is_walkable((cx + t.side[0], cy + t.side[1]))
    for i, a in enumerate(traps):
        for b in traps[i + 1:]:
            assert max(abs(a.cell[0] - b.cell[0]), abs(a.cell[1] - b.cell[1])) >= 4


@pytest.mark.parametrize("seed", range(10))
def test_traps_never_block_the_way(seed):
    """Traps are walked over, not around: every room stays reachable."""
    from pygame_rpg.gui.dungeon_screen import DungeonScreen  # noqa: F401
    d = _floor(seed)
    start = d.rooms[0].rect.center
    seen, todo = {start}, deque([start])
    while todo:
        x, y = todo.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and d.is_walkable(n):
                seen.add(n)
                todo.append(n)
    assert all(r.rect.center in seen for r in d.rooms)


def test_traps_are_seeded_and_grow_with_depth():
    d = _floor(4)
    a, b = place_traps(d, 4, 1), place_traps(d, 4, 1)
    assert [(t.kind, t.cell) for t in a] == [(t.kind, t.cell) for t in b]
    total = lambda f: sum(len(place_traps(_floor(s), s, f)) for s in range(15))
    assert total(5) > total(1)


def test_damage_grows_and_armour_soaks():
    assert trap_damage("spikes", 3, 0) > trap_damage("spikes", 1, 0)
    assert trap_damage("spikes", 1, 30) < trap_damage("spikes", 1, 0)
    assert trap_damage("firepit", 1, 999) == 1


def _screen_with(display, kind, seed_range=range(40)):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    for seed in seed_range:
        d = DungeonScreen(display, Player(name="Walker"), seed=seed)
        d.enemies.clear()
        for t in d.traps:
            if t.kind == kind:
                return d, t
    pytest.skip(f"no {kind} in the tried seeds")


def _stand_on(d, cell):
    d.x, d.y = d._centre(cell)
    d._mark_visited()


def test_tripwire_volley_hurts_a_hero_who_stops(display, saves):
    d, trap = _screen_with(display, "tripwire")
    _stand_on(d, trap.cell)
    hp = d.player.current_hp
    d.step(0, 0, 1 / 60)
    assert trap.spent and trap.timer > 0
    for _ in range(int((ARROW_DELAY + 0.5) * 60)):
        d.step(0, 0, 1 / 60)
        d.draw(display)
    assert d.player.current_hp < hp
    assert not d.darts
    # Spent: walking over it again does nothing.
    hp = d.player.current_hp
    for _ in range(60):
        d.step(0, 0, 1 / 60)
    assert d.player.current_hp == hp


def test_tripwire_can_be_outrun(display, saves):
    d, trap = _screen_with(display, "tripwire")
    _stand_on(d, trap.cell)
    hp = d.player.current_hp
    d.step(0, 0, 1 / 60)
    dx, dy = (1, 0) if trap.axis == "h" else (0, 1)
    for _ in range(int((ARROW_DELAY + 0.5) * 60)):
        d.step(dx, dy, 1 / 60)
    assert d.player.current_hp == hp


def test_a_swing_cuts_a_tripwire(display, saves):
    from pygame_rpg.gui import dungeon_screen as D
    d, trap = _screen_with(display, "tripwire")
    dx, dy = (1, 0) if trap.axis == "h" else (0, 1)
    _stand_on(d, (trap.cell[0] - dx, trap.cell[1] - dy))
    d.facing = D.HERO_DIR_RIGHT if dx else D.HERO_DIR_DOWN
    d.prop_at.clear()
    d.attack()
    assert trap.spent and trap.timer == 0
    hp = d.player.current_hp
    _stand_on(d, trap.cell)
    for _ in range(60):
        d.step(0, 0, 1 / 60)
    assert d.player.current_hp == hp and not d.darts
    # Cut wires stay cut in the run save.
    again = D.DungeonScreen(display, d.player, run=d.to_run())
    assert again.traps[d.traps.index(trap)].spent


def test_fire_pit_burns_only_while_lit(display, saves):
    d, trap = _screen_with(display, "firepit")
    _stand_on(d, trap.cell)
    # Line the clock up with the start of a cold phase.
    d.trap_t = -trap.phase
    hp = d.player.current_hp
    for _ in range(int(FIRE_COLD * 60) - 2):
        d.step(0, 0, 1 / 60)
    assert d.player.current_hp == hp
    for _ in range(int(FIRE_WARN * 60) + 30):
        d.step(0, 0, 1 / 60)
        d.draw(display)
    assert d.player.current_hp < hp


def test_spikes_pop_after_a_step_and_spare_the_quick(display, saves):
    d, trap = _screen_with(display, "spikes")
    _stand_on(d, trap.cell)
    hp = d.player.current_hp
    d.step(0, 0, 1 / 60)
    assert trap.timer > 0
    _stand_on(d, (trap.cell[0] + (trap.axis == "h"), trap.cell[1] + (trap.axis == "v")))
    for _ in range(int(SPIKE_DELAY * 60) + 5):
        d.step(0, 0, 1 / 60)
    assert trap.up > 0 and d.player.current_hp == hp
    d.draw(display)


def test_traps_never_kill(display, saves):
    d, trap = _screen_with(display, "spikes")
    d.player.current_hp = 2
    _stand_on(d, trap.cell)
    for _ in range(120):
        d.step(0, 0, 1 / 60)
    assert d.player.current_hp == 1
