"""Item icons (``item_icons.py``): every item gets its own drawn sprite."""
import pygame

from pygame_rpg import items as I
from pygame_rpg.assets import AssetManager
from pygame_rpg.item_icons import draw_item_icon


def pixels(surf):
    return bytes(pygame.image.tobytes(surf, "RGBA"))


def test_every_item_draws_a_32px_icon():
    for item in I.CATALOG.values():
        icon = draw_item_icon(item)
        assert icon.get_size() == (32, 32)
        opaque = pygame.mask.from_surface(icon).count()
        assert 40 < opaque < 32 * 32, item.id        # a shape, not a filled tile


def test_each_level1_item_looks_different():
    seen = {}
    for item in I.WEAPONS + I.ARMOR + I.CONSUMABLES + I.TRINKETS + I.ABILITIES + I.JUNK:
        key = pixels(draw_item_icon(item))
        assert key not in seen, f"{item.id} looks like {seen.get(key)}"
        seen[key] = item.id


def test_tiers_show_on_the_icon():
    for base in ("sword", "chainmail", "potion", "fireball", "greed_ring"):
        looks = {pixels(draw_item_icon(I.item_by_id(i)))
                 for i in (base, f"{base}_3", f"{base}_4")}
        assert len(looks) >= 2, base


def test_icons_are_cached_and_never_saved(tmp_path):
    a = AssetManager(tmp_path)
    sword = I.item_by_id("sword")
    assert a.item_icon(sword) is a.item_icon(I.item_by_id("sword"))
    assert not any(tmp_path.iterdir())
