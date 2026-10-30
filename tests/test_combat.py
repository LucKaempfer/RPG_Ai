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


@pytest.mark.parametrize("style", list(C.STYLES))
def test_preview_matches_the_hit(style):
    p, e = hero("sword"), tough()
    b = C.Battle(p, e, FixedRng())            # no variance, never misses
    lo, hi = b.attack_preview(style)
    assert lo <= hi
    b.attack(style)
    assert lo <= e.max_hp - e.hp <= hi


def test_styles_trade_damage_for_ailments():
    dmg = {}
    for style in C.STYLES:
        p, e = hero("sword"), tough()
        C.Battle(p, e, FixedRng()).attack(style)
        dmg[style] = e.max_hp - e.hp
    assert dmg["slash"] < dmg["strike"] < dmg["heavy"]
    assert dmg["bash"] < dmg["strike"]
    p, e = hero("sword"), tough()
    C.Battle(p, e, FixedRng(roll=50.0)).attack("slash")     # 25 + 30 > 50
    assert "bleeding" in e.statuses
    p, e = hero("sword"), tough()
    C.Battle(p, e, FixedRng(roll=50.0)).attack("strike")    # 25 < 50
    assert not e.statuses


def test_heavy_can_miss():
    p, e = hero("sword"), tough()
    C.Battle(p, e, FixedRng(roll=0.0)).attack("heavy")
    assert e.hp == e.max_hp


def test_incoming_preview_and_cast_preview():
    p, e = hero("sword", "fireball", "shield"), tough()
    b = C.Battle(p, e, FixedRng())
    lo, hi = b.incoming_preview()
    b.attack()
    assert lo <= p.max_hp - p.current_hp <= hi
    fb, sh = p.equipment["ability1"], p.equipment["ability2"]
    assert b.cast_preview(sh) is None
    lo, hi = b.cast_preview(fb)
    hp = e.hp
    b.cast(fb)
    assert lo <= hp - e.hp <= hi              # roll 99.9: no burning tick


# -- fights against several enemies -------------------------------------------

def group(*kinds, hp=999):
    foes = [E.make_enemy(E.ENEMY_TYPES[k], 1) for k in kinds]
    for f in foes:
        f.hp = f.max_hp = hp
    return foes


def test_group_gets_letters_and_one_intro_line():
    b = C.Battle(hero("sword"), group("slime", "slime", "bat"), FixedRng())
    assert [b.name_of(e) for e in b.enemies] == ["Slime A", "Slime B", "Bat"]
    assert b.log == ["Slime A, Slime B and Bat attack!"]


def test_attack_hits_only_the_target_and_everyone_hits_back():
    p = hero("sword")
    foes = group("slime", "bat")
    b = C.Battle(p, foes, FixedRng())
    assert b.set_target(1) and b.enemy is foes[1]
    b.attack()
    assert foes[0].hp == foes[0].max_hp and foes[1].hp < foes[1].max_hp
    taken = sum(max(1, 2 * f.attack - p.total("dp")) for f in foes)
    assert p.max_hp - p.current_hp == taken
    lo, hi = b.incoming_preview()               # both hits, summed
    assert lo == sum(max(1, round(2 * f.attack * 0.85) - p.total("dp")) for f in foes)
    assert hi == sum(max(1, round(2 * f.attack * 1.15) - p.total("dp")) for f in foes)


def test_target_moves_on_when_it_falls_and_win_needs_everyone():
    p = hero("sword")
    foes = group("slime", "bat", hp=1)
    foes[1].hp = foes[1].max_hp = 999
    b = C.Battle(p, foes, FixedRng())
    b.attack()                                   # the slime falls
    assert not foes[0].alive and b.state == C.ONGOING
    assert b.enemy is foes[1] and "The Slime falls!" in b.log
    assert not b.set_target(0)                   # can't aim at the fallen
    foes[1].hp = 1
    b.attack()
    assert b.state == C.WON
    assert b.xp_gained == foes[0].xp + foes[1].xp


def test_cycle_target_skips_the_fallen():
    foes = group("slime", "rat", "bat")
    b = C.Battle(hero(), foes, FixedRng())
    foes[1].hp = 0
    b.cycle_target(1)
    assert b.enemy is foes[2]
    b.cycle_target(1)
    assert b.enemy is foes[0]
    b.cycle_target(-1)
    assert b.enemy is foes[2]


def test_group_gold_adds_up_and_no_running_from_a_boss_group():
    p = hero("sword")
    foes = group("slime", "bat", hp=1)
    b = C.Battle(p, foes, random.Random(3))
    while b.state == C.ONGOING:
        for f in foes:
            f.hp = min(f.hp, 1)
        b.attack()
    assert b.state == C.WON and p.gold == b.gold_gained > 0
    boss = E.make_enemy(E.BOSS_TYPE, 1, boss=True)
    b = C.Battle(hero(), [boss] + group("rat"), FixedRng(0.0))
    assert b.run() == ["You can't run from this fight!"]
