"""Combat rules (``combat.py``): damage, ailments, cooldowns, outcomes."""
import random

import pytest

from pygame_rpg import combat as C, enemies as E, items as I
from pygame_rpg.player import Player


def hero(*ids, lvl=1):
    p = Player(name="T", lvl=lvl)
    for i in ids:
        item = I.item_by_id(i)
        p.inventory.append(item)
        if item.slot:
            p.equip(item)
    return p


def tough(kind="slime", floor=1):
    e = E.make_enemy(E.ENEMY_TYPES[kind], floor)
    e.hp = e.max_hp = 999
    return e


class FixedRng(random.Random):
    """No variance, and every percentage roll comes out as ``roll``."""
    def __init__(self, roll=99.9):
        super().__init__(0)
        self.roll = roll

    def uniform(self, a, b):
        return 1.0 if (a, b) == (0.85, 1.15) else self.roll


def test_hero_damage_formula():
    p, e = hero("sword"), tough()
    C.Battle(p, e, FixedRng()).attack()
    # (ap incl. the sword's +1, plus sword power 4 + 2*1) - slime defense
    assert e.max_hp - e.hp == p.total("ap") + 6 - e.defense == 10


def test_enemy_damage_formula_and_guard():
    p, e = hero("sword", "shield"), tough()
    b = C.Battle(p, e, FixedRng())
    b.attack()
    assert p.max_hp - p.current_hp == 2 * e.attack - p.total("dp")
    hp = p.current_hp
    b.cast(p.equipment["ability1"])
    assert hp - p.current_hp == max(1, 2 * e.attack - p.total("dp") - b.guard)


@pytest.mark.parametrize("weapon,stat", [(None, "ap"), ("bow", "rap"),
                                         ("fiery_wand", "map"), ("dagger", "ap")])
def test_weapon_type_picks_the_stat(weapon, stat):
    w = I.item_by_id(weapon) if weapon else None
    assert C.STAT_FOR[C.weapon_type(w)] == stat


def test_ailment_ticks_then_expires():
    p, e = hero("sword"), tough()
    b = C.Battle(p, e, FixedRng())
    e.statuses["poison"] = 2
    b.attack()
    b.attack()
    assert "poison" not in e.statuses
    assert e.max_hp - e.hp == 2 * 10 + 2 * C.AILMENTS["poison"].dot


def test_stun_skips_enemy_turn():
    p, e = hero("sword"), tough()
    e.statuses["stun"] = 1
    C.Battle(p, e, FixedRng()).attack()
    assert p.current_hp == p.max_hp


def test_full_ward_blocks_ailment():
    p = hero("sword", "poison_ward_4", lvl=4)
    b = C.Battle(p, tough(), FixedRng(roll=0.0))   # every roll succeeds
    b.attack()
    assert "poison" not in b.statuses


def test_cooldown():
    p, e = hero("fireball"), tough()
    b = C.Battle(p, e, FixedRng())
    fb = p.equipment["ability1"]
    b.cast(fb)
    assert not b.can_cast(fb)
    b.attack()
    assert b.can_cast(fb)


def test_win_gives_xp_recovery_and_boss_loot():
    p = hero("sword")
    p.current_hp = 50
    boss = E.make_enemy(E.BOSS_TYPE, 1, boss=True)
    boss.hp = 1
    b = C.Battle(p, boss, random.Random(1))
    b.attack()
    assert b.state == C.WON and p.xp == boss.xp
    assert p.current_hp == 50 + p.max_hp * C.WIN_HEAL_PCT // 100
    assert len(b.loot) == 1 and b.loot[0] in p.inventory


def test_no_running_from_the_boss():
    b = C.Battle(hero(), E.make_enemy(E.BOSS_TYPE, 1, boss=True), FixedRng(0.0))
    b.run()
    assert b.state == C.ONGOING


def test_defeat():
    p, e = hero(), tough()
    p.current_hp = 1
    C.Battle(p, e, FixedRng()).attack()
    assert p.current_hp == 0
