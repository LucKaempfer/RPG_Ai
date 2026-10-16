"""Player character: pure data + stats logic, no UI.

Mirrors the V3 text game's ``char_stats`` / ``lvl_up_stats`` dicts:
name, lvl, xp, hp, ap, rap, map, dp, rdp, mdp plus equipment slots,
a backpack and the weight limit.
"""
from dataclasses import dataclass, field

from .config import (
    START_LEVEL, START_XP, START_HP, START_AP, START_RAP, START_MAP,
    START_DP, START_RDP, START_MDP,
    XP_PER_LEVEL, LEVEL_UP_BONUS, BASE_MAX_WEIGHT, max_xp_for,
)

# Equipment slots a character can fill.
EQUIP_SLOTS = ("weapon", "armor", "accessory")

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

    def __post_init__(self):
        for slot in EQUIP_SLOTS:
            self.equipment.setdefault(slot, None)
        for stat in UPGRADABLE_STATS:
            self.lvl_up_counts.setdefault(stat, 0)

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

    def equip(self, slot: str, item) -> None:
        """Move ``item`` from the backpack into ``slot``.

        Whatever was in the slot goes back to the backpack.
        """
        if slot not in EQUIP_SLOTS:
            raise ValueError(f"unknown slot {slot!r}")
        if item not in self.inventory:
            raise ValueError("item is not in the backpack")
        self.inventory.remove(item)
        old = self.equipment[slot]
        self.equipment[slot] = item
        if old is not None:
            self.inventory.append(old)

    # --- Serialization (used by savegame.py) ---
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "lvl": self.lvl,
            "xp": self.xp,
            "hp": self.hp,
            "ap": self.ap,
            "rap": self.rap,
            "map": self.map,
            "dp": self.dp,
            "rdp": self.rdp,
            "mdp": self.mdp,
            "lvl_up_counts": dict(self.lvl_up_counts),
            "equipment": {
                slot: (getattr(item, "id", None) if item else None)
                for slot, item in self.equipment.items()
            },
            "inventory": [getattr(i, "id", None) for i in self.inventory],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
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
        p.equipment.update({
            s: d for s, d in data.get("equipment", {}).items() if s in EQUIP_SLOTS
        })
        p.inventory = list(data.get("inventory", []))
        return p
