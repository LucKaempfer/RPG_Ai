"""Character customization: the look stage of the hero maker, the
look in saves, and hero frames drawn per look."""
import pygame
import pytest

from pygame_rpg import savegame as S
from pygame_rpg.assets import (
    AssetManager, LOOK_OPTIONS, HERO_COLS, HERO_ROWS, look_choice,
)
from pygame_rpg.player import Player, LOOK_KEYS


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()       # fonts cached before another module's pygame.quit()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def test_look_keys_match_the_options():
    assert set(LOOK_KEYS) == set(LOOK_OPTIONS)
    assert Player().look == {k: 0 for k in LOOK_KEYS}
    assert look_choice({"hair": len(LOOK_OPTIONS["hair"])}, "hair") == LOOK_OPTIONS["hair"][0]


def test_look_round_trips_and_old_saves_get_the_default(saves):
    p = Player(name="Looks", look={"skin": 2, "hair": 4, "hair_color": 1, "tunic": 5})
    S.save_player(p)
    assert S.load_player("Looks").look == p.look
    data = p.to_dict()
    data.pop("look")
    data["name"] = "Plain"
    q = Player.from_dict(data, S._resolve)
    assert q.look == {k: 0 for k in LOOK_KEYS}
    data["look"] = {"skin": "x", "nonsense": 3, "tunic": 2}
    assert Player.from_dict(data, S._resolve).look["tunic"] == 2


def test_each_look_draws_its_own_frames(display):
    a = AssetManager()
    plain = a.hero_frames({k: 0 for k in LOOK_KEYS})
    red = a.hero_frames({"skin": 0, "hair": 0, "hair_color": 0, "tunic": 1})
    assert len(plain) == HERO_COLS * HERO_ROWS
    assert a.hero_frames({k: 0 for k in LOOK_KEYS}) is plain       # cached
    centre = (16, 18)
    assert plain[0].get_at(centre) != red[0].get_at(centre)
    for style in range(len(LOOK_OPTIONS["hair"])):
        assert a.hero_frames({"hair": style})                       # every style draws


def test_hero_maker_look_stage(display, saves):
    from pygame_rpg.gui.hero_maker import HeroMakerScreen
    h = HeroMakerScreen(display)
    h.text = "Mira"
    assert h.handle_event(key(pygame.K_RETURN)) is None
    assert h.stage == "look"
    h.handle_event(key(pygame.K_RIGHT))                 # skin 0 -> 1
    h.handle_event(key(pygame.K_DOWN))
    h.handle_event(key(pygame.K_LEFT))                  # hair wraps to the last
    assert h.look["skin"] == 1
    assert h.look["hair"] == len(LOOK_OPTIONS["hair"]) - 1
    h.handle_update(0.5)
    h.draw(display)
    h.handle_event(key(pygame.K_r))                     # random stays in range
    assert all(0 <= h.look[k] < len(LOOK_OPTIONS[k]) for k in LOOK_KEYS)
    chosen = dict(h.look)
    h.handle_event(key(pygame.K_ESCAPE))
    assert h.stage == "input"
    h.handle_event(key(pygame.K_RETURN))
    h.handle_event(key(pygame.K_RETURN))
    assert h.stage == "confirm"
    h.draw(display)
    name, kwargs = h.handle_event(key(pygame.K_RETURN))
    assert name == "base" and kwargs["player"].look == chosen
    assert S.load_player("Mira").look == chosen
