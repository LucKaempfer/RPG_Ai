"""The shop room: placement, the merchant, prices, buying and selling."""
import pygame
import pytest

from pygame_rpg import items as I, savegame as S, shop
from pygame_rpg.dungeon import Dungeon
from pygame_rpg.enemies import boss_room, cell_of
from pygame_rpg.player import Player
from pygame_rpg.special_rooms import special_rooms, keeper_cell


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()
    screen._FONTS.clear()       # don't leave dead fonts for the next module


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


@pytest.mark.parametrize("seed", range(20))
def test_one_safe_shop_per_floor(seed, display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    d = DungeonScreen(display, Player(name="Scout"), seed=seed)
    room = d.special["shop"]
    assert room is not d.dungeon.rooms[0] and room is not boss_room(d.dungeon)
    assert not any(room.contains(cell_of(e)) for e in d.enemies)
    assert not any(room.contains(c) for c, _ in d.chests)
    assert not any(room.contains(p.cell) for p in d.props)
    k = d.keepers["shop"]
    r = room.rect
    assert r.left < k[0] < r.right - 1 and r.top < k[1] < r.bottom - 1
    assert all(max(abs(k[0] - x), abs(k[1] - y)) > 1 for x, y in room.doors)


def test_special_rooms_are_seeded():
    a, b = Dungeon(), Dungeon()
    a.generate(9)
    b.generate(9)
    assert special_rooms(a, 9)["shop"].id == special_rooms(b, 9)["shop"].id


def test_prices():
    assert shop.price(I.item_by_id("sword")) == 20
    assert shop.price(I.item_by_id("sword_4")) == 200
    assert shop.price(I.item_by_id("potion_2")) == 16
    assert shop.sell_price(I.item_by_id("gold_tooth")) == 25
    assert shop.sell_price(I.item_by_id("sword_2")) == 15


def test_stock_scales_with_the_floor():
    one, four = shop.roll_stock(3, 1), shop.roll_stock(3, 4)
    assert [i.id for i in one[:3]] == ["potion", "ration", "mana_potion"]
    assert [i.id for i in four[:3]] == ["potion_4", "ration_4", "mana_potion_4"]
    assert all(i.kind in shop.GEAR_KINDS and i.level <= 2 for i in one[3:])
    assert [i.id for i in shop.roll_stock(3, 1)] == [i.id for i in one]


def test_buy_and_sell_rules():
    p = Player(name="Buyer", gold=30)
    stock = shop.roll_stock(1, 1)
    sold = set()
    assert shop.buy(p, stock, sold, 0).startswith("Bought")       # potion restocks
    assert shop.buy(p, stock, sold, 0).startswith("Bought") and not sold
    gear = 3
    p.gold = shop.price(stock[gear])
    assert shop.buy(p, stock, sold, gear).startswith("Bought") and sold == {gear}
    assert shop.buy(p, stock, sold, gear) == "Sold out."
    assert shop.buy(p, stock, sold, 0).startswith("Not enough gold")
    p.inventory.append(I.item_by_id("silver_goblet"))
    assert shop.sell(p, p.inventory[-1]).startswith("Sold") and p.gold == 20
    heavy = Player(name="Full", gold=999)
    heavy.inventory += [I.item_by_id("chainmail_4")] * 10
    assert "too heavy" in shop.buy(heavy, [I.item_by_id("sword_2")], set(), 0)


def test_trading_through_the_screens(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    from pygame_rpg.gui.shop_screen import ShopScreen
    p = Player(name="Trader", gold=200)
    p.inventory.append(I.item_by_id("rat_tail"))
    d = DungeonScreen(display, p, seed=5)
    assert d.interact() is None                         # nobody in reach
    kx, ky = d.keepers["shop"]
    d.x, d.y = d._centre((kx, ky + 1))
    assert not d._fits(*d._centre((kx, ky)))            # the merchant blocks
    name, kw = d.handle_event(key(pygame.K_e))
    assert name == "shop" and kw["return_to"] is d
    s = ShopScreen(display, p, kw["stock"], kw["sold"], return_to=d)
    s.index[0] = 3
    s.handle_event(key(pygame.K_RETURN))                # buy gear
    assert d.shop_sold == {3}
    s.handle_event(key(pygame.K_RIGHT))
    s.handle_event(key(pygame.K_RETURN))                # sell the rat tail (row 0)
    assert all(i.id != "rat_tail" for i in p.inventory)
    s.draw(display)
    assert s.handle_event(key(pygame.K_ESCAPE)) == ("resume", {"screen": d})
    # Sold-out gear survives the run save, the gold the hero save.
    again = DungeonScreen(display, S.load_player("Trader"), run=d.to_run())
    assert again.shop_sold == {3} and again.player.gold == p.gold
