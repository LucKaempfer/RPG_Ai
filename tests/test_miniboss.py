"""Minibosses: one guarded room per floor, tied into the story."""
from types import SimpleNamespace

import pygame
import pytest

from pygame_rpg import lore, miniboss as M, savegame as S
from pygame_rpg import enemies as E
from pygame_rpg.combat import Battle, WON
from pygame_rpg.dungeon import Dungeon
from pygame_rpg.player import Player


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()
    screen._FONTS.clear()


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")


def _floor(player, floor=1, seed=3):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    return DungeonScreen(pygame.display.get_surface(), player, floor=floor, seed=seed)


def test_every_story_floor_has_its_own_miniboss_and_deeper_floors_a_warden():
    names = {M.miniboss_type(f).name for f in range(1, lore.LORE_FLOORS + 1)}
    assert len(names) == lore.LORE_FLOORS
    deep = M.miniboss_type(lore.LORE_FLOORS + 3)
    assert deep.name == "Deep Warden" and deep.intro
    from pygame_rpg.assets import ENEMY_NAMES
    for f in range(1, 12):
        assert M.miniboss_type(f).sprite in ENEMY_NAMES


def test_miniboss_is_tougher_than_a_foe_and_softer_than_the_boss():
    for f in (1, 3, 5, 8):
        mini = E.make_enemy(M.miniboss_type(f), f)
        boss = E.make_enemy(E.BOSS_TYPE, f, boss=True)
        foes = [E.make_enemy(t, f) for t in E.ENEMY_TYPES.values()]
        assert mini.max_hp > max(e.max_hp for e in foes)
        assert mini.xp < boss.xp * 1.0 and mini.xp > max(e.xp for e in foes)


@pytest.mark.parametrize("seed", range(25))
def test_room_is_seeded_and_never_entrance_lair_or_special(display, saves, seed):
    ds = _floor(Player(name="Mapper"), seed=seed)
    room = ds.miniboss_room
    assert room is not None and ds.miniboss in ds.enemies
    assert room is not ds.dungeon.rooms[0]
    assert room is not E.boss_room(ds.dungeon)
    assert room not in ds.special.values()
    assert room.contains(E.cell_of(ds.miniboss))
    cell = E.cell_of(ds.miniboss)
    others = {E.cell_of(e) for e in ds.enemies if e is not ds.miniboss}
    assert cell not in others and cell not in {c for c, _ in ds.chests}
    assert cell not in {c for _, c in ds.lore} and cell not in ds.prop_at
    again = _floor(Player(name="Mapper"), seed=seed)
    assert again.miniboss_room.id == room.id
    assert E.cell_of(again.miniboss) == cell


def test_adding_the_miniboss_moves_nothing_else(display, saves):
    """Old runs still load: enemies, chests and writings stay put and the
    miniboss is the last enemy of the floor."""
    ds = _floor(Player(name="Same"), seed=11)
    d = Dungeon()
    d.generate(11)
    plain = [(e.name, e.x, e.y) for e in E.place_enemies(d, 1)]
    mine = [(e.name, e.x, e.y) for e in ds.all_enemies[:-1]]
    safe = list(ds.special.values())
    assert mine == [p for p in plain
                    if not any(r.contains((int(p[1] // 32), int(p[2] // 32)))
                               for r in safe)]
    assert ds.all_enemies[-1] is ds.miniboss


def test_old_save_without_the_miniboss_still_loads(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = Player(name="Oldie")
    ds = _floor(p, seed=5)
    run = ds.to_run()
    run["beaten"] = [0]
    back = DungeonScreen(display, p, run=run)
    assert back.miniboss.alive and not back.all_enemies[0].alive
    back.miniboss.hp = 0
    again = DungeonScreen(display, p, run=back.to_run())
    assert not again.miniboss.alive and again.miniboss not in again.enemies


def test_battle_opens_with_its_line_drops_loot_and_can_be_fled():
    class Rng:
        def uniform(self, a, b): return a
        def randint(self, a, b): return a
        def random(self): return 0.0
        def choice(self, seq): return seq[0]
    p = Player(name="Brave")
    mini = E.make_enemy(M.miniboss_type(2), 2)
    mini.miniboss = True
    b = Battle(p, mini, Rng())
    assert b.log[0] == M.miniboss_type(2).intro
    assert b.run_chance() > 0                      # only the boss holds you


def test_beating_it_files_its_writing_and_tells_it_once(display, saves):
    p = Player(name="Slayer")
    ds = _floor(p, floor=3, seed=7)
    ds.lore.clear()
    mini = ds.miniboss
    mini.hp = 0
    battle = SimpleNamespace(state=WON, enemies=[mini], xp_gained=0,
                             gold_gained=0, loot=[], blueprint=None)
    ds.battle_over(battle)
    ds.check_levels = False
    entry = lore.MINIBOSS_LORE[3]
    name, kw = ds.step(0, 0, 0.016)
    assert name == "story" and kw["title"] == entry.title
    assert kw["return_to"] is ds
    assert entry.id in S.load_player("Slayer").lore
    assert ds.step(0, 0, 0.016) is None
    again = _floor(p, floor=3, seed=8)
    again.miniboss.hp = 0
    again.battle_over(SimpleNamespace(state=WON, enemies=[again.miniboss],
                                      xp_gained=0, gold_gained=0, loot=[],
                                      blueprint=None))
    assert again.story is None                     # found once per hero


def test_deep_floor_miniboss_leaves_no_writing(display, saves):
    p = Player(name="Deep")
    ds = _floor(p, floor=7, seed=2)
    ds.miniboss.hp = 0
    ds.battle_over(SimpleNamespace(state=WON, enemies=[ds.miniboss], xp_gained=0,
                                   gold_gained=0, loot=[], blueprint=None))
    assert ds.story is None


def test_map_marks_the_room_until_it_falls(display, saves):
    from pygame_rpg.gui.map_screen import MapScreen
    p = Player(name="Cartographer")
    ds = _floor(p, seed=4)
    ds.visited.append(ds.miniboss_room)
    m = MapScreen(display, ds)
    assert m._miniboss_marked()
    m.draw(display)
    ds.miniboss.hp = 0
    assert not m._miniboss_marked()


def test_floor_draws_with_the_miniboss_in_sight(display, saves):
    ds = _floor(Player(name="Looker"), seed=6)
    ds.x, ds.y = ds._centre(ds.miniboss_room.rect.center)
    ds.visible.add(E.cell_of(ds.miniboss))
    ds.draw(display)


def test_journal_scrolls_to_every_row(display, saves):
    from pygame_rpg.gui.journal_screen import JournalScreen, VISIBLE_ROWS
    p = Player(name="Scroller")
    p.lore = [lore.MINIBOSS_LORE[5].id, "epilogue"]
    j = JournalScreen(display, p)
    assert len(j.rows) > VISIBLE_ROWS
    for _ in range(len(j.rows) - 1):
        j.handle_event(key(pygame.K_DOWN))
        assert j.scroll <= j.focus < j.scroll + VISIBLE_ROWS
        j.draw(display)
    assert j.focus == len(j.rows) - 1
    assert j.open(j.focus)[1]["title"] == lore.EPILOGUE_TITLE
    hobb = [r[2] for r in j.rows].index(lore.MINIBOSS_LORE[5].title)
    assert "miniboss" in j.rows[hobb][0] and j.open(hobb) is not None
    j.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=50))
    assert j.scroll == 0 and j.focus < VISIBLE_ROWS
