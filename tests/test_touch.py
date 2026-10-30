"""Android support: device detection, on-screen controls, the audio cache."""
import pygame
import pytest

from pygame_rpg import audio, device, settings
from pygame_rpg.gui import screen as screen_mod
from pygame_rpg.gui import touch
from pygame_rpg.gui.display import Display, TOUCH_BAR, android_size, letterbox
from pygame_rpg.player import Player


@pytest.fixture
def touch_display(saves, monkeypatch):
    """A Display with the touch controls on, in a 1920 x 1080 window."""
    monkeypatch.setattr(device, "TOUCH", True)
    monkeypatch.setattr(settings, "current", settings.Settings())
    monkeypatch.setattr(settings, "virtual_held", set())
    pygame.init()
    screen_mod._FONTS.clear()      # fonts from an earlier pygame.init
    d = Display()
    d.window = pygame.display.set_mode((1920, 1080), pygame.RESIZABLE)
    d._layout()
    pygame.event.clear()
    yield d
    pygame.quit()
    screen_mod._FONTS.clear()


def finger(kind, pos, d, fid=1):
    w, h = d.window.get_size()
    return pygame.event.Event(kind, x=pos[0] / w, y=pos[1] / h, dx=0, dy=0,
                              touch_id=0, finger_id=fid, pressure=1.0)


def posted():
    return [e for e in pygame.event.get() if e.type == pygame.KEYDOWN]


def test_data_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("RPG_DATA_DIR", raising=False)
    monkeypatch.setattr(device, "IS_ANDROID", False)
    assert str(device.data_dir()) == "."
    monkeypatch.setattr(device, "IS_ANDROID", True)
    monkeypatch.setenv("ANDROID_PRIVATE", str(tmp_path))
    assert device.data_dir() == tmp_path
    monkeypatch.setenv("RPG_DATA_DIR", "/elsewhere")
    assert str(device.data_dir()) == "/elsewhere"


def test_layout_leaves_room_for_the_controls():
    view = letterbox((1600, 1200), side=round(1200 * TOUCH_BAR))
    assert view.x >= round(1200 * TOUCH_BAR) and view.w / view.h == 800 / 600
    # A 20:9 phone: the canvas fills the height, bars are wide anyway.
    assert android_size((2400, 1080)) == (1333, 600)
    assert android_size((1080, 2400)) == (1333, 600)     # portrait report
    w, h = android_size((2048, 1536))                    # 4:3 tablet
    assert w >= 800 + 2 * 600 * TOUCH_BAR and h >= 600


def test_pad_directions():
    assert touch.pad_dirs(1, 1, 100) == frozenset()       # dead zone
    assert touch.pad_dirs(80, 0, 100) == {"right"}
    assert touch.pad_dirs(0, -80, 100) == {"up"}
    assert touch.pad_dirs(60, 60, 100) == {"right", "down"}
    assert touch.pad_dirs(60, 50, 100, diagonal=False) == {"right"}


def test_controls_sit_in_the_bars(touch_display):
    t = touch_display.touch
    view = touch_display.view
    (cx, cy), r = t.pad
    assert cx + r <= view.left
    for (bx, by), br, _ in t.buttons.values():
        assert bx + br <= view.left or bx - br >= view.right


def test_dungeon_pad_and_buttons(touch_display):
    d = touch_display
    d.update(0.0, "dungeon")
    (cx, cy), r = d.touch.pad
    assert d.handle_event(finger(pygame.FINGERDOWN, (cx + r * 0.7, cy), d)) is None
    assert settings.virtual_held == {"right"}
    keys = pygame.key.get_pressed()
    assert settings.held(keys, "right") and not settings.held(keys, "left")
    d.handle_event(finger(pygame.FINGERMOTION, (cx, cy - r * 0.7), d))
    assert settings.virtual_held == {"up"}
    d.handle_event(finger(pygame.FINGERUP, (cx, cy - r * 0.7), d))
    assert settings.virtual_held == set()
    assert posted() == []                       # moving sends no keys

    for name, action in (("a", "attack"), ("b", "interact"), ("bag", "inventory")):
        (bx, by), _, _ = d.touch.buttons[name]
        d.handle_event(finger(pygame.FINGERDOWN, (bx, by), d, fid=2))
        d.handle_event(finger(pygame.FINGERUP, (bx, by), d, fid=2))
        (ev,) = posted()
        assert settings.pressed(ev, action)
        assert not settings.pressed(ev, "attack" if action != "attack" else "interact")
    (bx, by), _, _ = d.touch.buttons["menu"]
    d.handle_event(finger(pygame.FINGERDOWN, (bx, by), d, fid=2))
    (ev,) = posted()
    assert ev.key == pygame.K_ESCAPE


