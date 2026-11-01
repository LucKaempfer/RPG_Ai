"""High-resolution rendering (hires.py): logical sizes over 2x pixels,
text and shapes at full resolution, and every screen drawing with it."""
import pygame
import pytest

from pygame_rpg import assets as A, hires
from pygame_rpg.gui import dungeon_screen, screen as S


def _clear_caches():
    for cache in (S._FONTS, S._WINDOW_FONTS, S._BACKGROUNDS, dungeon_screen._LIGHT,
                  dungeon_screen._SHADOWS, dungeon_screen._LORE_SPRITES,
                  A.assets._cache):
        cache.clear()


@pytest.fixture(scope="module")
def hi():
    pygame.init()
    pygame.display.set_mode((800, 600))
    _clear_caches()
    hires.install(2)
    yield
    hires.uninstall()
    _clear_caches()
    pygame.quit()


def test_surface_sizes_are_logical(hi):
    s = pygame.Surface((40, 30), pygame.SRCALPHA)
    assert isinstance(s, hires.HiSurface)
    assert s.get_size() == (40, 30) and s.get_rect(center=(5, 5)).size == (40, 30)
    assert hires.raw_size(s) == (80, 60)
    s.set_at((3, 4), (255, 0, 0))
    assert [hires.Plain.get_at(s, (x, y))[:3] for x in (6, 7) for y in (8, 9)] \
        == [(255, 0, 0)] * 4
    assert s.get_at((3, 4))[:3] == (255, 0, 0)


def test_blit_fill_and_draw_use_logical_positions(hi):
    s = pygame.Surface((50, 50))
    s.fill((0, 0, 0))
    s.fill((0, 255, 0), (10, 10, 5, 5))
    assert hires.Plain.get_at(s, (29, 29))[:3] == (0, 255, 0)
    assert hires.Plain.get_at(s, (30, 30))[:3] == (0, 0, 0)
    sprite = pygame.Surface((4, 4))
    sprite.fill((0, 0, 255))
    assert s.blit(sprite, (20, 20)) == pygame.Rect(20, 20, 4, 4)
    assert s.get_at((23, 23))[:3] == (0, 0, 255)
    pygame.draw.rect(s, (255, 255, 0), (40, 40, 2, 2))
    assert hires.Plain.get_at(s, (83, 83))[:3] == (255, 255, 0)
    # A plain surface (e.g. a loaded image) is enlarged in pixel blocks.
    plain = hires.Plain((2, 2))
    plain.fill((9, 9, 9))
    s.blit(plain, (0, 0))
    assert hires.Plain.get_at(s, (3, 3))[:3] == (9, 9, 9)


def test_fractional_widths_draw_finer_lines(hi):
    s = pygame.Surface((10, 10))
    s.fill((0, 0, 0))
    pygame.draw.line(s, (255, 255, 255), (0, 5), (9, 5), 0.5)
    rows = [hires.Plain.get_at(s, (8, y))[:3] == (255, 255, 255) for y in range(20)]
    assert sum(rows) == 1                     # one real pixel thick


def test_text_is_rendered_at_double_resolution(hi):
    f = S.font(24)
    assert isinstance(f, hires.HiFont)
    text = f.render("Hello", True, (255, 255, 255))
    w, h = text.get_size()
    assert hires.raw_size(text)[1] >= 2 * h - 1
    assert f.size("Hello") == (w, h)


def test_copies_transforms_and_zoom(hi):
    s = pygame.Surface((8, 6), pygame.SRCALPHA)
    s.fill((1, 2, 3, 255))
    for out in (s.copy(), s.subsurface((0, 0, 4, 3)), s.convert_alpha(),
                pygame.transform.flip(s, True, False)):
        assert isinstance(out, hires.HiSurface)
        assert out.get_at((0, 0)) == (1, 2, 3, 255)
    big = pygame.transform.scale(s, (16, 12))
    assert big.get_size() == (16, 12) and hires.raw_size(big) == (32, 24)
    frames = A.AssetManager().hero_frames(size=128)
    assert frames[0].get_size() == (128, 128)
    assert hires.raw_size(frames[0]) == (256, 256)    # drawn at that size


def test_every_screen_draws_in_hires(hi, saves):
    from pygame_rpg.gui.display import Display
    from pygame_rpg.main import build_screen
    from pygame_rpg.player import Player
    from pygame_rpg import items as I
    d = Display()
    assert isinstance(d.canvas, hires.HiSurface)
    p = Player(name="Sharp")
    p.inventory.extend(I.item_by_id(k) for k in list(I.CATALOG)[:8])
    dung = build_screen("dungeon", d.canvas, {"player": p, "seed": 2})
    screens = [build_screen(n, d.canvas, {"player": p}) for n in
               ("title", "hero_maker", "hero_chooser", "base", "inventory",
                "stats", "settings", "level_up")]
    screens.append(dung)
    for s in screens:
        for _ in range(3):
            s.handle_update(0.1)
            s.draw(d.canvas)
        for size in ((1600, 1200), (1200, 900), (2000, 1500)):
            d.window = pygame.display.set_mode(size)
            d._layout()
            d.present()
            assert d.window.get_at(d.view.center) is not None


def test_touch_screen_in_hires(hi, saves, monkeypatch):
    """Phone layout: the window holds the canvas's real pixels, the wide
    dungeon canvas is shown 1:1 and the controls draw on the window."""
    from pygame_rpg import device, settings
    from pygame_rpg.gui.display import Display, android_size, WIDE_HEIGHT
    from pygame_rpg.main import build_screen
    from pygame_rpg.player import Player
    assert android_size((2400, 1080))[1] == WIDE_HEIGHT * 2
    monkeypatch.setattr(device, "TOUCH", True)
    monkeypatch.setattr(settings, "virtual_held", set())
    d = Display()
    d.window = pygame.display.set_mode(android_size((2400, 1080)))
    d._layout()
    dung = build_screen("dungeon", d.canvas, {"player": Player(name="Phone"), "seed": 1})
    canvas = d.canvas_for(dung)
    assert canvas.get_size()[1] == WIDE_HEIGHT
    assert hires.raw_size(canvas) == d.view.size == d.window.get_size()
    d.update(0.0, "dungeon")
    dung.draw(canvas)
    d.present()
    (cx, cy), _ = d.touch.pad
    assert d.window.get_at((cx, cy)) is not None
