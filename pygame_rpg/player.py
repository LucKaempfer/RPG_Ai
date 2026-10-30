"""Player character: pure data + stats logic, no UI.

Mirrors the V3 text game's ``char_stats`` / ``lvl_up_stats`` dicts:
name, lvl, xp, hp, ap, rap, map, dp, rdp, mdp plus equipment slots,
a backpack and the weight limit.

The stat fields are *base* stats (starting values + level-ups).
Equipment never mutates them: ``total(stat)`` = base + the sum over
equipped items, recomputed on every call.  ``hp`` is the base max HP;
the HP the hero currently has is ``current_hp`` (capped at ``max_hp``).
MP works the same way: ``max_mp`` grows with level, ``current_mp`` is
what is left to cast abilities with.
"""
from dataclasses import dataclass, field

from .crafting import BLUEPRINTS, STARTER_BLUEPRINTS
from .config import (
    START_LEVEL, START_XP, START_HP, START_AP, START_RAP, START_MAP,
    START_DP, START_RDP, START_MDP, START_MP, MP_PER_LEVEL,
    XP_PER_LEVEL, LEVEL_UP_BONUS, BASE_MAX_WEIGHT, max_xp_for,
)

# Equipment slots a character can fill.  Items carry the slot they fit
# (``Item.slot``); trinkets say "trinket" and take either trinket slot,
# abilities say "ability" and take any of the four ability slots.
TRINKET_SLOTS = ("trinket1", "trinket2")
ABILITY_SLOTS = ("ability1", "ability2", "ability3", "ability4")
EQUIP_SLOTS = ("weapon", "head", "torso", "hands", "feet",
               *TRINKET_SLOTS, *ABILITY_SLOTS)
# Item.slot values that stand for a group of slots.
SLOT_GROUPS = {"trinket": TRINKET_SLOTS, "ability": ABILITY_SLOTS}

# Slot names used by saves written before the M2 wiring.  "accessory"
# becomes the first trinket slot; anything else unknown (e.g. the old
# single "armor" slot) has its item moved back to the backpack on load.
LEGACY_SLOTS = {"accessory": "trinket1"}

# Stats equipment can add to (hp = bonus max HP).
BONUS_STATS = ("hp", "ap", "rap", "map", "dp", "rdp", "mdp")

# Character look (hero maker): option index per key.  The options
# themselves (colours, hair styles) live in ``assets.LOOK_OPTIONS``.
LOOK_KEYS = ("skin", "hair", "hair_color", "tunic")

# Crafting materials (from smashed props), kept in a weightless pouch.
MATERIALS = ("wood", "iron", "cloth", "bone", "stone")

# Stats that can be raised on level-up (V3 xp_check lets the player
# pick one of: hp, ap, rap, map, dp, rdp, mdp).
UPGRADABLE_STATS = ("hp", "ap", "rap", "map", "dp", "rdp", "mdp")


