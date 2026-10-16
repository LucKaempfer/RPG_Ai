"""Item catalog (M3: level-1 starters, ported from RPG_V3/assets_V3.py).

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
    weight: int = 0      # kg
    # Stat bonuses (weapons apply these while equipped).
    ap: int = 0
    rap: int = 0
    map: int = 0
    dp: int = 0
    rdp: int = 0
    mdp: int = 0
    slot: str = ""       # equipment slot (weapons: "weapon")
    effect: str = ""     # status effect applied in combat
    heal: int = 0        # consumables: HP restored on use
    description: str = ""


def _wp(id_, name, ap=0, rap=0, map_=0, dp=0, effect="", desc=""):
    return Item(
        id=id_, name=name, kind="weapon", weight=1,
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

# --- Consumables ---
CONSUMABLES = [
    Item(id="potion", name="Health Potion", kind="consumable", weight=1,
         heal=25, description="Restores 25 HP."),
]

# --- Full catalog: id -> Item ---
CATALOG = {i.id: i for i in WEAPONS + CONSUMABLES}

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
