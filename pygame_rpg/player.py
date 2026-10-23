"""Player character: pure data + stats logic, no UI.

Mirrors the V3 text game's ``char_stats`` / ``lvl_up_stats`` dicts:
name, lvl, xp, hp, ap, rap, map, dp, rdp, mdp plus equipment slots,
a backpack and the weight limit.

The stat fields are *base* stats (starting values + level-ups).
Equipment never mutates them: ``total(stat)`` = base + the sum over
equipped items, recomputed on every call.  ``hp`` is the base max HP;
the HP the hero currently has is ``current_hp`` (capped at ``max_hp``).
"""
from dataclasses import dataclass, field

from .config import (
    START_LEVEL, START_XP, START_HP, START_AP, START_RAP, START_MAP,
    START_DP, START_RDP, START_MDP,
    XP_PER_LEVEL, LEVEL_UP_BONUS, BASE_MAX_WEIGHT, max_xp_for,
)

# Equipment slots a character can fill.  Items carry the slot they fit
# (``Item.slot``); trinkets say "trinket" and take either trinket slot.
EQUIP_SLOTS = ("weapon", "head", "torso", "hands", "feet",
               "trinket1", "trinket2")
TRINKET_SLOTS = ("trinket1", "trinket2")

# Slot names used by saves written before the M2 wiring.  "accessory"
# becomes the first trinket slot; anything else unknown (e.g. the old
# single "armor" slot) has its item moved back to the backpack on load.
LEGACY_SLOTS = {"accessory": "trinket1"}

# Stats equipment can add to (hp = bonus max HP).
BONUS_STATS = ("hp", "ap", "rap", "map", "dp", "rdp", "mdp")

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

    def __post_init__(self):
        for slot in EQUIP_SLOTS:
            self.equipment.setdefault(slot, None)
        for stat in UPGRADABLE_STATS:
            self.lvl_up_counts.setdefault(stat, 0)
        if self.current_hp is None:
            self.current_hp = self.max_hp

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
        return BASE_MAX_WEIGHT

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
        equipped.  Trinkets take the first free trinket slot (the first
        one when both are full)."""
        slot = getattr(item, "slot", "")
        if slot == "trinket":
            for s in TRINKET_SLOTS:
                if self.equipment[s] is None:
                    return s
            return TRINKET_SLOTS[0]
        return slot if slot in EQUIP_SLOTS else None

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
            "ap": self.ap,
            "rap": self.rap,
            "map": self.map,
            "dp": self.dp,
            "rdp": self.rdp,
            "mdp": self.mdp,
            "lvl_up_counts": dict(self.lvl_up_counts),
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
        go back to the backpack.  A missing ``current_hp`` means full HP.
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
        p.inventory = [resolve(r) for r in data.get("inventory", [])]
        for slot, r in data.get("equipment", {}).items():
            if r is None:
                continue
            item = resolve(r)
            slot = LEGACY_SLOTS.get(slot, slot)
            fits = (slot in TRINKET_SLOTS and item.slot == "trinket"
                    or slot in EQUIP_SLOTS and item.slot == slot)
            if fits and p.equipment[slot] is None:
                p.equipment[slot] = item
            else:
                p.inventory.append(item)
        saved_hp = data.get("current_hp")
        p.current_hp = p.max_hp if saved_hp is None else saved_hp
        p._clamp_hp()
        return p
