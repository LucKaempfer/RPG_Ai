"""Blueprints, the anvil room, crafting and upgrading weapons."""
import random

import pygame
import pytest

from pygame_rpg import combat as C, crafting as K, enemies as E, items as I, savegame as S
from pygame_rpg.player import Player


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()
    screen._FONTS.clear()       # don't leave dead fonts for the next module


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def rich(**kw):
    p = Player(name="Smith", gold=500, **kw)
    p.materials.update({m: 50 for m in p.materials})
    return p


def test_families_and_base_ids():
    assert K.family(I.item_by_id("sword")) == "blade"
    assert K.family(I.item_by_id("mace_3")) == "blunt"
    assert K.family(I.item_by_id("bow")) == "ranged"
    assert K.family(I.item_by_id("fiery_wand_2")) == "magic"
    assert K.family(I.item_by_id("dagger")) == "blade"
    assert K.base_id(I.item_by_id("poisonous_staff_3")) == "poisonous_staff"
    assert K.base_id(I.item_by_id("sword")) == "sword"


def test_new_heroes_know_the_sword_and_blueprints_save(saves):
    p = Player(name="Learner")
    assert p.blueprints == ["sword"]
    p.blueprints.append("bow")
    S.save_player(p)
    assert S.load_player("Learner").blueprints == ["sword", "bow"]
    data = p.to_dict()
    data.pop("blueprints")
    assert Player.from_dict(data, S._resolve).blueprints == ["sword"]
    data["blueprints"] = ["bow", "not_a_weapon"]
    assert Player.from_dict(data, S._resolve).blueprints == ["bow"]


def test_crafting_needs_the_blueprint_materials_and_gold():
    p = Player(name="Poor")
    ok, why = K.can_craft(p, "bow")
    assert not ok and "blueprint" in why
    ok, why = K.can_craft(p, "sword")
    assert not ok and "iron" in why and "gold" in why
    p = rich()
    mats, gold = K.craft_cost("sword")
    assert K.craft(p, "sword") == "Crafted Sword!"
    assert p.inventory[-1].id == "sword" and p.gold == 500 - gold
    assert all(p.materials[m] == 50 - n for m, n in mats.items())


def test_upgrading_in_place_keeps_it_equipped():
    p = rich(lvl=4)
    sword = I.item_by_id("sword")
    p.inventory.append(sword)
    p.equip(sword)
    for level in (2, 3, 4):
        msg, better = K.upgrade(p, p.equipment["weapon"])
        assert better.id == f"sword_{level}" and p.equipment["weapon"] is better
    assert not K.can_upgrade(p, p.equipment["weapon"])[0]          # max level
    assert K.upgradeable(p) == []
    bow = I.item_by_id("bow")
    p.inventory.append(bow)
    assert "blueprint" in K.can_upgrade(p, bow)[1]
    p.blueprints.append("bow")
    msg, better = K.upgrade(p, bow)
    assert better.id == "bow_2" and better in p.inventory and bow not in p.inventory


def test_upgrade_needs_the_hero_level():
    p = rich(lvl=1)
    sword = I.item_by_id("sword")
    p.inventory.append(sword)
    ok, why = K.can_upgrade(p, sword)
    assert not ok and why == "Requires level 2."


def test_upgrade_costs_grow_with_the_level():
    m2, g2 = K.upgrade_cost(I.item_by_id("bow"))
    m4, g4 = K.upgrade_cost(I.item_by_id("bow_3"))
    assert m4["wood"] == 2 * m2["wood"] and g4 == 2 * g2


def test_the_boss_always_drops_a_new_blueprint():
    p = Player(name="Slayer")
    boss = E.make_enemy(E.BOSS_TYPE, 1, boss=True)
    boss.hp = 1
    b = C.Battle(p, boss, random.Random(3))
    b.attack()
    assert b.state == C.WON and b.blueprint and b.blueprint != "sword"
    assert b.blueprint in p.blueprints
    p.blueprints = list(K.BLUEPRINTS)                 # knows them all
    assert K.roll_blueprint(random.Random(1), p.blueprints) is None


@pytest.mark.parametrize("seed", range(10))
def test_one_anvil_room_per_floor(seed, display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    from pygame_rpg.enemies import cell_of
    d = DungeonScreen(display, Player(name="Scout"), seed=seed)
    anvil, shop = d.special["anvil"], d.special["shop"]
    assert anvil is not shop
    assert not any(anvil.contains(cell_of(e)) for e in d.enemies)
    assert not any(anvil.contains(p.cell) for p in d.props)


def test_forging_through_the_screens(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    from pygame_rpg.gui.forge_screen import ForgeScreen
    p = rich(lvl=2)
    p.blueprints.append("bow")
    sword = I.item_by_id("sword")
    p.inventory.append(sword)
    p.equip(sword)
    d = DungeonScreen(display, p, seed=5)
    kx, ky = d.keepers["anvil"]
    d.x, d.y = d._centre((kx, ky + 1))
    name, kw = d.handle_event(key(pygame.K_e))
    assert name == "forge" and kw["return_to"] is d
    f = ForgeScreen(display, p, return_to=d)
    assert f.rows() == ["sword", "bow"]                # sorted by family
    f.handle_event(key(pygame.K_DOWN))
    f.handle_event(key(pygame.K_RETURN))               # craft the bow
    assert any(i.id == "bow" for i in p.inventory)
    f.handle_event(key(pygame.K_RIGHT))                # Upgrade tab: equipped sword first
    f.draw(display)
    f.handle_event(key(pygame.K_RETURN))
    assert p.equipment["weapon"].id == "sword_2"
    assert f.handle_event(key(pygame.K_ESCAPE)) == ("resume", {"screen": d})
    assert S.load_player("Smith").equipment["weapon"].id == "sword_2"


def test_armour_blueprints_craft_and_upgrade():
    assert {"leather_cap", "chainmail", "iron_boots"} <= set(K.BLUEPRINTS)
    assert K.family(I.item_by_id("leather_vest_2")) == "leather"
    assert K.family(I.item_by_id("iron_helmet")) == "iron"
    # A torso piece weighs 2, so it costs twice a helmet's materials.
    cap, _ = K.craft_cost("iron_helmet")
    mail, _ = K.craft_cost("chainmail")
    assert mail == {m: 2 * n for m, n in cap.items()}
    up, gold = K.upgrade_cost(I.item_by_id("chainmail_2"))
    assert up == {m: 3 * n for m, n in mail.items()} and gold == 3 * K.UPGRADE_GOLD
    p = rich(lvl=3)
    assert "blueprint" in K.can_craft(p, "chainmail")[1]
    p.blueprints.append("chainmail")
    assert K.craft(p, "chainmail") == "Crafted Chain Mail!"
    mail = p.inventory[-1]
    p.equip(mail)
    assert K.upgradeable(p) == [mail]
    msg, better = K.upgrade(p, mail)
    assert better.id == "chainmail_2" and p.equipment["torso"] is better
    assert p.max_hp == p.hp + better.hp


def test_forge_lists_armour(display, saves):
    from pygame_rpg.gui.forge_screen import ForgeScreen
    p = rich(lvl=2)
    p.blueprints += ["leather_boots", "bow"]
    boots = I.item_by_id("leather_boots")
    p.inventory.append(boots)
    p.equip(boots)
    f = ForgeScreen(display, p)
    assert f.rows() == ["sword", "bow", "leather_boots"]     # weapons first
    f.tab = 1
    assert f.rows() == [boots]
    f.draw(display)
    f.handle_event(key(pygame.K_RETURN))
    assert p.equipment["feet"].id == "leather_boots_2"