@dataclass
class Player:
    name: str = ""
    lvl: int = START_LEVEL
    xp: int = START_XP
    hp: int = START_HP
    ap: int = START_AP
    rap: int = START_RAP  # raw attack points
    map: int = START_MAP
    dp: int = START_DP
    rdp: int = START_RDP
    mdp: int = START_MDP
    # How many times each stat was raised by level-ups (V3 lvl_up_stats).
    lvl_up_counts: dict = field(default_factory=dict)
    # Backpack: list of Item objects (see items.py).
    inventory: list = field(default_factory=list)
    # Slot name -> Item or None.
    equipment: dict = field(default_factory=dict)
    # HP the hero has right now; None = full (resolved to max_hp).
    current_hp: int = None
    # MP left for abilities; None = full (resolved to max_mp).
    current_mp: int = None
    # Appearance chosen in the hero maker: LOOK_KEYS -> option index.
    look: dict = field(default_factory=dict)
    # Money (mob and prop drops; spent and earned at the shop).
    gold: int = 0
    # Crafting materials in the pouch: MATERIALS -> count (no weight).
    materials: dict = field(default_factory=dict)
    # Weapon blueprints learned (weapon base ids, see crafting.py).
    blueprints: list = field(default_factory=lambda: list(STARTER_BLUEPRINTS))

    def __post_init__(self):
        for slot in EQUIP_SLOTS:
            self.equipment.setdefault(slot, None)
        for stat in UPGRADABLE_STATS:
            self.lvl_up_counts.setdefault(stat, 0)
        for key in LOOK_KEYS:
            self.look.setdefault(key, 0)
        for mat in MATERIALS:
            self.materials.setdefault(mat, 0)
        if self.current_hp is None:
            self.current_hp = self.max_hp
        if self.current_mp is None:
            self.current_mp = self.max_mp

    # --- Derived stats (base + equipment) ---
    def bonus(self, stat: str) -> int:
        """Sum of ``stat`` over all equipped items."""
        return sum(getattr(item, stat, 0)
                   for item in self.equipment.values() if item is not None)

    def total(self, stat: str) -> int:
        """Effective stat: base value + equipment bonus."""
        return getattr(self, stat) + self.bonus(stat)

    @property
    def max_hp(self) -> int:
        return self.total("hp")

    def heal(self, amount: int) -> int:
        """Restore up to ``amount`` HP (capped at max_hp); returns the
        HP actually restored."""
        before = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        return self.current_hp - before

    def _clamp_hp(self) -> None:
        self.current_hp = max(0, min(self.current_hp, self.max_hp))

    # --- MP (ability casts, M4 battle menu) ---
    @property
    def max_mp(self) -> int:
        return START_MP + MP_PER_LEVEL * (self.lvl - 1)

    def restore_mp(self, amount: int) -> int:
        """Restore up to ``amount`` MP (capped at max_mp); returns the
        MP actually restored."""
        before = self.current_mp
        self.current_mp = min(self.max_mp, self.current_mp + amount)
        return self.current_mp - before

    def rest(self) -> None:
        """Full HP and MP (back at the Base after a run)."""
        self.current_hp = self.max_hp
        self.current_mp = self.max_mp

    def can_cast(self, ability) -> bool:
        """Enough MP for ``ability`` and it sits in an ability slot.
        Cooldowns are battle state and live in combat.py (M4)."""
        return (self.slot_of(ability) in ABILITY_SLOTS
                and self.current_mp >= ability.mp_cost)

    def spend_mp(self, ability) -> None:
        if not self.can_cast(ability):
            raise ValueError(f"cannot cast {getattr(ability, 'id', ability)!r}")
        self.current_mp -= ability.mp_cost

    def equipped_abilities(self) -> list:
        """Abilities in slot order (the battle menu's 4 entries)."""
        return [self.equipment[s] for s in ABILITY_SLOTS
                if self.equipment[s] is not None]

    # --- XP / level-up (V3 xp_check) ---
    @property
    def max_xp(self) -> int:
        return max_xp_for(self.lvl)

    def add_xp(self, amount: int) -> int:
        """Add XP; returns how many level-ups occurred (0 or more).

        Reaching exactly max_xp counts (tutorial: level 1 needs 100 XP).
        """
        self.xp += amount
        ups = 0
        while self.xp >= self.max_xp:
            self.xp -= self.max_xp
            self.lvl += 1
            self.current_mp += MP_PER_LEVEL
            ups += 1
        return ups

    def apply_level_up(self, stat: str) -> None:
        """Grant +LEVEL_UP_BONUS to one stat (chosen per level-up)."""
        if stat not in UPGRADABLE_STATS:
            raise ValueError(f"unknown stat {stat!r}")
        setattr(self, stat, getattr(self, stat) + LEVEL_UP_BONUS)
        self.lvl_up_counts[stat] += 1
        if stat == "hp":
            # A raised max HP comes with the matching current HP.
            self.current_hp += LEVEL_UP_BONUS

    # --- Weight / equipment ---
    @property
    def max_weight(self) -> int:
        """Base carry limit plus equipped trinkets' bonus_weight."""
        return BASE_MAX_WEIGHT + sum(
            getattr(i, "bonus_weight", 0)
            for i in self.equipment.values() if i is not None)

    @property
    def weight(self) -> int:
        total = 0
        for item in self.inventory:
            total += getattr(item, "weight", 0)
        for item in self.equipment.values():
            if item is not None:
                total += getattr(item, "weight", 0)
        return total

    def can_carry(self, item) -> bool:
        return self.weight + getattr(item, "weight", 0) <= self.max_weight

    def slot_for(self, item):
        """The slot ``item`` would go into, or None if it can't be
        equipped.  Grouped slots (trinkets, abilities) take the first
        free one, or the first one when all are full."""
        slot = getattr(item, "slot", "")
        if slot in SLOT_GROUPS:
            group = SLOT_GROUPS[slot]
            for s in group:
                if self.equipment[s] is None:
                    return s
            return group[0]
        return slot if slot in EQUIP_SLOTS else None

    def can_equip(self, item) -> bool:
        """Item has a slot and the hero meets its level gate."""
        return (self.slot_for(item) is not None
                and getattr(item, "level", 1) <= self.lvl)

    def slot_of(self, item):
        """The slot ``item`` is equipped in (identity check), or None."""
        for slot, equipped in self.equipment.items():
            if equipped is item:
                return slot
        return None

    def equip(self, item, slot=None) -> None:
        """Move ``item`` from the backpack into ``slot`` (default: its
        natural slot, see ``slot_for``).

        Whatever was in the slot goes back to the backpack.
        """
        if slot is None:
            slot = self.slot_for(item)
        if slot not in EQUIP_SLOTS:
            raise ValueError(f"unknown slot {slot!r}")
        if getattr(item, "level", 1) > self.lvl:
            raise ValueError(f"{item.id!r} needs level {item.level}")
        if item not in self.inventory:
            raise ValueError("item is not in the backpack")
        self.inventory.remove(item)
        old = self.equipment[slot]
        self.equipment[slot] = item
        if old is not None:
            self.inventory.append(old)
        self._clamp_hp()

    def unequip(self, slot: str) -> None:
        """Move the item in ``slot`` back to the backpack."""
        item = self.equipment.get(slot)
        if item is None:
            return
        self.equipment[slot] = None
        self.inventory.append(item)
        self._clamp_hp()

    def drop(self, item) -> None:
        """Remove ``item`` from the game (backpack or equipment)."""
        if item in self.inventory:
            self.inventory.remove(item)
            return
        slot = self.slot_of(item)
        if slot is not None:
            self.equipment[slot] = None
            self._clamp_hp()

    # --- Consumables ---
    def can_use(self, item) -> bool:
        """Whether ``item`` can be used outside battle right now."""
        return (getattr(item, "kind", "") == "consumable"
                and item in self.inventory
                and not item.combat_only
                and item.heal > 0
                and self.current_hp < self.max_hp)

    def use(self, item) -> int:
        """Use one charge of a consumable; returns the HP restored.
        The item leaves the backpack when its last charge is spent."""
        if not self.can_use(item):
            raise ValueError(f"cannot use {getattr(item, 'id', item)!r} now")
        healed = self.heal(item.heal)
        item.charges -= 1
        if item.charges <= 0:
            self.inventory.remove(item)
        return healed

    # --- Serialization (used by savegame.py) ---
    @staticmethod
    def _item_ref(item, default_charges):
        """Save form of an item: its id, or {"id", "charges"} when a
        consumable has used charges (``default_charges(id)`` = catalog
        value)."""
        if item is None:
            return None
        if item.charges and item.charges != default_charges(item.id):
            return {"id": item.id, "charges": item.charges}
        return item.id

    def to_dict(self, default_charges=lambda _id: None) -> dict:
        ref = lambda item: self._item_ref(item, default_charges)
        return {
            "name": self.name,
            "lvl": self.lvl,
            "xp": self.xp,
            "hp": self.hp,
            "current_hp": self.current_hp,
            "current_mp": self.current_mp,
            "ap": self.ap,
            "rap": self.rap,
            "map": self.map,
            "dp": self.dp,
            "rdp": self.rdp,
            "mdp": self.mdp,
            "lvl_up_counts": dict(self.lvl_up_counts),
            "look": dict(self.look),
            "gold": self.gold,
            "materials": dict(self.materials),
            "blueprints": list(self.blueprints),
            "equipment": {slot: ref(item)
                          for slot, item in self.equipment.items()},
            "inventory": [ref(i) for i in self.inventory],
        }

    @classmethod
    def from_dict(cls, data: dict, resolve) -> "Player":
        """Build a player from saved data.  ``resolve(ref)`` turns a
        saved item reference (id or {"id", "charges"}) into an Item.

        Migrates saves from before the M2 wiring: legacy slot names are
        renamed, and items in unknown slots or in a slot they don't fit
        go back to the backpack.  A save without a ``look`` gets the
        default look, one without ``materials`` an empty pouch, one without ``blueprints``
        the starter blueprints.  A missing ``current_hp`` /
        ``current_mp`` means full HP / MP.
        """
        p = cls(
            name=data.get("name", ""),
            lvl=data.get("lvl", START_LEVEL),
            xp=data.get("xp", START_XP),
            hp=data.get("hp", START_HP),
            ap=data.get("ap", START_AP),
            rap=data.get("rap", START_RAP),
            map=data.get("map", START_MAP),
            dp=data.get("dp", START_DP),
            rdp=data.get("rdp", START_RDP),
            mdp=data.get("mdp", START_MDP),
        )
        p.lvl_up_counts.update(data.get("lvl_up_counts", {}))
        p.gold = max(0, int(data.get("gold", 0)))
        known = data.get("blueprints")
        if isinstance(known, list):
            p.blueprints = [b for b in known if b in BLUEPRINTS]
        mats = data.get("materials", {})
        if isinstance(mats, dict):
            p.materials.update({k: max(0, v) for k, v in mats.items()
                                if k in MATERIALS and isinstance(v, int)})
        look = data.get("look", {})
        if isinstance(look, dict):
            p.look.update({k: int(v) for k, v in look.items()
                           if k in LOOK_KEYS and isinstance(v, int)})
        p.inventory = [resolve(r) for r in data.get("inventory", [])]
        for slot, r in data.get("equipment", {}).items():
            if r is None:
                continue
            item = resolve(r)
            slot = LEGACY_SLOTS.get(slot, slot)
            fits = (slot in SLOT_GROUPS.get(item.slot, ())
                    or slot in EQUIP_SLOTS and item.slot == slot)
            if fits and p.equipment[slot] is None:
                p.equipment[slot] = item
            else:
                p.inventory.append(item)
        saved_hp = data.get("current_hp")
        p.current_hp = p.max_hp if saved_hp is None else saved_hp
        p._clamp_hp()
        saved_mp = data.get("current_mp")
        p.current_mp = (p.max_mp if saved_mp is None
                        else max(0, min(saved_mp, p.max_mp)))
        return p
