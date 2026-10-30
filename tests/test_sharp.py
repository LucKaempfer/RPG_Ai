"""Sharp picture: the game font, Scale2x window scaling, big sprites and
the shared panel / bar / background drawing."""
import pygame
import pytest

from pygame_rpg.assets import AssetManager, upscale, SPRITE_OUTLINE
from pygame_rpg.gui import screen as S
from pygame_rpg.gui.display import Display


@pytest.fixture(scope="module")
def display():
    pygame.init()
    S._FONTS.clear()       # fonts cached before another module's pygame.quit()
    yield Display()
    pygame.quit()
    S._FONTS.clear()       # don't leave dead fonts for the next module


def test_game_font_is_inter_and_cached(display):
    assert S.FONT_FILE.exists()
    f = S.font(24)
    assert f is S.font(24)
    assert f.name.startswith("Inter")
    # Same text height as the old default font at that size.
    assert abs(f.get_linesize() - pygame.font.Font(None, 24).get_linesize()) <= 2


def test_double_size_window_keeps_hard_pixels(display):
    display.window = pygame.display.set_mode((1600, 1200))
    display._layout()
    display.canvas.fill((0, 0, 0))
    display.canvas.set_at((10, 10), (255, 255, 255))
    display.present()
    # One canvas pixel becomes exactly a 2 x 2 block, no smoothing.
    block = [display.window.get_at((x, y))[:3] for x in (20, 21) for y in (20, 21)]
    assert block == [(255, 255, 255)] * 4
    assert display.window.get_at((22, 20))[:3] == (0, 0, 0)


def test_odd_size_window_keeps_colours(display):
    display.window = pygame.display.set_mode((1200, 900))
    display._layout()
    for colour in ((0, 0, 0), (22, 22, 30), (230, 190, 90)):
        display.canvas.fill(colour)
        display.present()
        shown = display.window.get_at(display.view.center)[:3]
        assert all(abs(a - b) <= 3 for a, b in zip(shown, colour)), (colour, shown)


def test_upscale_sizes_and_outline(display):
    hero = AssetManager().hero_frames()[0]
    big = upscale(hero, 128)
    assert big.get_size() == (128, 128)
    assert upscale(hero, (48, 48)).get_size() == (48, 48)
    lined = upscale(hero, 128, outline=True)
    colours = {tuple(lined.get_at((x, y))) for x in range(128) for y in range(128)}
    assert SPRITE_OUTLINE + (255,) in colours
    # Transparent around the sprite stays transparent.
    assert lined.get_at((0, 0))[3] == 0


def test_panel_bar_and_background_draw(display):
    surf = display.canvas
    S.draw_background(surf)
    corner, middle = surf.get_at((0, 0)), surf.get_at((400, 300))
    assert sum(corner[:3]) < sum(middle[:3])          # vignette
    S.draw_panel(surf, (100, 100, 200, 80))
    assert surf.get_at((200, 140))[:3] == S.PANEL_COLOR
    S.draw_bar(surf, (100, 300, 200, 12), 50, 100, (200, 70, 70))
    assert surf.get_at((150, 308))[:3] == (200, 70, 70)   # filled half
    assert surf.get_at((250, 308))[:3] == S.TROUGH_COLOR  # empty half
    S.Button("OK", (100, 400, 120, 40)).draw(surf, hot=True)
