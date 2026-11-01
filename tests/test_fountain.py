"""The healing fountain room: placement, the two gifts, once per floor,
the choice screen (keys and taps) and the run save."""
import pygame
import pytest

from pygame_rpg import savegame as S
from pygame_rpg.enemies import boss_room, cell_of
from pygame_rpg.player import Player
from pygame_rpg.special_rooms import fountain_potion, fountain_heal


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()
    screen._FONTS.clear()


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def at_fountain(display, player, seed=5, floor=1):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    d = DungeonScreen(display, player, floor=floor, seed=seed)
    kx, ky = d.keepers["fountain"]
    d.x, d.y = d._centre((kx, ky + 1))
    return d


def hurt(player, share=0.2):
    player.current_hp = max(1, int(player.max_hp * share))
    return player


@pytest.mark.parametrize("seed", range(20))
def test_one_safe_fountain_per_floor(seed, display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    d = DungeonScreen(display, Player(name="Scout"), seed=seed)
    room = d.special["fountain"]
    assert room is not d.dungeon.rooms[0] and room is not boss_room(d.dungeon)
    assert room is not d.special["shop"] and room is not d.special["anvil"]
    assert not any(room.contains(cell_of(e)) for e in d.enemies)
    assert not any(room.contains(c) for c, _ in d.chests)
    assert not any(room.contains(p.cell) for p in d.props)


def test_potion_follows_the_floor_tier():
    assert fountain_potion(1).id == "potion"
    assert fountain_potion(2).id == "potion_2"
    assert fountain_potion(3).id == "potion_3"
    assert fountain_potion(4).id == fountain_potion(9).id == "potion_4"


def test_heal_is_half_of_max_hp_capped_at_full():
    p = Player(name="Medic")
    p.current_hp = 1
    assert fountain_heal(p) == p.max_hp // 2
    p.current_hp = p.max_hp - 3
    assert fountain_heal(p) == 3
    p.current_hp = p.max_hp
    assert fountain_heal(p) == 0


def test_drink_through_the_screen_then_dry(display, saves):
    from pygame_rpg.gui.fountain_screen import FountainScreen
    p = hurt(Player(name="Thirsty"))
    before = p.current_hp
    d = at_fountain(display, p)
    name, kw = d.handle_event(key(pygame.K_e))
    assert name == "fountain" and kw["return_to"] is d
    f = FountainScreen(display, p, d)
    f.draw(display)
    f.handle_event(key(pygame.K_DOWN))        # focus "Fill a flask"
    f.handle_event(key(pygame.K_DOWN))        # focus "Drink"
    out = f.handle_event(key(pygame.K_RETURN))
    assert out == ("resume", {"screen": d})
    assert p.current_hp == before + p.max_hp // 2
    assert d.fountain_used
    # Once per floor: E now only says it is dry, and no second gift.
    assert d.handle_event(key(pygame.K_e)) is None
    assert d.use_fountain("potion") == ""
    d.draw(display)                           # the dry frame draws


def test_fill_a_flask_by_tap(display, saves):
    from pygame_rpg.gui.fountain_screen import FountainScreen
    p = Player(name="Flask")
    d = at_fountain(display, p, floor=3)
    f = FountainScreen(display, p, d)
    tap = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                             pos=f.buttons["potion"].rect.center)
    n = len(p.inventory)
    assert f.handle_event(tap) == ("resume", {"screen": d})
    assert len(p.inventory) == n + 1 and p.inventory[-1].id == "potion_3"
    assert d.fountain_used


def test_full_hp_cannot_drink_and_leave_keeps_it(display, saves):
    from pygame_rpg.gui.fountain_screen import FountainScreen
    p = Player(name="Healthy")
    d = at_fountain(display, p)
    f = FountainScreen(display, p, d)
    assert not f.enabled["heal"]
    tap = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                             pos=f.buttons["heal"].rect.center)
    assert f.handle_event(tap) is None and not d.fountain_used
    assert f.handle_event(key(pygame.K_ESCAPE)) == ("resume", {"screen": d})
    assert not d.fountain_used


def test_used_fountain_is_saved(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = hurt(Player(name="Saver"))
    S.save_player(p)
    d = at_fountain(display, p, seed=11)
    assert d.use_fountain("heal")
    run = S.load_run(p.name)
    assert run["fountain_used"] is True
    again = DungeonScreen(display, p, run=run)
    assert again.fountain_used


def test_full_map_marks_the_fountain(display, saves):
    from pygame_rpg.gui.map_screen import MapScreen
    d = at_fountain(display, Player(name="Mapper"))
    d.visited.append(d.special["fountain"])
    MapScreen(display, d).draw(display)
