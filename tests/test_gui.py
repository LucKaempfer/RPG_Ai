"""Headless GUI checks for the M5 polish: keyboard menus and effects."""
import random

import pygame
import pytest

from pygame_rpg import combat as C, items as I, savegame as S
from pygame_rpg.gui.effects import Particles, menu_key
from pygame_rpg.player import Player
from pygame_rpg.gui.screen import QUIT


@pytest.fixture(scope="module")
def display():
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def test_menu_key_wraps_and_activates():
    assert menu_key(key(pygame.K_DOWN), 3, None) == (0, False)
    assert menu_key(key(pygame.K_UP), 3, 0) == (2, False)
    assert menu_key(key(pygame.K_s), 3, 2) == (0, False)
    assert menu_key(key(pygame.K_RETURN), 3, 1) == (1, True)
    assert menu_key(key(pygame.K_SPACE), 3, None) == (0, True)
    assert menu_key(key(pygame.K_x), 3, 1) == (1, False)


def test_particles_fade_out(display):
    fx = Particles(random.Random(0))
    fx.burst(100, 100, (255, 0, 0), count=10)
    assert len(fx.items) == 10
    fx.draw(display)
    for _ in range(30):
        fx.update(0.05)
    assert not fx


def test_title_keyboard(display):
    from pygame_rpg.gui.title_screen import TitleScreen
    t = TitleScreen(display)
    t.handle_update(0.5)
    t.draw(display)
    assert t.handle_event(key(pygame.K_RETURN)) == ("tutorial", {"next": "hero_maker"})
    t.handle_event(key(pygame.K_DOWN))          # focus 0 -> 1
    assert t.handle_event(key(pygame.K_RETURN)) == ("tutorial", {"next": "hero_chooser"})
    t.handle_event(key(pygame.K_DOWN))
    assert t.handle_event(key(pygame.K_RETURN)) is QUIT


def test_base_keyboard(display, saves):
    from pygame_rpg.gui.base_screen import BaseScreen
    p = Player(name="Keys")
    b = BaseScreen(display, p)
    b.handle_event(key(pygame.K_DOWN))          # Inventory
    assert b.handle_event(key(pygame.K_RETURN)) == ("inventory", {"player": p})
    b.handle_event(key(pygame.K_DOWN))
    b.handle_event(key(pygame.K_DOWN))          # Adventure
    assert b.handle_event(key(pygame.K_RETURN)) == ("dungeon", {"player": p})
    b.draw(display)


def test_base_keyboard_only_reaches_choose_stat(display, saves):
    from pygame_rpg.gui.base_screen import BaseScreen
    p = Player(name="Keys", xp=150)
    b = BaseScreen(display, p)
    b.handle_event(key(pygame.K_DOWN))
    assert b.handle_event(key(pygame.K_RETURN)) == ("level_up", {"player": p})


def test_level_up_keyboard_and_fanfare(display, saves):
    from pygame_rpg.gui.level_up_screen import LevelUpScreen
    p = Player(name="Keys", xp=350)                 # two levels pending
    lu = LevelUpScreen(display, p)
    assert lu.fx and lu.glow_t > 0                  # fanfare on arrival
    lu.handle_event(key(pygame.K_DOWN))
    lu.handle_event(key(pygame.K_DOWN))             # AP
    assert lu.handle_event(key(pygame.K_RETURN)) is None
    assert p.lvl == 2 and p.ap == 6
    lu.handle_update(0.1)
    lu.draw(display)
    assert lu.handle_event(key(pygame.K_RETURN)) == ("base", {"player": p})
    assert p.lvl == 3 and p.ap == 7


def test_battle_end_animations(display, saves):
    from pygame_rpg.gui.battle_screen import BattleScreen, END_TIME
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = Player(name="Anim")
    ds = DungeonScreen(display, p, seed=2)
    foe = next(e for e in ds.enemies if not e.boss)
    win = BattleScreen(display, p, foe, ds, rng=random.Random(0))
    foe.hp = 1
    win._do(("attack",))
    assert win.battle.state == C.WON and win.fx and win.end_t == 0.0
    for _ in range(3):
        win.handle_update(END_TIME / 2)
        win.draw(display)
    other = next(e for e in ds.enemies if not e.boss and e is not foe)
    other.hp = other.max_hp = 999
    lose = BattleScreen(display, p, other, ds, rng=random.Random(0))
    p.current_hp = 1
    lose._do(("attack",))
    assert lose.battle.state == C.LOST
    lose.handle_update(END_TIME)
    lose.draw(display)


def test_chest_pop(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = Player(name="Chest")
    ds = DungeonScreen(display, p, seed=4)
    ds.x, ds.y = ds._centre(ds.chests[0][0])
    ds.enemies = []
    ds.step(0, 0, 1 / 60)
    assert ds.chests[0][1] and ds.fx
    ds.draw(display)


@pytest.mark.parametrize("name", ["slime", "bat", "rat", "goblin", "skeleton", "rat_king"])
def test_enemy_sheets_have_their_own_shape(display, name):
    from pygame_rpg.assets import _gen_enemy_sheet
    sheet = _gen_enemy_sheet(name)
    assert sheet.get_size() == (8 * 32, 32)
    if name != "slime":
        assert (pygame.image.tobytes(sheet, "RGBA")
                != pygame.image.tobytes(_gen_enemy_sheet("slime"), "RGBA"))
