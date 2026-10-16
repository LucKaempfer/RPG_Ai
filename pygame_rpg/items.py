"""Item catalog (M2: item system).

Weapons: level-1 bases ported from RPG_V3/assets_V3.py, plus grown
levels 2-4 tiers (V3 has no level-2+ data, so the growth is a design
decision per Plan.md §4.2).

Armor: designed from scratch (V3 holds only an empty `class Armor:`),
head / torso / hands / feet, level-1 bases plus grown levels 2-4.

V3 weapon constructor: WP(name, lvl, ap, rap, map, dp, rdp, mdp, kg).
Weapon effects: melee_sharp/range_sharp -> bleeding, *_dull -> stun,
magic poison/fire/electric -> poison/burning/electrocuted.
"""
from dataclasses import dataclass

# --- Data ---

@dataclass
class Item:
    id: str
    name: str
    kind: str            # "weapon" | "consumable" | "armor" | "trinket"
    level: int = 1       # player level gate (min level to equip)
    weight: int = 0      # kg
    # Stat bonuses (weapons apply these while equipped).
    ap: int = 0
    rap: int = 0
    map: int = 0
    dp: int = 0
    rdp: int = 0
    mdp: int = 0
    hp: int = 0          # armor: bonus max HP while equipped
    slot: str = ""       # equipment slot (weapons: "weapon")
    effect: str = ""     # status effect applied in combat
    heal: int = 0        # consumables: HP restored on use
    description: str = ""


def _wp(id_, name, ap=0, rap=0, map_=0, dp=0, effect="", desc="",
        level=1, weight=1):
    """Weapon builder. `level` is the player level gate; `weight` in kg."""
    return Item(
        id=id_, name=name, kind="weapon", level=level, weight=weight,
        ap=ap, rap=rap, map=map_, dp=dp,
        slot="weapon", effect=effect, description=desc,
    )


# --- Level-1 weapon catalog (all V3 level-1 weapons, 1 kg each) ---
WEAPONS = [
    # melee sharp (bleeding)
    _wp("saber", "Saber", ap=1, dp=1, effect="bleeding"),
    _wp("spear", "Spear", ap=1, dp=1, effect="bleeding"),
    _wp("dagger", "Dagger", ap=1, map_=1, dp=1, effect="bleeding"),
    _wp("sword", "Sword", ap=1, dp=1, effect="bleeding"),
    _wp("greatsword", "Greatsword", ap=1, dp=1, effect="bleeding"),
    # melee dull (stun)
    _wp("warhammer", "Warhammer", ap=1, dp=1, effect="stun"),
    _wp("mace", "Mace", ap=1, dp=1, effect="stun"),
    _wp("club", "Club", ap=1, dp=1, effect="stun"),
    # range sharp (bleeding)
    _wp("crossbow", "Crossbow", rap=1, effect="bleeding"),
    _wp("bow", "Bow", rap=1, effect="bleeding"),
    _wp("blowpipe", "Blowpipe", rap=1, effect="bleeding"),
    # range dull (stun)
    _wp("boomerang", "Boomerang", rap=1, effect="stun"),
    _wp("slingshot", "Slingshot", rap=1, effect="stun"),
    _wp("whip", "Whip", rap=1, effect="stun"),
    # magic (poison / fire / electric)
    _wp("poisonous_staff", "Poisonous Staff", map_=1, effect="poison"),
    _wp("poisonous_wand", "Poisonous Wand", map_=1, effect="poison"),
    _wp("fiery_staff", "Fiery Staff", map_=1, effect="burning"),
    _wp("fiery_wand", "Fiery Wand", map_=1, effect="burning"),
    _wp("electric_staff", "Electric Staff", map_=1, effect="electrocuted"),
    _wp("electric_wand", "Electric Wand", map_=1, effect="electrocuted"),
]

# --- Higher weapon tiers (levels 2-4, grown from the level-1 bases) ---
# V3 has no level-2+ data, so these are a design decision (Plan.md
# §4.2): per level above 1, each attack stat the weapon has (ap/rap/map)
# and dp grow by +1, and weight = level. A stat a weapon lacks stays 0.
# Better ailment chance/duration is keyed off `level` in combat.py (M4).
_ROMAN = {2: "II", 3: "III", 4: "IV"}

