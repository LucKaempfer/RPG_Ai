"""Crafting and upgrading weapons at a floor's anvil (no drawing).

Blueprints: the hero learns a weapon's blueprint by finding it (the boss
always drops one, enemies, chests and smashed props sometimes do) and
keeps it for good (``Player.blueprints``, weapon base ids).  New heroes
know their starter Sword.

With a weapon's blueprint the hero can, at an anvil:

* craft the level-1 weapon from materials (``RECIPES`` by weapon family)
  plus CRAFT_GOLD;
* upgrade one they carry to the next tier (``sword`` -> ``sword_2`` ...
  up to level 4) for the family's materials x the new level plus
  UPGRADE_GOLD x the new level.  The hero must have reached the new
  level, as for equipping.  An equipped weapon stays equipped.
"""
from .items import WEAPONS, item_by_id

# Weapon base ids (blueprints name these) and their families.
BLUEPRINTS = tuple(w.id for w in WEAPONS)
STARTER_BLUEPRINTS = ("sword",)
MAX_LEVEL = 4
CRAFT_GOLD = 10
UPGRADE_GOLD = 15

RECIPES = {
    "blade": {"iron": 3, "wood": 1},                  # sharp melee
    "blunt": {"iron": 2, "wood": 2, "stone": 1},      # dull melee
    "ranged": {"wood": 3, "cloth": 2},
    "magic": {"wood": 2, "bone": 2, "cloth": 1},
}
FAMILY_NAMES = {"blade": "Blade", "blunt": "Blunt weapon",
                "ranged": "Ranged weapon", "magic": "Magic weapon"}


def family(weapon) -> str:
    if weapon.rap:
        return "ranged"
    if weapon.map and not weapon.ap:
        return "magic"
    return "blunt" if weapon.effect == "stun" else "blade"


def base_id(item) -> str:
    """The level-1 id of a weapon tier (``bow_3`` -> ``bow``)."""
    head, _, tail = item.id.rpartition("_")
    return head if head and tail.isdigit() else item.id


def _scaled(recipe, times):
    return {mat: n * times for mat, n in recipe.items()}


def craft_cost(base: str):
    """(materials, gold) to craft the level-1 weapon ``base``."""
    return dict(RECIPES[family(item_by_id(base))]), CRAFT_GOLD


def upgrade_cost(item):
    """(materials, gold) to raise ``item`` one level."""
    new = item.level + 1
    return _scaled(RECIPES[family(item)], new), UPGRADE_GOLD * new


def _afford(player, mats, gold):
    """None if the hero can pay, else what is missing (a message)."""
    short = [f"{n - player.materials.get(m, 0)} {m}"
             for m, n in mats.items() if player.materials.get(m, 0) < n]
    if player.gold < gold:
        short.append(f"{gold - player.gold} gold")
    return "Need " + ", ".join(short) + "." if short else None


def _pay(player, mats, gold):
    for m, n in mats.items():
        player.materials[m] -= n
    player.gold -= gold


def can_craft(player, base):
    """(ok, reason)."""
    if base not in player.blueprints:
        return False, "You don't know this blueprint."
    weapon = item_by_id(base)
    if not player.can_carry(weapon):
        return False, "Too heavy to carry."
    missing = _afford(player, *craft_cost(base))
    return (missing is None), (missing or "")


def craft(player, base) -> str:
    ok, why = can_craft(player, base)
    if not ok:
        return why
    _pay(player, *craft_cost(base))
    weapon = item_by_id(base)
    player.inventory.append(weapon)
    return f"Crafted a {weapon.name}!"


def upgradeable(player) -> list:
    """Weapons the hero carries (equipped first) below MAX_LEVEL."""
    weapon = player.equipment.get("weapon")
    items = ([weapon] if weapon is not None else []) + [
        i for i in player.inventory if i.kind == "weapon"]
    return [i for i in items if i.level < MAX_LEVEL]


def can_upgrade(player, item):
    """(ok, reason)."""
    if item.kind != "weapon" or item.level >= MAX_LEVEL:
        return False, "It can't be improved any further."
    if base_id(item) not in player.blueprints:
        return False, f"You need the {item_by_id(base_id(item)).name} blueprint."
    if player.lvl < item.level + 1:
        return False, f"Requires level {item.level + 1}."
    better = item_by_id(f"{base_id(item)}_{item.level + 1}")
    if player.weight - item.weight + better.weight > player.max_weight:
        return False, "Too heavy to carry."
    missing = _afford(player, *upgrade_cost(item))
    return (missing is None), (missing or "")


def upgrade(player, item):
    """Raise ``item`` one tier in place (backpack or weapon slot).
    Returns (message, new item or None)."""
    ok, why = can_upgrade(player, item)
    if not ok:
        return why, None
    _pay(player, *upgrade_cost(item))
    better = item_by_id(f"{base_id(item)}_{item.level + 1}")
    if player.equipment.get("weapon") is item:
        player.equipment["weapon"] = better
    else:
        player.inventory[player.inventory.index(item)] = better
    return f"{item.name} is now {better.name}!", better


def roll_blueprint(rng, known):
    """A weapon blueprint the hero doesn't know yet (None if they know
    them all)."""
    unknown = [b for b in BLUEPRINTS if b not in known]
    return rng.choice(unknown) if unknown else None
