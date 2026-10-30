"""Player-facing stat names (``stat_names.py``) and the screens using them."""
import pygame
import pytest

from pygame_rpg import items as I
from pygame_rpg.player import Player, UPGRADABLE_STATS, BONUS_STATS
from pygame_rpg.stat_names import LABEL, SHORT, ABOUT, stat_line


def test_every_stat_has_a_name_and_description():
    for stat in set(UPGRADABLE_STATS) | set(BONUS_STATS) | {"mp"}:
        assert LABEL[stat] and SHORT[stat] and ABOUT[stat]
        assert LABEL[stat].upper() != stat.upper()


def test_stat_line_uses_friendly_names():
    assert stat_line(I.item_by_id("sword")) == ["+1 Melee Atk", "+1 Melee Def"]
    assert "DP" not in I.item_by_id("shield").description


@pytest.fixture(scope="module")
def display():
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()


def test_stat_screens_render(display, saves):
    from pygame_rpg.gui.stats_screen import StatsScreen
    from pygame_rpg.gui.level_up_screen import LevelUpScreen
    from pygame_rpg.gui.base_screen import BaseScreen
    surf = display
    p = Player(name="T", xp=150)
    for cls in (StatsScreen, LevelUpScreen, BaseScreen):
        cls(surf, p).draw(surf)
