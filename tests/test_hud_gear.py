"""The HUD's gear strip: the equipped weapon and armour show in the
dungeon, empty slots as dim outlines, and a tap on the strip opens the
inventory (touch-friendly)."""
import pygame
import pytest

from pygame_rpg.gui.hud import Hud, GEAR_SLOTS, GEAR_X, GEAR_Y, GEAR_BOX, GEAR_STEP
from pygame_rpg.items import item_by_id
from pygame_rpg.player import Player


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()
    screen._FONTS.clear()


def geared(*ids, lvl=5):
    p = Player(name="Gear", lvl=lvl)
    for i in ids:
        item = item_by_id(i)
        p.inventory.append(item)
        p.equip(item)
    return p


def box_centre(i):
    return (GEAR_X + i * GEAR_STEP + GEAR_BOX // 2, GEAR_Y + GEAR_BOX // 2)


def strip(surface):
    return [tuple(surface.get_at(box_centre(i)))[:3] for i in range(len(GEAR_SLOTS))]


def test_gear_strip_covers_weapon_and_armour_slots():
    assert [s for s, _ in GEAR_SLOTS] == ["weapon", "head", "torso", "hands", "feet"]


def test_equipped_items_change_the_strip(display):
    hud = Hud()
    bare = pygame.Surface((800, 600))
    hud.draw(bare, Player(name="Bare"), 1)
    dressed = pygame.Surface((800, 600))
    hud.draw(dressed, geared("sword", "iron_helmet", "chainmail",
                             "leather_gloves", "iron_boots"), 1)
    # Every slot looks different once something is equipped in it.
    for a, b in zip(strip(bare), strip(dressed)):
        assert a != b


def test_empty_slot_shows_a_dim_outline(display):
    hud = Hud()
    s = pygame.Surface((800, 600))
    hud.draw(s, geared("sword"), 1)
    weapon, *empty = strip(s)
    for px in empty:
        assert max(px) < 120            # dim silhouette, not a bright icon


def test_tapping_the_strip_opens_the_inventory(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = geared("sword")
    ds = DungeonScreen(display, p, seed=3)
    ds.draw(display)
    tap = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=box_centre(2))
    assert ds.handle_event(tap) == ("inventory", {"player": p, "return_to": ds})
    miss = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(400, 300))
    assert ds.handle_event(miss) is None
