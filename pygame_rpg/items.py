"""Item catalog (M2: item system).

Weapons: level-1 bases ported from RPG_V3/assets_V3.py, plus grown
levels 2-4 tiers (V3 has no level-2+ data, so the growth is a design
decision; see DEVELOPMENT.md §4).

Armor: designed from scratch (V3 holds only an empty `class Armor:`),
head / torso / hands / feet, level-1 bases plus grown levels 2-4.

Consumables: designed from scratch (V3 holds only an empty
`class Consumable:`): health potions, food, mana potions and bombs,
level-1 bases plus grown levels 2-4.  `charges` = uses per item.

Trinkets: passive bonus items — extra weight capacity, XP gain, loot
chance, movement speed, and one-ailment wards.  Level-1 bases plus grown
levels 2-4; they take either of the 2 trinket slots.

Abilities: designed from scratch (V3 holds only an empty
`class Ability:`): active battle skills that cost MP and have a
cooldown in turns.  Learned abilities sit in the backpack like items
and are assigned to the 4 ability slots; the level gate unlocks the
stronger tiers.

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
                         # | "ability"
    rarity: str = "common"  # common/rare/epic/legendary: UI border color
                            # + spawn weights (M4); never stat magnitude
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
    mana: int = 0        # consumables: mana restored (abilities, M2 step 5)
    damage: int = 0      # consumables: bomb damage dealt in battle (M4)
    charges: int = 0     # consumables: uses left; the item is gone at 0
    combat_only: bool = False  # consumables: only usable in battle (M4)
    # Trinket passive bonuses (applied while equipped):
    bonus_weight: int = 0   # trinkets: flat kg added to max_weight
    xp_bonus: int = 0       # trinkets: % bonus to XP gained (10 = +10%)
    loot_bonus: int = 0     # trinkets: % bonus to loot drop chance
    speed_bonus: int = 0    # trinkets: % bonus to movement speed
    resist: str = ""        # trinkets: ailment resisted (bleeding/stun/
                            # poison/burning/electrocuted)
    # Ability data (used by the M4 battle menu):
    attack_type: str = ""   # abilities: "melee" | "ranged" | "magic" | ""
                            # (support); picks ap/rap/map vs dp/rdp/mdp
    mp_cost: int = 0        # abilities: MP spent per cast
    cooldown: int = 0       # abilities: turns before it can be cast again
    guard: int = 0          # abilities: + to dp/rdp/mdp while active
    duration: int = 0       # abilities: turns a guard/effect lasts
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
# V3 has no level-2+ data, so these are a design decision (DEVELOPMENT.md
# §4): per level above 1, each attack stat the weapon has (ap/rap/map)
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
# Slots: head / torso / hands / feet, four levels each (DEVELOPMENT.md §4:
# dp/rdp/mdp scaling + small hp bonus; tiers per level; weight matters).
# Slot stat profile (design decision, DEVELOPMENT.md §4):
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

# --- Consumables (designed from scratch; V3 has no consumable data) ---
# Four lines, each a level-1 base plus grown levels 2-4:
#   health potion -> heal 25 x level, 1 charge          (usable anywhere)
#   ration (food) -> heal 10 x level, 3 charges         (usable anywhere)
#   mana potion   -> mana 20 x level, 1 charge          (battle only)
#   bombs         -> damage 15 + 10 per level above 1, 1 charge, plus an
#                    ailment (fire -> burning, poison -> poison,
#                    flash -> stun)                     (battle only)
# Weight stays at the base weight (1 kg) for every tier.
def _con(id_, name, heal=0, mana=0, damage=0, effect="", charges=1,
         combat_only=False, level=1, weight=1):
    """Consumable builder. The description is derived from the effect."""
    parts = []
    if heal:
        parts.append(f"Restores {heal} HP")
    if mana:
        parts.append(f"Restores {mana} mana")
    if damage:
        parts.append(f"Deals {damage} damage" + (f" + {effect}" if effect else ""))
    desc = ", ".join(parts) + "."
    if charges > 1:
        desc += f" {charges} uses."
    if combat_only:
        desc += " Battle only."
    return Item(
        id=id_, name=name, kind="consumable", level=level, weight=weight,
        heal=heal, mana=mana, damage=damage, effect=effect,
        charges=charges, combat_only=combat_only, description=desc,
    )


CONSUMABLES = [
    _con("potion", "Health Potion", heal=25),
    _con("ration", "Ration", heal=10, charges=3),
    _con("mana_potion", "Mana Potion", mana=20, combat_only=True),
    _con("fire_bomb", "Fire Bomb", damage=15, effect="burning", combat_only=True),
    _con("poison_bomb", "Poison Bomb", damage=15, effect="poison", combat_only=True),
    _con("flash_bomb", "Flash Bomb", damage=15, effect="stun", combat_only=True),
]


def _con_tier(base: Item, level: int) -> Item:
    """Grow a level-1 consumable base into a higher-level tier."""
    up = level - 1
    return _con(
        f"{base.id}_{level}",
        f"{base.name} {_ROMAN[level]}",
        heal=base.heal * level,
        mana=base.mana * level,
        damage=base.damage + 10 * up if base.damage else 0,
        effect=base.effect, charges=base.charges,
        combat_only=base.combat_only, level=level, weight=base.weight,
    )


CONSUMABLE_TIERS = [
    _con_tier(base, level)
    for base in CONSUMABLES
    for level in (2, 3, 4)
]

# --- Trinkets (designed from scratch; V3 has no trinket data) ---
# DEVELOPMENT.md §6.1: passive bonuses while equipped, 2 equipment slots
# (wired in sub-milestone 6). One trinket carries one kind of bonus:
# flat +kg to max_weight, +% XP gained, +% loot drop chance, +% movement
# speed, or a ward resisting one ailment. Two strength steps per bonus
# kind (5 and 10 at level 1) so the two slots can be mixed; the five
# wards cover the five weapon ailments (bleeding/stun/poison/burning/
# electrocuted). Trinkets weigh 0 kg — small wearable items that do not
# burden the backpack.
def _trinket(id_, name, bonus_weight=0, xp_bonus=0, loot_bonus=0,
             speed_bonus=0, resist="", level=1, desc=""):
    """Trinket builder. Weight is always 0 kg (small wearable items).
    Without ``desc`` the description is derived from the bonus."""
    if not desc:
        desc = (f"Holding it lets you carry {bonus_weight} kg more." if bonus_weight
                else f"Gains {xp_bonus}% more XP from defeats." if xp_bonus
                else f"{loot_bonus}% better loot drop chance." if loot_bonus
                else f"Moves {speed_bonus}% faster." if speed_bonus
                else f"Resists {resist}." if resist else "")
    return Item(
        id=id_, name=name, kind="trinket", level=level, weight=0,
        slot="trinket",
        bonus_weight=bonus_weight, xp_bonus=xp_bonus,
        loot_bonus=loot_bonus, speed_bonus=speed_bonus, resist=resist,
        description=desc,
    )


TRINKETS = [
    # weight capacity (flat +kg to max_weight)
    _trinket("weight_belt", "Weight Belt", bonus_weight=2,
             desc="Holding it lets you carry 2 kg more."),
    _trinket("iron_belt", "Iron Belt", bonus_weight=4,
             desc="Holding it lets you carry 4 kg more."),
    # XP gain (+% XP from defeats)
    _trinket("wisdom_amulet", "Wisdom Amulet", xp_bonus=10,
             desc="Gains 10% more XP from defeats."),
    _trinket("scholar_coin", "Scholar's Coin", xp_bonus=5,
             desc="Gains 5% more XP from defeats."),
    # loot (+% loot drop chance)
    _trinket("greed_ring", "Greed Ring", loot_bonus=10,
             desc="10% better loot drop chance."),
    _trinket("fortune_charm", "Fortune Charm", loot_bonus=5,
             desc="5% better loot drop chance."),
    # speed (+% movement speed)
    _trinket("haste_scarf", "Haste Scarf", speed_bonus=10,
             desc="Moves 10% faster."),
    _trinket("swift_feather", "Swift Feather", speed_bonus=5,
             desc="Moves 5% faster."),
    # wards (resist one ailment; strength scales with level in combat.py)
    _trinket("bleed_ward", "Bleed Ward", resist="bleeding",
             desc="Resists bleeding."),
    _trinket("stun_ward", "Stun Ward", resist="stun",
             desc="Resists stun."),
    _trinket("poison_ward", "Poison Ward", resist="poison",
             desc="Resists poison."),
    _trinket("burn_ward", "Burn Ward", resist="burning",
             desc="Resists burning."),
    _trinket("shock_ward", "Shock Ward", resist="electrocuted",
             desc="Resists electrocution."),
]

# Higher trinket tiers (levels 2-4, grown from the level-1 bases): per
# level above 1, the flat bonus grows by +1 kg (bonus_weight) and each
# percentage bonus grows by +5 points (xp/loot/speed). Wards keep their
# resist ailment; the resistance strength scales with the trinket's level
# in combat.py (M4), mirroring how weapon ailment chance/duration is
# keyed off level. Trinket weight stays 0 kg at every tier.
def _trinket_tier(base: Item, level: int) -> Item:
    """Grow a level-1 trinket base into a higher-level tier."""
    up = level - 1
    return _trinket(
        f"{base.id}_{level}",
        f"{base.name} {_ROMAN[level]}",
        bonus_weight=base.bonus_weight + (up if base.bonus_weight else 0),
        xp_bonus=base.xp_bonus + (5 * up if base.xp_bonus else 0),
        loot_bonus=base.loot_bonus + (5 * up if base.loot_bonus else 0),
        speed_bonus=base.speed_bonus + (5 * up if base.speed_bonus else 0),
        resist=base.resist,
        level=level,
    )


TRINKET_TIERS = [
    _trinket_tier(base, level)
    for base in TRINKETS
    for level in (2, 3, 4)
]

# --- Abilities (designed from scratch; V3 has no ability data) ---
# Active battle skills, cast from the battle menu (M4) out of the 4
# ability slots.  They weigh 0 kg (learned, not carried) and are used
# up by nothing: the cost is MP (`mp_cost`) and a cooldown in turns.
# Level-1 bases:
#   fireball        magic,  20 dmg + burning,       4 MP, cooldown 2
#   chain_lightning magic,  15 dmg + electrocuted,  5 MP, cooldown 2
#   power_strike    melee,  15 dmg + stun,          4 MP, cooldown 3
#   piercing_shot   ranged, 15 dmg + bleeding,      4 MP, cooldown 2
#   heal            support, restores 25 HP,        6 MP, cooldown 3
#   shield          support, +3 dp/rdp/mdp 3 turns, 5 MP, cooldown 4
# Damage is added to the caster's matching attack stat in combat.py.
def _ab(id_, name, attack_type="", damage=0, effect="", heal=0, guard=0,
        duration=0, mp_cost=0, cooldown=0, level=1):
    """Ability builder. The description is derived from the effect."""
    if damage:
        desc = f"{attack_type.capitalize()}: {damage} damage" + (
            f" + {effect}" if effect else "")
    elif heal:
        desc = f"Restores {heal} HP"
    else:
        desc = f"+{guard} DP/RDP/MDP for {duration} turns"
    desc += f". {mp_cost} MP, cooldown {cooldown}."
    return Item(
        id=id_, name=name, kind="ability", level=level, weight=0,
        slot="ability", attack_type=attack_type, damage=damage,
        effect=effect, heal=heal, guard=guard, duration=duration,
        mp_cost=mp_cost, cooldown=cooldown, description=desc,
    )


ABILITIES = [
    _ab("fireball", "Fireball", "magic", damage=20, effect="burning",
        mp_cost=4, cooldown=2),
    _ab("chain_lightning", "Chain Lightning", "magic", damage=15,
        effect="electrocuted", mp_cost=5, cooldown=2),
    _ab("power_strike", "Power Strike", "melee", damage=15, effect="stun",
        mp_cost=4, cooldown=3),
    _ab("piercing_shot", "Piercing Shot", "ranged", damage=15,
        effect="bleeding", mp_cost=4, cooldown=2),
    _ab("heal", "Heal", heal=25, mp_cost=6, cooldown=3),
    _ab("shield", "Shield", guard=3, duration=3, mp_cost=5, cooldown=4),
]


# Higher ability tiers (levels 2-4, grown from the level-1 bases): per
# level above 1, damage +10, heal +15, guard +2, and MP cost +2.
# Effect, duration and cooldown stay the same.  The level gate is what
# "unlocked by level" means: Fireball III needs player level 3.
def _ab_tier(base: Item, level: int) -> Item:
    """Grow a level-1 ability base into a higher-level tier."""
    up = level - 1
    return _ab(
        f"{base.id}_{level}",
        f"{base.name} {_ROMAN[level]}",
        attack_type=base.attack_type,
        damage=base.damage + 10 * up if base.damage else 0,
        effect=base.effect,
        heal=base.heal + 15 * up if base.heal else 0,
        guard=base.guard + 2 * up if base.guard else 0,
        duration=base.duration,
        mp_cost=base.mp_cost + 2 * up,
        cooldown=base.cooldown,
        level=level,
    )


ABILITY_TIERS = [
    _ab_tier(base, level)
    for base in ABILITIES
    for level in (2, 3, 4)
]

# --- Full catalog: id -> Item ---
CATALOG = {i.id: i for i in (WEAPONS + WEAPON_TIERS + ARMOR + ARMOR_TIERS
                             + CONSUMABLES + CONSUMABLE_TIERS
                             + TRINKETS + TRINKET_TIERS
                             + ABILITIES + ABILITY_TIERS)}

# Default equipment handed out by the hero maker (V3 starts heroes empty;
# the GUI gives a basic weapon, one potion and a first ability).
STARTER_INVENTORY = ["sword", "potion", "fireball"]


def item_by_id(item_id: str) -> Item:
    """Look up a catalog item by id; returns a copy so per-character
    state can never mutate the catalog."""
    if item_id not in CATALOG:
        raise KeyError(f"unknown item id: {item_id!r}")
    import copy
    return copy.copy(CATALOG[item_id])
