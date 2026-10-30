"""Inventory screen: backpack filter tabs."""
import pygame
import pytest

from pygame_rpg import items as I
from pygame_rpg.player import Player
from pygame_rpg.gui.inventory_screen import InventoryScreen, FILTERS


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()       # fonts cached before another module's pygame.quit()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()
    screen._FONTS.clear()       # don't leave dead fonts for the next module


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def screen(display):
    p = Player(name="T")
    p.inventory = [I.item_by_id(i) for i in
                   ("potion", "sword", "leather_cap", "bow", "fireball", "ration")]
    return InventoryScreen(display, p)


def tab(name):
    return [label for label, _ in FILTERS].index(name)


def test_tabs_filter_the_backpack(display):
    s = screen(display)
    assert len(s.shown()) == 6
    s.handle_event(click(s.tab_rects[tab("Weapons")].center))
    assert [i.id for i in s.shown()] == ["sword", "bow"]
    s.handle_event(click(s.tab_rects[tab("Potions")].center))
    assert [i.id for i in s.shown()] == ["potion", "ration"]
    s.handle_event(click(s.tab_rects[tab("Junk")].center))
    assert s.shown() == []
    s.draw(display)


def test_rows_pick_from_the_filtered_list(display):
    s = screen(display)
    s.set_filter(tab("Weapons"))
    s.handle_event(click(s._row_rects()[1].center))
    assert s.selected.id == "bow"
    s.handle_event(click(s.btn_equip.rect.center))
    assert s.player.equipment["weapon"].id == "bow"
    assert [i.id for i in s.shown()] == ["sword"]


def test_keys_cycle_filters_and_hidden_selection_drops(display):
    s = screen(display)
    s.selected = s.player.inventory[0]           # the potion
    s.handle_event(key(pygame.K_RIGHT))
    assert s.filter == tab("Weapons") and s.selected is None
    s.handle_event(key(pygame.K_LEFT))
    s.handle_event(key(pygame.K_LEFT))
    assert s.filter == len(FILTERS) - 1
