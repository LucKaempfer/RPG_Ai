"""Hero classes (no drawing): chosen once in the hero maker.

A class sets the hero's starting stats, a mana bonus, the starter kit
(the weapon and ability go straight into their slots) and the weapon
blueprint the hero already knows.  Every class has the same stat
budget (stat points summed over the six combat stats), so none is just
stronger; they lean different ways.  Level-ups work the same for all.

``Player.hero_class`` stores the key; saves from before classes have ""
(``NO_CLASS``), which keeps the old flat stats and the old starter kit.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HeroClass:
    key: str
    name: str
    blurb: str                  # one line under the name
    about: str                  # a few sentences on how it plays
    stats: dict                 # hp, ap, rap, map, dp, rdp, mdp
    mp_bonus: int = 0           # added to max MP at every level
    kit: tuple = ()             # starter item ids (weapon + ability equipped)
    gold: int = 0               # starting gold
    blueprints: tuple = field(default_factory=tuple)   # known on top of the starters


CLASSES = {
    "warrior": HeroClass(
        "warrior", "Warrior", "Tough, hits hard up close",
        "Lots of health and armour. Fights best with swords, axes and maces "
        "and shrugs off claws and bites, but magic hurts.",
        {"hp": 120, "ap": 8, "rap": 3, "map": 2, "dp": 8, "rdp": 5, "mdp": 4},
        kit=("sword", "potion", "power_strike")),
    "archer": HeroClass(
        "archer", "Archer", "Strikes from range",
        "Deadly with bows, crossbows and slings, and hard to hit with "
        "arrows. Less health, so finish fights before they get close.",
        {"hp": 95, "ap": 4, "rap": 9, "map": 3, "dp": 4, "rdp": 7, "mdp": 3},
        kit=("bow", "potion", "piercing_shot"), blueprints=("bow",)),
    "mage": HeroClass(
        "mage", "Mage", "Spells and burning wands",
        "The strongest magic and the most mana, with good protection "
        "against spells. Fragile in a brawl.",
        {"hp": 85, "ap": 2, "rap": 3, "map": 10, "dp": 3, "rdp": 4, "mdp": 8},
        mp_bonus=10, kit=("fiery_wand", "potion", "mana_potion", "fireball"),
        blueprints=("fiery_wand",)),
    "rogue": HeroClass(
        "rogue", "Rogue", "Quick blades, dirty tricks",
        "Good with daggers and thrown weapons alike. Starts with a "
        "poison bomb, a Shield spell to dodge behind and some gold.",
        {"hp": 100, "ap": 7, "rap": 6, "map": 3, "dp": 5, "rdp": 5, "mdp": 4},
        kit=("dagger", "potion", "poison_bomb", "shield"), gold=30,
        blueprints=("dagger",)),
}
CLASS_ORDER = tuple(CLASSES)
NO_CLASS = ""


def class_of(player):
    """The player's ``HeroClass``, or None for heroes made before classes."""
    return CLASSES.get(getattr(player, "hero_class", NO_CLASS))


def class_name(player) -> str:
    cls = class_of(player)
    return cls.name if cls else "Adventurer"


def make_hero(name, look, key):
    """A new level-1 hero of class ``key``: its stats, kit (weapon and
    abilities equipped), gold and blueprints, at full HP / MP."""
    from .items import item_by_id
    from .player import Player
    cls = CLASSES[key]
    p = Player(name=name, look=dict(look), hero_class=key, **cls.stats)
    p.gold = cls.gold
    p.blueprints += [b for b in cls.blueprints if b not in p.blueprints]
    p.inventory = [item_by_id(i) for i in cls.kit]
    for item in list(p.inventory):
        if item.kind in ("weapon", "ability"):
            p.equip(item)
    p.rest()
    return p
