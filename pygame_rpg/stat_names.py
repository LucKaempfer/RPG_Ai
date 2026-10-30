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
}

# The six combat stats as a table: attack type -> (attack, defense).
TYPES = ("melee", "ranged", "magic")
ATTACK = {"melee": "ap", "ranged": "rap", "magic": "map"}
DEFENSE = {"melee": "dp", "ranged": "rdp", "magic": "mdp"}


def stat_line(item, stats=("ap", "rap", "map", "dp", "rdp", "mdp", "hp")) -> list:
    """["+1 Melee Atk", "+2 Health", ...] for the stats ``item`` adds."""
    return [f"+{getattr(item, s)} {SHORT[s]}" for s in stats if getattr(item, s, 0)]
