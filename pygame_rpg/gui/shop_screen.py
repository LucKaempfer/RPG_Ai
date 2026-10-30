# pygame_rpg/gui/shop_screen.py
"""Shop screen: trade with the floor's merchant (``shop.py`` rules).

Left: the merchant's goods (price; potions never run out, gear is one
of each).  Right: the hero's backpack with what each item sells for.
Left / Right pick a side, Up / Down an item, Enter (or the Buy / Sell
button) trades, Esc returns to the floor.  The dungeon floor passes
itself as ``return_to`` along with its stock and the set of sold-out
indices, so purchases last for the floor (and its run save).
"""

import pygame

from .. import audio
from ..assets import AssetManager
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..savegame import save_player
from ..shop import buy, sell, price, sell_price
from .inventory_screen import RARITY_COLOR
from .screen import (
    QUIT, Screen, Button, font,
    BG_COLOR, PANEL_COLOR, PANEL_HOT, TEXT_COLOR, DIM_TEXT, GOLD,
    BORDER_COLOR, FOCUS_BORDER,
)

ROW_H = 36
ROWS = 10
GOOD = (130, 210, 130)
BAD = (235, 110, 100)


class ShopScreen(Screen):
    name = "shop"

    @property
    def ambience(self):
        return getattr(self.return_to, "ambience", None)

    def __init__(self, screen, player, stock, sold, return_to=None):
        super().__init__(screen)
        self.player = player
        self.stock = stock
        self.sold = sold
        self.return_to = return_to
        self.side = 0                   # 0 = buy (merchant), 1 = sell (backpack)
        self.index = [0, 0]
        self.message, self.message_ok = "Welcome, traveller!", True
        self.assets = AssetManager()
        self._icons = {}
        self.panels = (pygame.Rect(24, 90, 368, ROWS * ROW_H + 50),
                       pygame.Rect(408, 90, 368, ROWS * ROW_H + 50))
        self.btn_buy = Button("Buy", (24, 540, 140, 36), size=22)
        self.btn_sell = Button("Sell", (408, 540, 140, 36), size=22)
        self.btn_back = Button("Back", (636, 540, 140, 36), size=22)
        self.hot = None

    # -- rows ------------------------------------------------------------
    def goods(self):
        """(item, price, available) for the merchant's side."""
        return [(item, price(item), i not in self.sold)
                for i, item in enumerate(self.stock)]

    def wares(self):
        """(item, sell price) for the backpack side."""
        return [(item, sell_price(item)) for item in self.player.inventory]

    def _count(self, side):
        return len(self.stock) if side == 0 else len(self.player.inventory)

    def _window(self, side):
        """First row shown, so the selection stays in view."""
        sel, n = self.index[side], self._count(side)
        return max(0, min(sel - ROWS // 2, n - ROWS))

    def _row_rect(self, side, row):
        p = self.panels[side]
        return pygame.Rect(p.x + 8, p.y + 40 + row * ROW_H, p.w - 16, ROW_H - 4)

    # -- actions ---------------------------------------------------------
    def trade(self):
        """Buy or sell the selected row on the current side."""
        if self.side == 0:
            if not self.stock:
                return
            msg = buy(self.player, self.stock, self.sold, self.index[0])
            ok = msg.startswith("Bought")
        else:
            if not self.player.inventory:
                return
            item = self.player.inventory[self.index[1]]
            msg = sell(self.player, item)
            ok = msg.startswith("Sold")
            self.index[1] = min(self.index[1], max(0, self._count(1) - 1))
        self.message, self.message_ok = msg, ok
        audio.play("chest" if ok else "fail", volume=0.6)
        if ok:
            save_player(self.player)

    def _back(self):
        save_player(self.player)
        if self.return_to is not None:
            return ("resume", {"screen": self.return_to})
        return ("base", {"player": self.player})

    # -- Screen hooks ----------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            save_player(self.player)
            if self.return_to is not None:
                self.return_to.save_run()
            return QUIT
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE:
                return self._back()
            if k in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
                self.side = 1 - self.side if k == pygame.K_TAB else (
                    0 if k in (pygame.K_LEFT, pygame.K_a) else 1)
            elif k in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                n = self._count(self.side)
                if n:
                    step = -1 if k in (pygame.K_UP, pygame.K_w) else 1
                    self.index[self.side] = (self.index[self.side] + step) % n
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.trade()
        elif event.type == pygame.MOUSEMOTION:
            self.hot = next((b for b in (self.btn_buy, self.btn_sell, self.btn_back)
                             if b.rect.collidepoint(event.pos)), None)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.btn_back.rect.collidepoint(pos):
                return self._back()
            if self.btn_buy.rect.collidepoint(pos):
                self.side = 0
                self.trade()
            elif self.btn_sell.rect.collidepoint(pos):
                self.side = 1
                self.trade()
            for side in (0, 1):
                top = self._window(side)
                for row in range(min(ROWS, self._count(side) - top)):
                    if self._row_rect(side, row).collidepoint(pos):
                        self.side, self.index[side] = side, top + row
        elif event.type == pygame.MOUSEWHEEL:
            n = self._count(self.side)
            if n:
                self.index[self.side] = max(0, min(n - 1, self.index[self.side] - event.y))
        return None

    # -- drawing -----------------------------------------------------------
    def _icon(self, item, size=24):
        key = (item.id, size)
        if key not in self._icons:
            surf = self.assets.load_image(f"items/{item.id}.png")
            self._icons[key] = pygame.transform.scale(surf, (size, size))
        return self._icons[key]

    def draw(self, surface):
        surface.fill(BG_COLOR)
        title = font(32).render("Merchant", True, GOLD)
        surface.blit(title, title.get_rect(midtop=(SCREEN_WIDTH // 2, 18)))
        p = self.player
        info = font(20).render(
            f"Gold {p.gold}      Weight {p.weight} / {p.max_weight} kg", True, TEXT_COLOR)
        surface.blit(info, info.get_rect(midtop=(SCREEN_WIDTH // 2, 56)))

        goods = self.goods()
        wares = self.wares()
        for side, (head, rows) in enumerate((("For sale", goods), ("Your backpack", wares))):
            panel = self.panels[side]
            active = side == self.side
            pygame.draw.rect(surface, PANEL_COLOR, panel, border_radius=8)
            pygame.draw.rect(surface, FOCUS_BORDER if active else BORDER_COLOR,
                             panel, width=2, border_radius=8)
            surface.blit(font(22).render(head, True, TEXT_COLOR), (panel.x + 12, panel.y + 10))
            if not rows:
                note = font(18).render("Nothing here.", True, DIM_TEXT)
                surface.blit(note, (panel.x + 14, panel.y + 48))
            top = self._window(side)
            for row, entry in enumerate(rows[top:top + ROWS]):
                item, cost = entry[0], entry[1]
                available = entry[2] if side == 0 else True
                r = self._row_rect(side, row)
                if top + row == self.index[side]:
                    pygame.draw.rect(surface, PANEL_HOT, r, border_radius=4)
                    if active:
                        pygame.draw.rect(surface, FOCUS_BORDER, r, width=2, border_radius=4)
                pygame.draw.rect(surface, RARITY_COLOR.get(item.rarity, BORDER_COLOR),
                                 (r.x + 3, r.y + 3, 28, 28), width=2, border_radius=4)
                surface.blit(self._icon(item), (r.x + 5, r.y + 5))
                color = TEXT_COLOR if available else DIM_TEXT
                name = item.name if available else f"{item.name} (sold)"
                surface.blit(font(20).render(name, True, color), (r.x + 38, r.y + 8))
                tag = font(18).render(f"{cost} g", True, GOLD if available else DIM_TEXT)
                surface.blit(tag, tag.get_rect(midright=(r.right - 8, r.centery)))

        msg = font(20).render(self.message, True, GOOD if self.message_ok else BAD)
        surface.blit(msg, msg.get_rect(midtop=(SCREEN_WIDTH // 2, 508)))
        for btn in (self.btn_buy, self.btn_sell, self.btn_back):
            btn.draw(surface, hot=(btn is self.hot))
        hint = font(16).render("Left/Right: side   Up/Down: item   Enter: trade   Esc: back",
                               True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(midbottom=(SCREEN_WIDTH // 2 + 20, SCREEN_HEIGHT - 4)))