def test_walk_and_attack_at_once(touch_display):
    d = touch_display
    d.update(0.0, "dungeon")
    (cx, cy), r = d.touch.pad
    (ax, ay), _, _ = d.touch.buttons["a"]
    d.handle_event(finger(pygame.FINGERDOWN, (cx - r * 0.7, cy), d, fid=1))
    d.handle_event(finger(pygame.FINGERDOWN, (ax, ay), d, fid=2))
    assert settings.virtual_held == {"left"}
    assert settings.pressed(posted()[0], "attack")


def test_menu_pad_sends_arrows_and_repeats(touch_display):
    d = touch_display
    d.update(0.0, "inventory")
    (cx, cy), r = d.touch.pad
    d.handle_event(finger(pygame.FINGERDOWN, (cx, cy + r * 0.7), d))
    assert [e.key for e in posted()] == [pygame.K_DOWN]
    assert settings.virtual_held == set()      # menus don't "hold"
    d.update(touch.REPEAT_DELAY + 0.01, "inventory")
    d.update(touch.REPEAT_EVERY + 0.01, "inventory")
    assert [e.key for e in posted()] == [pygame.K_DOWN, pygame.K_DOWN]
    d.handle_event(finger(pygame.FINGERUP, (cx, cy + r * 0.7), d))
    d.update(1.0, "inventory")
    assert posted() == []
    (ax, ay), _, _ = d.touch.buttons["a"]
    (bx, by), _, _ = d.touch.buttons["b"]
    d.handle_event(finger(pygame.FINGERDOWN, (ax, ay), d, fid=2))
    d.handle_event(finger(pygame.FINGERDOWN, (bx, by), d, fid=3))
    assert [e.key for e in posted()] == [pygame.K_RETURN, pygame.K_ESCAPE]
    assert d.touch.hit(d.touch.buttons["bag"][0]) is None   # dungeon only
    assert d.touch.hit(d.touch.buttons["menu"][0]) is None


def test_taps_on_the_canvas_reach_the_screens(touch_display):
    d = touch_display
    d.update(0.0, "title")
    view = d.view
    tap = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=view.center,
                             button=1, touch=True)
    ev = d.handle_event(tap)
    assert abs(ev.pos[0] - 400) <= 1 and abs(ev.pos[1] - 300) <= 1
    # SDL's mouse copy of a finger on the controls is swallowed.
    (ax, ay), _, _ = d.touch.buttons["a"]
    assert d.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, pos=(ax, ay), button=1, touch=True)) is None


def test_back_button_is_escape(touch_display):
    ev = touch_display.handle_event(pygame.event.Event(
        pygame.KEYDOWN, key=pygame.K_AC_BACK, mod=0))
    assert ev.key == pygame.K_ESCAPE


def test_present_draws_the_controls(touch_display):
    d = touch_display
    d.update(0.0, "dungeon")
    d.canvas.fill((255, 0, 0))
    d.present()
    (cx, cy), _ = d.touch.pad
    assert d.window.get_at((cx, cy))[:3] == touch.PAD_COLOR
    assert d.window.get_at(d.view.center)[:3] == (255, 0, 0)


def test_dungeon_walks_on_the_pad_and_names_the_buttons(touch_display):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen, controls_hint
    ds = DungeonScreen(touch_display.canvas, Player(name="Thumbs"), seed=1)
    x0 = ds.x
    settings.virtual_held.add("right")
    for _ in range(10):
        ds.handle_update(1 / 60)
    settings.virtual_held.clear()
    assert ds.x != x0 or ds.moving
    assert controls_hint().startswith("D-pad: move")
    assert settings.action_label("interact") == "B"


def test_suspend_saves_the_run(saves):
    from pygame_rpg import savegame
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    pygame.init()
    try:
        canvas = pygame.display.set_mode((800, 600))
        ds = DungeonScreen(canvas, Player(name="Pocket"), seed=3)
        savegame.delete_run("Pocket")
        ds.suspend()
        assert savegame.load_run("Pocket") is not None
        assert savegame.name_exists("Pocket")
    finally:
        pygame.quit()


def test_audio_cache(saves, monkeypatch):
    pygame.init()
    try:
        a = audio.Audio()
        a.init(background=False)
        if not a.ok:
            pytest.skip("no mixer on this machine")
        folders = list(audio.cache_root().glob("audio-*"))
        assert len(folders) == 1
        assert len(list(folders[0].glob("*.pcm"))) == len(audio._RECIPES)
        # A second start loads the cache instead of synthesising.
        def boom(s):
            raise AssertionError("synthesised again")
        monkeypatch.setattr(audio, "_RECIPES",
                            {k: boom for k in audio._RECIPES})
        b = audio.Audio()
        b._build(*pygame.mixer.get_init()[::2])
        assert set(b.sounds) == set(a.sounds)
        assert (b.sounds["sewer"].get_raw() == a.sounds["sewer"].get_raw())
    finally:
        pygame.quit()
