"""Audio: the synthesised sounds build, and screens ask for the right ones."""
import math
import random

import pygame
import pytest

from pygame_rpg import audio, combat as C
from pygame_rpg.player import Player


@pytest.fixture(scope="module")
def display():
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()


@pytest.fixture
def played(monkeypatch):
    """Record audio.play names instead of playing them."""
    names = []
    monkeypatch.setattr(audio, "play",
                        lambda name, delay=0.0, volume=1.0: names.append(name))
    return names


@pytest.mark.parametrize("name", sorted(audio._RECIPES))
def test_recipes_are_finite_and_short(name):
    buf = audio._RECIPES[name](audio._Synth(8000))
    assert buf and all(math.isfinite(x) for x in buf)
    assert max(abs(x) for x in buf) > 0.01         # not silent
    assert len(buf) / 8000 <= (9 if name == "sewer" else 3)


def test_every_play_name_has_a_sound():
    names = set(audio._RECIPES)
    wanted = {"step", "door", "chest", "encounter", "stairs", "level_up",
              "miss", "hurt", "magic", "heal", "guard", "potion", "bomb",
              "ailment", "run", "fail", "victory", "defeat", "click",
              *C.STYLES}
    for want in wanted:
        assert want in names or f"{want}0" in names, want
    for name, _ in audio._SCATTER["sewer"]:
        assert name in names or f"{name}0" in names


def test_audio_runs_on_the_dummy_driver(display):
    a = audio.Audio()
    a.init(background=False)
    if not a.ok:
        pytest.skip("no mixer on this machine")
    assert {"sewer", "strike", "drip0"} <= set(a.sounds)
    a.play("step")
    a.play("hurt", delay=0.1)
    a.set_ambience("sewer")
    for _ in range(30):
        a.update(0.1)
    assert not a.pending
    a.toggle_mute()
    a.play("door")
    assert a.muted
    a.toggle_mute()
    a.set_ambience(None)


def test_battle_sounds(display, saves, played):
    from pygame_rpg.gui.battle_screen import BattleScreen
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = Player(name="Loud")
    ds = DungeonScreen(display, p, seed=2)
    foes = [e for e in ds.enemies if not e.boss]
    bs = BattleScreen(display, p, foes[0], ds, rng=random.Random(0))
    assert bs.ambience == "sewer"
    bs._do(("mode", "attack"))
    assert played[-1] == "click"
    foes[0].hp = foes[0].max_hp = 999
    played.clear()
    bs.battle.rng = random.Random(1)
    bs._do(("attack", "bash"))
    assert played[0] in ("bash", "ailment") and "hurt" in played
    foes[0].hp = 1
    played.clear()
    bs.battle.statuses.clear()
    bs._do(("attack", "slash"))
    assert played == ["slash", "victory"]


def test_dungeon_sounds(display, saves, played):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = Player(name="Walk")
    ds = DungeonScreen(display, p, seed=4)
    assert ds.ambience == "sewer"
    ds.enemies = []
    # Walk from just outside a door onto it.
    door = next(iter(ds.dungeon.door_tiles))
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        start = (door[0] - dx, door[1] - dy)
        ds.x, ds.y = ds._centre(start)
        if ds._fits(ds.x, ds.y) and ds._fits(*ds._centre(door)):
            break
    for _ in range(12):            # ~2 tiles: onto the door and past it
        ds.move(dx, dy, 1 / 30)
    assert "door" in played and "step" in played
    ds.x, ds.y = ds._centre(ds.chests[0][0])
    ds.step(0, 0, 1 / 60)
    assert played[-1] == "chest"
