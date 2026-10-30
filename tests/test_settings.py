"""Settings: saving, key bindings, the settings screen and brightness."""
import json

import pygame
import pytest

from pygame_rpg import settings
from pygame_rpg.gui.screen import QUIT


@pytest.fixture
def fresh(saves, monkeypatch):
    """Default settings for one test, saved into the temp save folder."""
    monkeypatch.setattr(settings, "current", settings.Settings())
    return saves


@pytest.fixture(scope="module")
def canvas():
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def test_save_and_load_round_trip(fresh):
    settings.current.brightness = 1.4
    settings.current.effects_volume = 0.2
    settings.current.fullscreen = True
    settings.current.bind("attack", 0, pygame.K_j)
    settings.save()
    settings.current = settings.Settings()
    s = settings.load()
    assert (s.brightness, s.effects_volume, s.fullscreen) == (1.4, 0.2, True)
    assert s.keys["attack"] == [pygame.K_j, pygame.K_f]


def test_missing_or_broken_file_gives_defaults(fresh):
    assert settings.load().keys == settings.DEFAULT_KEYS
    settings.settings_file().write_text("{not json", encoding="utf-8")
    assert settings.load().brightness == 1.0
    settings.settings_file().write_text(json.dumps({
        "brightness": 9, "effects_volume": "loud",
        "keys": {"up": [pygame.K_ESCAPE, None], "down": "s"}}), encoding="utf-8")
    s = settings.load()
    assert s.brightness == settings.BRIGHTNESS_RANGE[1]   # clamped
    assert s.effects_volume == settings.Settings().effects_volume
    assert s.keys["up"] == settings.DEFAULT_KEYS["up"]    # Esc is reserved
    assert s.keys["down"] == settings.DEFAULT_KEYS["down"]


def test_a_key_does_one_thing(fresh):
    settings.current.bind("inventory", 1, pygame.K_w)     # was move up
    assert settings.current.keys["up"] == [pygame.K_UP, None]
    assert settings.current.keys["inventory"] == [pygame.K_i, pygame.K_w]
    settings.current.bind("inventory", 0, None)
    assert settings.action_label("inventory") == "W"
    settings.current.reset_keys()
    assert settings.current.keys == settings.DEFAULT_KEYS


def test_dungeon_follows_the_bindings(fresh, canvas):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen, controls_hint
    from pygame_rpg.player import Player
    d = DungeonScreen(canvas, Player(name="Binder"), seed=1)
    assert d.handle_event(key(pygame.K_i))[0] == "inventory"
    settings.current.bind("inventory", 0, pygame.K_TAB)
    assert d.handle_event(key(pygame.K_i)) is None
    assert d.handle_event(key(pygame.K_TAB))[0] == "inventory"
    assert "Tab: inventory" in controls_hint()
    assert controls_hint().startswith("Arrows / WASD: move")
    settings.current.bind("up", 1, pygame.K_z)
    assert controls_hint().startswith("Up Left Down Right: move")


def test_settings_screen_keyboard(fresh, canvas):
    from pygame_rpg.gui.settings_screen import SettingsScreen
    back_to = object()
    s = SettingsScreen(canvas, return_to=back_to)
    s.handle_event(key(pygame.K_RIGHT))                  # brightness +10%
    assert settings.current.brightness == 1.1
    s.handle_event(key(pygame.K_DOWN))
    s.handle_event(key(pygame.K_DOWN))
    for _ in range(20):
        s.handle_event(key(pygame.K_LEFT))               # effects to 0
    assert settings.current.effects_volume == 0.0
    s.handle_event(key(pygame.K_DOWN))                   # fullscreen
    s.handle_event(key(pygame.K_RETURN))
    assert settings.current.fullscreen
    s.handle_event(key(pygame.K_DOWN))                   # Move up, slot 0
    s.handle_event(key(pygame.K_RETURN))
    assert s.listening == ("up", 0)
    s.draw(canvas)
    s.handle_event(key(pygame.K_m))                      # reserved
    assert settings.current.keys["up"][0] == pygame.K_UP and s.message
    s.handle_event(key(pygame.K_RETURN))
    s.handle_event(key(pygame.K_u))
    assert settings.current.keys["up"] == [pygame.K_u, pygame.K_w]
    s.handle_event(key(pygame.K_RIGHT))                  # slot 1, clear it
    s.handle_event(key(pygame.K_RETURN))
    s.handle_event(key(pygame.K_BACKSPACE))
    assert settings.current.keys["up"] == [pygame.K_u, None]
    s.draw(canvas)
    assert s.handle_event(key(pygame.K_ESCAPE)) == ("resume", {"screen": back_to})
    saved = json.loads(settings.settings_file().read_text(encoding="utf-8"))
    assert saved["keys"]["up"] == [pygame.K_u, None] and saved["fullscreen"]
    assert s.handle_event(pygame.event.Event(pygame.QUIT)) is QUIT


def test_settings_screen_mouse_drags_a_slider(fresh, canvas):
    from pygame_rpg.gui.settings_screen import SettingsScreen
    s = SettingsScreen(canvas)
    track = s.track(1)                                   # ambience volume
    s.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=(track.right, track.centery)))
    assert settings.current.ambience_volume == 1.0
    s.handle_event(pygame.event.Event(
        pygame.MOUSEMOTION, pos=(track.centerx, 0), rel=(0, 0), buttons=(1, 0, 0)))
    assert settings.current.ambience_volume == 0.5
    s.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONUP, button=1, pos=(track.centerx, 0)))
    r = s.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=s.btn_back.rect.center))
    assert r == "title"


def test_base_has_a_settings_button(fresh, canvas):
    from pygame_rpg.gui.base_screen import BaseScreen
    from pygame_rpg.player import Player
    b = BaseScreen(canvas, Player(name="Opts"))
    r = b.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=b.btn_settings.rect.center))
    assert r == ("settings", {"return_to": b})


def test_brightness_scales_the_picture(fresh):
    from pygame_rpg.gui.display import Display
    pygame.init()
    d = Display()
    d.canvas.fill((100, 100, 100))
    for level, expected in ((1.0, 100), (0.5, 50), (1.5, 150), (2.0, 200)):
        settings.current.brightness = level
        d.present()
        w, h = d.window.get_size()
        assert abs(d.window.get_at((w // 2, h // 2))[0] - expected) <= 2
