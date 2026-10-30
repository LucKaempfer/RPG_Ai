"""Shop rules (no drawing): prices, the floor's stock, buying, selling.

Each floor's merchant (``special_rooms``) sells potions, rations and
mana potions without running out, plus four pieces of gear rolled from
the floor seed (one of each, up to floor + 1 in level).  The merchant
buys anything in the backpack: junk for its full ``value``, everything
else for a quarter of its price.
"""
import random

from .items import item_by_id, roll_loot

# Price per kind for a level-1 item; gear grows with the triangle number
# of its level (1, 3, 6, 10 x base), consumables linearly.
BASE_PRICE = {"weapon": 20, "armor": 15, "trinket": 25, "ability": 30,
              "consumable": 8}
SELL_SHARE = 4            # gear and consumables sell for price // 4
GEAR_KINDS = ("weapon", "armor", "trinket", "ability")
GEAR_IN_STOCK = 4
RESTOCKING = ("potion", "ration", "mana_potion")   # never sell out


def price(item) -> int:
    """What the merchant asks for ``item``."""
    if item.kind == "junk":
        return item.value
    base = BASE_PRICE.get(item.kind, 10)
    if item.kind == "consumable":
        return base * item.level
    return base * item.level * (item.level + 1) // 2


def sell_price(item) -> int:
    """What the merchant pays for ``item``."""
    if item.kind == "junk":
        return item.value
    return max(1, price(item) // SELL_SHARE)


def _tier_id(base: str, level: int) -> str:
    return base if level <= 1 else f"{base}_{level}"


def roll_stock(seed, floor: int) -> list:
    """The floor's goods: restocking consumables at the floor's tier,
    then GEAR_IN_STOCK rolled pieces of gear."""
    rng = random.Random(f"shop-{seed}")
    tier = max(1, min(4, floor))
    stock = [item_by_id(_tier_id(base, tier)) for base in RESTOCKING]
    stock += [roll_loot(rng, max_level=min(4, floor + 1), kinds=GEAR_KINDS)
              for _ in range(GEAR_IN_STOCK)]
    return stock


def restocks(item) -> bool:
    return item.kind == "consumable"


def buy(player, stock, sold, index) -> str:
    """Buy ``stock[index]``; ``sold`` (a set of indices) records gear that
    is gone.  Returns a message; the purchase happened if it starts with
    "Bought"."""
    if index in sold:
        return "Sold out."
    item = stock[index]
    cost = price(item)
    if player.gold < cost:
        return f"Not enough gold ({cost} needed)."
    if not player.can_carry(item):
        return f"{item.name} is too heavy to carry."
    player.gold -= cost
    player.inventory.append(item_by_id(item.id))
    if not restocks(item):
        sold.add(index)
    return f"Bought {item.name} for {cost} gold."


def sell(player, item) -> str:
    """Sell a backpack item (equipped items can't be sold)."""
    if item not in player.inventory:
        return "Unequip it first."
    gain = sell_price(item)
    player.inventory.remove(item)
    player.gold += gain
    return f"Sold {item.name} for {gain} gold."
