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
    screen._FONTS.clear()       # don't leave dead fonts for the next module


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


def test_walk_frames_follow_the_distance(display, saves, monkeypatch):
    """The walk cycle advances with the pixels walked, and a footstep
    (sound + splash) lands twice per stride."""
    from pygame_rpg import audio
    from pygame_rpg.assets import HERO_WALK_COLS
    from pygame_rpg.gui import dungeon_screen as D
    steps = []
    monkeypatch.setattr(audio, "play", lambda name, delay=0.0, volume=1.0: steps.append(name))
    p = Player(name="Walker")
    d = D.DungeonScreen(display, p, seed=3)
    seen_frames = set()
    walked = 0.0
    for _ in range(400):
        x, y = d.x, d.y
        d.move(1, 0, 1 / 60) if d._fits(d.x + 3, d.y) else d.move(-1, 0, 1 / 60)
        walked += abs(d.x - x) + abs(d.y - y)
        seen_frames.add(d.walk_frame())
        d.draw(display)
    assert seen_frames == set(range(len(HERO_WALK_COLS)))
    assert abs(steps.count("step") - walked / D.STRIDE) <= 2
    d.move(0, 0, 1 / 60)
    assert not d.moving


def test_gear_shows_on_the_hero(display, saves):
    from pygame_rpg import items as I
    from pygame_rpg.assets import gear_of, NO_GEAR
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = Player(name="Knight")
    assert gear_of(p.equipment) == NO_GEAR
    for item_id in ("mace_2", "iron_helmet", "leather_vest", "iron_gauntlets", "leather_boots"):
        item = I.item_by_id(item_id)
        p.inventory.append(item)
        p.lvl = 4
        p.equip(item)
    assert gear_of(p.equipment) == ("blunt", "stun", "iron", "leather", "iron", "leather")
    wand = I.item_by_id("electric_wand")
    p.inventory.append(wand)
    p.equip(wand)
    assert gear_of(p.equipment)[:2] == ("magic", "electrocuted")
    a = AssetManager()
    bare, geared = a.hero_frames(p.look), a.hero_frames(p.look, gear_of(p.equipment))
    assert bare is not geared
    assert any(pygame.image.tobytes(b, "RGBA") != pygame.image.tobytes(g, "RGBA")
               for b, g in zip(bare, geared))
    # The dungeon picks up a gear change without being rebuilt.
    d = DungeonScreen(display, p, seed=1)
    before = d.hero_frames()
    p.unequip("head")
    assert d.hero_frames() is not before
    d.draw(display)
