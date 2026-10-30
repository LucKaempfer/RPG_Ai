"""Money and junk: drops from mobs and smashed props, saved gold."""
import random

import pygame
import pytest

from pygame_rpg import combat as C, enemies as E, items as I, savegame as S
from pygame_rpg.config import ENEMY_GOLD, BOSS_GOLD_MULT
from pygame_rpg.player import Player


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()


def _win(enemy, seed, player=None):
    p = player or Player(name="Rich")
    enemy.hp = 1
    b = C.Battle(p, enemy, random.Random(seed))
    b.attack()
    assert b.state == C.WON
    return p, b


def test_every_win_pays_gold_scaled_by_floor():
    lo, hi = ENEMY_GOLD
    for floor in (1, 3):
        p, b = _win(E.make_enemy(E.ENEMY_TYPES["rat"], floor), seed=floor)
        assert lo * floor <= b.gold_gained <= hi * floor and p.gold == b.gold_gained
    p, b = _win(E.make_enemy(E.BOSS_TYPE, 2, boss=True), seed=4)
    assert b.gold_gained >= lo * 2 * BOSS_GOLD_MULT


def test_mobs_sometimes_drop_junk_for_their_floor():
    junk = []
    for sd in range(80):
        _, b = _win(E.make_enemy(E.ENEMY_TYPES["rat"], 1), seed=sd)
        junk += [i for i in b.loot if i.kind == "junk"]
    assert 5 < len(junk) < 40
    assert all(j.level == 1 and j.value > 0 for j in junk)


def test_loot_rolls_never_give_junk():
    rng = random.Random(1)
    assert all(I.roll_loot(rng).kind != "junk" for _ in range(300))
    assert {I.roll_junk(rng, 4).id for _ in range(300)} == {j.id for j in I.JUNK}


def test_gold_and_junk_are_saved(saves):
    p = Player(name="Saver", gold=57)
    p.inventory.append(I.item_by_id("silver_goblet"))
    S.save_player(p)
    q = S.load_player("Saver")
    assert q.gold == 57 and q.inventory[-1].value == 20
    data = p.to_dict()
    data.pop("gold")
    assert Player.from_dict(data, S._resolve).gold == 0


def test_smashed_props_can_hold_coins_and_junk(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = Player(name="Looter")
    gold = junk = 0
    for seed in range(12):
        d = DungeonScreen(display, p, seed=seed)
        for prop in d.props:
            before = (p.gold, len(p.inventory))
            while not prop.broken:
                d._hit_prop(prop)
            gold += p.gold > before[0]
            junk += len(p.inventory) > before[1]
        d.draw(display)
    assert gold > 10 and junk > 3
    assert all(i.kind == "junk" for i in p.inventory)
