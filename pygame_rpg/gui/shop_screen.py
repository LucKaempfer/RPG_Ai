# pygame_rpg/gui/shop_screen.py
"""Shop screen: trade with the floor's merchant (``shop.py`` rules).

Left: the merchant's goods (price; potions never run out, gear is one
of each).  Right: the hero's backpack with what each item sells for.
Below: the selected item's details: level, weight, what it does, and
for gear its stats next to what the hero wears in that slot now.
Left / Right pick a side, Up / Down an item, Enter (or the Buy / Sell
button) trades, Esc returns to the floor.  The dungeon floor passes
itself as ``return_to`` along with its stock and the set of sold-out
indices, so purchases last for the floor (and its run save).
"""

import pygame

from .. import audio
from ..assets import AssetManager, upscale
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..savegame import save_player
from ..shop import buy, sell, price, sell_price
from ..combat import weapon_type
from ..stat_names import SHORT, stat_diffs
from .inventory_screen import RARITY_COLOR, _wrap
from .screen import (
    draw_background, draw_panel, QUIT, Screen, Button, font, PANEL_COLOR,
    PANEL_HOT, TEXT_COLOR, DIM_TEXT, GOLD, BORDER_COLOR, FOCUS_BORDER,
)

ROW_H = 36
ROWS = 7
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
        self.detail = pygame.Rect(24, 400, 752, 102)
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
            surf = self.assets.item_icon(item)
            self._icons[key] = upscale(surf, size)
        return self._icons[key]

    def selected(self):
        """The item under the cursor on the active side, or None."""
        rows = self.stock if self.side == 0 else self.player.inventory
        i = self.index[self.side]
        return rows[i] if 0 <= i < len(rows) else None

    def _draw_detail(self, surface):
        """Details of the selected item: name, level / kind / weight,
        stat changes against the equipped item, and its description."""
        box = self.detail
        draw_panel(surface, box, radius=8)
        item, p = self.selected(), self.player
        if item is None:
            return
        x, y = box.x + 12, box.y + 8
        name = font(22).render(item.name, True, GOLD if item.rarity == "common"
                               else RARITY_COLOR.get(item.rarity, GOLD))
        surface.blit(name, (x, y))
        kind = (f"{weapon_type(item)} weapon" + (f", causes {item.effect}" if item.effect else "")
                if item.kind == "weapon" else item.kind)
        info = f"{item.rarity} {kind}  ·  level {item.level}  ·  {item.weight} kg"
        tag = font(18).render(info, True, DIM_TEXT)
        surface.blit(tag, (x + name.get_width() + 14, y + 3))
        if p.slot_for(item) is not None and item.level > p.lvl:
            need = font(18).render(f"Needs level {item.level}", True, BAD)
            surface.blit(need, need.get_rect(topright=(box.right - 12, y + 3)))
        elif p.slot_of(item) is not None:
            worn = font(18).render("Equipped", True, GOOD)
            surface.blit(worn, worn.get_rect(topright=(box.right - 12, y + 3)))
        y += 28
        diffs = [] if p.slot_of(item) is not None else stat_diffs(p, item)
        if diffs:
            cur = p.equipment.get(p.slot_for(item))
            head = font(18).render("vs " + (cur.name if cur else "nothing") + ":",
                                   True, DIM_TEXT)
            surface.blit(head, (x, y))
            cx = x + head.get_width() + 10
            for stat, old, new in diffs:
                color = GOOD if new > old else BAD if new < old else TEXT_COLOR
                chip = font(18).render(f"{SHORT[stat]} {old} -> {new}", True, color)
                if cx + chip.get_width() > box.right - 12:
                    break
                surface.blit(chip, (cx, y))
                cx += chip.get_width() + 18
            y += 22
        text = (f"Junk. The merchant pays {sell_price(item)} gold for it."
                if item.kind == "junk" else item.description)
        for line in _wrap(text, 18, box.w - 24)[:3 if not diffs else 2]:
            surface.blit(font(18).render(line, True, TEXT_COLOR), (x, y))
            y += 20

    def draw(self, surface):
        draw_background(surface)
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

        self._draw_detail(surface)
        msg = font(20).render(self.message, True, GOOD if self.message_ok else BAD)
        surface.blit(msg, msg.get_rect(midtop=(SCREEN_WIDTH // 2, 508)))
        for btn in (self.btn_buy, self.btn_sell, self.btn_back):
            btn.draw(surface, hot=(btn is self.hot))
        hint = font(16).render("Left/Right: side   Up/Down: item   Enter: trade   Esc: back",
                               True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(midbottom=(SCREEN_WIDTH // 2 + 20, SCREEN_HEIGHT - 4)))
