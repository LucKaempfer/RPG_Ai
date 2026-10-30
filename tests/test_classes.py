"""Hero classes: stats, kits, saves and the hero maker's class stage."""
import pygame
import pytest

from pygame_rpg import savegame as S
from pygame_rpg.classes import CLASSES, CLASS_ORDER, make_hero, class_name
from pygame_rpg.config import START_MP, MP_PER_LEVEL
from pygame_rpg.player import Player

COMBAT = ("ap", "rap", "map", "dp", "rdp", "mdp")


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


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def test_classes_share_one_stat_budget():
    budgets = {sum(c.stats[s] for s in COMBAT) for c in CLASSES.values()}
    assert budgets == {30}                      # same as the classless 6 x 5


@pytest.mark.parametrize("key_", CLASS_ORDER)
def test_make_hero_uses_the_class(key_):
    cls = CLASSES[key_]
    p = make_hero("T", {}, key_)
    for stat, value in cls.stats.items():
        assert getattr(p, stat) == value
    assert p.current_hp == p.max_hp >= cls.stats["hp"]
    assert p.max_mp == p.current_mp == START_MP + cls.mp_bonus
    assert p.equipment["weapon"].id == cls.kit[0]
    assert p.equipment["weapon"].kind == "weapon"
    assert p.equipped_abilities()
    carried = sorted([i.id for i in p.inventory]
                     + [i.id for i in p.equipment.values() if i])
    assert carried == sorted(cls.kit)
    assert all(b in p.blueprints for b in cls.blueprints)
    assert p.gold == cls.gold


def test_class_survives_a_save_and_old_saves_have_none(saves):
    p = make_hero("Mage", {}, "mage")
    p.lvl = 3
    S.save_player(p)
    q = S.load_player("Mage")
    assert q.hero_class == "mage" and class_name(q) == "Mage"
    assert q.max_mp == START_MP + 10 + 2 * MP_PER_LEVEL
    old = Player.from_dict({"name": "Old", "hero_class": "pirate"}, S._resolve)
    assert old.hero_class == "" and class_name(old) == "Adventurer"
    assert old.max_mp == START_MP


def test_hero_maker_class_stage(display, saves):
    from pygame_rpg.gui.hero_maker import HeroMakerScreen
    h = HeroMakerScreen(display)
    h.text = "Robin"
    h.handle_event(key(pygame.K_RETURN))
    assert h.stage == "class" and h.hero_class == CLASS_ORDER[0]
    h.handle_event(click(h.class_cards[CLASS_ORDER.index("archer")].center))
    assert h.hero_class == "archer"
    h.handle_event(key(pygame.K_RIGHT))
    assert h.hero_class == "mage"
    h.handle_event(key(pygame.K_LEFT))
    h.draw(display)
    h.handle_event(click(h.btn_class_next.rect.center))
    assert h.stage == "look"
    h.draw(display)
    h.handle_event(key(pygame.K_RETURN))
    h.draw(display)
    name, kw = h.handle_event(key(pygame.K_RETURN))
    assert name == "story" and kw["next"][0] == "base"  # prologue first
    kw = kw["next"][1]
    assert kw["player"].hero_class == "archer"
    assert kw["player"].equipment["weapon"].id == "bow"
    assert S.load_player("Robin").rap == CLASSES["archer"].stats["rap"]