def _tier(base: Item, level: int) -> Item:
    """Grow a level-1 weapon base into a higher-level tier."""
    up = level - 1
    return _wp(
        f"{base.id}_{level}",
        f"{base.name} {_ROMAN[level]}",
        ap=base.ap + (up if base.ap else 0),
        rap=base.rap + (up if base.rap else 0),
        map_=base.map + (up if base.map else 0),
        dp=base.dp + up,
        effect=base.effect, desc=base.description,
        level=level, weight=level,
    )

WEAPON_TIERS = [
    _tier(base, level)
    for base in WEAPONS
    for level in (2, 3, 4)
]

# --- Armor (designed from scratch; V3 has no armor data) ---
# Slots: head / torso / hands / feet, four levels each (Plan.md §4.3:
# dp/rdp/mdp scaling + small hp bonus; tiers per level; weight matters).
# Slot stat profile (design decision, Plan.md §4.2/§4.3):
#   head  -> dp            (physical defence)
#   torso -> dp + rdp + mdp (the main piece, all defensive stats)
#   hands -> rdp           (raw defence)
#   feet  -> mdp           (magic defence)
# Every piece also grants a small max-hp bonus. Level-1 bases:
#   head/hands/feet: one defensive stat = 1, hp = 2, weight = 1 kg
#   torso: all three defensive stats = 1, hp = 3, weight = 2 kg
def _arm(id_, name, slot, dp=0, rdp=0, mdp=0, hp=0, level=1, weight=1):
    """Armor builder. `slot` is the armor sub-slot (head/torso/hands/feet)."""
    return Item(
        id=id_, name=name, kind="armor", level=level, weight=weight,
        dp=dp, rdp=rdp, mdp=mdp, hp=hp, slot=slot,
    )


ARMOR = [
    # head (dp)
    _arm("leather_cap", "Leather Cap", "head", dp=1, hp=2),
    _arm("iron_helmet", "Iron Helmet", "head", dp=1, hp=2),
    # torso (dp + rdp + mdp)
    _arm("leather_vest", "Leather Vest", "torso", dp=1, rdp=1, mdp=1, hp=3, weight=2),
    _arm("chainmail", "Chain Mail", "torso", dp=1, rdp=1, mdp=1, hp=3, weight=2),
    # hands (rdp)
    _arm("leather_gloves", "Leather Gloves", "hands", rdp=1, hp=2),
    _arm("iron_gauntlets", "Iron Gauntlets", "hands", rdp=1, hp=2),
    # feet (mdp)
    _arm("leather_boots", "Leather Boots", "feet", mdp=1, hp=2),
    _arm("iron_boots", "Iron Boots", "feet", mdp=1, hp=2),
]

# Higher armor tiers (levels 2-4, grown from the level-1 bases): per level
# above 1, each defensive stat the piece has (dp/rdp/mdp) grows by +1,
# hp grows by +1, and weight grows by +1 (weight = base weight + level - 1).
def _arm_tier(base: Item, level: int) -> Item:
    """Grow a level-1 armor base into a higher-level tier."""
    up = level - 1
    return _arm(
        f"{base.id}_{level}",
        f"{base.name} {_ROMAN[level]}",
        base.slot,
        dp=base.dp + (up if base.dp else 0),
        rdp=base.rdp + (up if base.rdp else 0),
        mdp=base.mdp + (up if base.mdp else 0),
        hp=base.hp + up,
        level=level, weight=base.weight + up,
    )


ARMOR_TIERS = [
    _arm_tier(base, level)
    for base in ARMOR
    for level in (2, 3, 4)
]

# --- Consumables ---
CONSUMABLES = [
    Item(id="potion", name="Health Potion", kind="consumable", weight=1,
         heal=25, description="Restores 25 HP."),
]

# --- Full catalog: id -> Item ---
CATALOG = {i.id: i for i in WEAPONS + WEAPON_TIERS + ARMOR + ARMOR_TIERS + CONSUMABLES}

# Default equipment handed out by the hero maker (V3 starts heroes empty;
# the GUI gives a basic weapon and one potion).
STARTER_INVENTORY = ["sword", "potion"]


def item_by_id(item_id: str) -> Item:
    """Look up a catalog item by id; returns a copy so per-character
    state can never mutate the catalog."""
    if item_id not in CATALOG:
        raise KeyError(f"unknown item id: {item_id!r}")
    import copy
    return copy.copy(CATALOG[item_id])
