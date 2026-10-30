"""Player-facing names for the stats (no drawing).

The code and the saves keep the short V3 keys (``ap``, ``rdp`` ...);
everything the player reads goes through this module instead, so a
screen never shows "AP" or "MDP".

``LABEL``   full name ("Melee Attack"), for lists and the stats screen
``SHORT``   compact name ("Melee Atk"), for tight rows and item lines
``ABOUT``   one sentence on what the stat does
"""

LABEL = {
    "hp": "Health",
    "mp": "Mana",
    "ap": "Melee Attack",
    "rap": "Ranged Attack",
    "map": "Magic Attack",
    "dp": "Melee Defense",
    "rdp": "Ranged Defense",
    "mdp": "Magic Defense",
    "power": "Weapon Power",
}

SHORT = {
    "hp": "Health",
    "mp": "Mana",
    "ap": "Melee Atk",
    "rap": "Ranged Atk",
    "map": "Magic Atk",
    "dp": "Melee Def",
    "rdp": "Ranged Def",
    "mdp": "Magic Def",
    "power": "Power",
}

ABOUT = {
    "hp": "How much damage you can take before you collapse.",
    "mp": "Spent to cast abilities; grows with every level.",
    "ap": "Damage with swords, axes, maces and other close-range weapons.",
    "rap": "Damage with bows, crossbows, slingshots and other thrown or shot weapons.",
    "map": "Damage with staffs, wands and magic abilities.",
    "dp": "Blocks damage from enemies that bite, claw or hit up close.",
    "rdp": "Blocks damage from arrows, darts and other ranged attacks.",
    "mdp": "Blocks damage from spells and magic attacks.",
    "power": "A weapon's own damage, added to your attack; grows with its level.",
}

# The six combat stats as a table: attack type -> (attack, defense).
TYPES = ("melee", "ranged", "magic")
ATTACK = {"melee": "ap", "ranged": "rap", "magic": "map"}
DEFENSE = {"melee": "dp", "ranged": "rdp", "magic": "mdp"}


def stat_line(item, stats=("ap", "rap", "map", "dp", "rdp", "mdp", "hp")) -> list:
    """["+1 Melee Atk", "+2 Health", ...] for the stats ``item`` adds."""
    return [f"+{getattr(item, s)} {SHORT[s]}" for s in stats if getattr(item, s, 0)]


def stat_diffs(player, item) -> list:
    """(stat, now, with item) for every stat ``item`` or the gear it
    would replace adds, comparing against what the hero wears in the
    item's slot.  Weapons also compare their power ("power").  Empty
    for items that can't be equipped."""
    from .config import WEAPON_POWER_BASE, WEAPON_POWER_PER_LEVEL, UNARMED_POWER
    slot = player.slot_for(item)
    if slot is None:
        return []
    cur = player.equipment.get(slot)
    rows = []
    if item.kind == "weapon":
        power = lambda w: (UNARMED_POWER if w is None
                           else WEAPON_POWER_BASE + WEAPON_POWER_PER_LEVEL * w.level)
        rows.append(("power", power(cur), power(item)))
    for stat in ("ap", "rap", "map", "dp", "rdp", "mdp", "hp"):
        old, new = getattr(cur, stat, 0), getattr(item, stat, 0)
        if old or new:
            rows.append((stat, old, new))
    return rows
