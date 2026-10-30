# pygame_rpg/gui/forge_screen.py
"""Forge screen: craft and upgrade weapons and armour at a floor's
anvil (``crafting.py`` rules).

Two tabs: Craft (every blueprint the hero knows: the level-1 item for
materials + gold) and Upgrade (the weapons and armour the hero carries,
raised one tier).  The right panel shows the result and what it costs, each
material green if the pouch holds enough.  Left / Right (or Tab) switch
tabs, Up / Down pick, Enter forges, Esc returns to the floor.
"""

import pygame

from .. import audio
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..crafting import (
    craft, craft_cost, can_craft, upgrade, upgrade_cost, can_upgrade,
    upgradeable, base_id, family, FAMILY_NAMES,
)
from ..items import item_by_id
from ..savegame import save_player
from ..stat_names import stat_line
from .screen import (
    QUIT, Screen, Button, font,
    BG_COLOR, PANEL_COLOR, PANEL_HOT, TEXT_COLOR, DIM_TEXT, GOLD,
    BORDER_COLOR, FOCUS_BORDER,
)

ROW_H = 34
ROWS = 10
GOOD = (130, 210, 130)
BAD = (235, 110, 100)
TABS = ("Craft", "Upgrade")


def _stats(item) -> str:
    return "  ".join(stat_line(item) + [f"{item.weight} kg", f"Lv {item.level}"])


def _blit_wrapped(surface, text, color, x, y, width, size=18):
    """Draw ``text`` (parts split by two spaces) on as many lines as it
    needs to fit ``width``; returns the y below the last line."""
    line = ""
    for part in text.split("  "):
        trial = f"{line}  {part}" if line else part
        if line and font(size).size(trial)[0] > width:
            surface.blit(font(size).render(line, True, color), (x, y))
            y += 22
            line = "   " + part
        else:
            line = trial
    surface.blit(font(size).render(line, True, color), (x, y))
    return y + 22


class ForgeScreen(Screen):
    name = "forge"

    @property
    def ambience(self):
        return getattr(self.return_to, "ambience", None)

    def __init__(self, screen, player, return_to=None):
        super().__init__(screen)
        self.player = player
        self.return_to = return_to
        self.tab = 0
        self.index = [0, 0]
        self.message, self.message_ok = "The coals are hot.", True
        self.list_panel = pygame.Rect(24, 120, 360, ROWS * ROW_H + 50)
        self.info_panel = pygame.Rect(400, 120, 376, ROWS * ROW_H + 50)
        self.tab_rects = [pygame.Rect(24 + i * 120, 84, 112, 32) for i in range(2)]
        self.btn_go = Button("Forge", (24, 540, 160, 36), size=22)
        self.btn_back = Button("Back", (636, 540, 140, 36), size=22)
        self.hot = None

    # -- rows ------------------------------------------------------------
    def rows(self):
        """Craft tab: blueprint base ids; Upgrade tab: weapon items."""
        if self.tab == 0:
            return sorted(self.player.blueprints,
                          key=lambda b: (item_by_id(b).kind != "weapon",
                                         family(item_by_id(b)), b))
        return upgradeable(self.player)

    def selected(self):
        rows = self.rows()
        if not rows:
            return None
        self.index[self.tab] = min(self.index[self.tab], len(rows) - 1)
        return rows[self.index[self.tab]]

    def _window(self):
        n, sel = len(self.rows()), self.index[self.tab]
        return max(0, min(sel - ROWS // 2, n - ROWS))

    def _row_rect(self, row):
        p = self.list_panel
        return pygame.Rect(p.x + 8, p.y + 12 + row * ROW_H, p.w - 16, ROW_H - 4)

    # -- actions ---------------------------------------------------------
    def forge(self):
        sel = self.selected()
        if sel is None:
            return
        if self.tab == 0:
            msg = craft(self.player, sel)
            ok = msg.startswith("Crafted")
        else:
            msg, better = upgrade(self.player, sel)
            ok = better is not None
        self.message, self.message_ok = msg, ok
        audio.play("bash" if ok else "fail", volume=0.7)
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
                self.tab = 1 - self.tab if k == pygame.K_TAB else (
                    0 if k in (pygame.K_LEFT, pygame.K_a) else 1)
            elif k in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                n = len(self.rows())
                if n:
                    step = -1 if k in (pygame.K_UP, pygame.K_w) else 1
                    self.index[self.tab] = (self.index[self.tab] + step) % n
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.forge()
        elif event.type == pygame.MOUSEMOTION:
            self.hot = next((b for b in (self.btn_go, self.btn_back)
                             if b.rect.collidepoint(event.pos)), None)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.btn_back.rect.collidepoint(pos):
                return self._back()
            if self.btn_go.rect.collidepoint(pos):
                self.forge()
            for i, r in enumerate(self.tab_rects):
                if r.collidepoint(pos):
                    self.tab = i
            top = self._window()
            for row in range(min(ROWS, len(self.rows()) - top)):
                if self._row_rect(row).collidepoint(pos):
                    self.index[self.tab] = top + row
        return None

    # -- drawing -----------------------------------------------------------
    def draw(self, surface):
        surface.fill(BG_COLOR)
        p = self.player
        title = font(32).render("Anvil", True, GOLD)
        surface.blit(title, title.get_rect(midtop=(SCREEN_WIDTH // 2, 14)))
        pouch = "   ".join(f"{m} {n}" for m, n in p.materials.items())
        info = font(19).render(f"Gold {p.gold}      {pouch}", True, TEXT_COLOR)
        surface.blit(info, info.get_rect(midtop=(SCREEN_WIDTH // 2, 52)))

        for i, r in enumerate(self.tab_rects):
            on = i == self.tab
            pygame.draw.rect(surface, PANEL_HOT if on else PANEL_COLOR, r, border_radius=6)
            pygame.draw.rect(surface, FOCUS_BORDER if on else BORDER_COLOR, r, 2, border_radius=6)
            t = font(22).render(TABS[i], True, TEXT_COLOR if on else DIM_TEXT)
            surface.blit(t, t.get_rect(center=r.center))

        for panel in (self.list_panel, self.info_panel):
            pygame.draw.rect(surface, PANEL_COLOR, panel, border_radius=8)
            pygame.draw.rect(surface, BORDER_COLOR, panel, width=2, border_radius=8)

        rows = self.rows()
        sel = self.selected()
        if not rows:
            empty = ("You know no blueprints yet." if self.tab == 0
                     else "Nothing to upgrade.")
            surface.blit(font(18).render(empty, True, DIM_TEXT),
                         (self.list_panel.x + 14, self.list_panel.y + 16))
        top = self._window()
        for row, entry in enumerate(rows[top:top + ROWS]):
            r = self._row_rect(row)
            if top + row == self.index[self.tab]:
                pygame.draw.rect(surface, PANEL_HOT, r, border_radius=4)
                pygame.draw.rect(surface, FOCUS_BORDER, r, width=2, border_radius=4)
            if self.tab == 0:
                ok = can_craft(p, entry)[0]
                name = item_by_id(entry).name
            else:
                ok = can_upgrade(p, entry)[0]
                name = entry.name + ("  (equipped)" if p.slot_of(entry) else "")
            label = font(20).render(name, True, TEXT_COLOR if ok else DIM_TEXT)
            surface.blit(label, (r.x + 10, r.y + 7))
            if ok:
                mark = font(18).render("ready", True, GOOD)
                surface.blit(mark, mark.get_rect(midright=(r.right - 8, r.centery)))

        if sel is not None:
            self._draw_info(surface, sel)

        msg = font(20).render(self.message, True, GOOD if self.message_ok else BAD)
        surface.blit(msg, msg.get_rect(midtop=(SCREEN_WIDTH // 2, 508)))
        self.btn_go.label = TABS[self.tab]
        for btn in (self.btn_go, self.btn_back):
            btn.draw(surface, hot=(btn is self.hot))
        hint = font(16).render("Left/Right: tab   Up/Down: pick   Enter: forge   Esc: back",
                               True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(midbottom=(SCREEN_WIDTH // 2 + 10, SCREEN_HEIGHT - 4)))

    def _draw_info(self, surface, sel):
        p = self.player
        x, y = self.info_panel.x + 14, self.info_panel.y + 14
        if self.tab == 0:
            result = item_by_id(sel)
            mats, gold = craft_cost(sel)
            ok, why = can_craft(p, sel)
            head = f"Craft: {result.name}"
        else:
            result = item_by_id(f"{base_id(sel)}_{sel.level + 1}")
            mats, gold = upgrade_cost(sel)
            ok, why = can_upgrade(p, sel)
            head = f"{sel.name}  ->  {result.name}"
        surface.blit(font(22).render(head, True, GOLD), (x, y))
        y += 30
        surface.blit(font(18).render(FAMILY_NAMES[family(result)], True, DIM_TEXT), (x, y))
        y += 24
        width = self.info_panel.right - x - 12
        if self.tab == 1:
            y = _blit_wrapped(surface, "Now:   " + _stats(sel), DIM_TEXT, x, y, width)
        y = _blit_wrapped(surface, ("After: " if self.tab else "") + _stats(result),
                          TEXT_COLOR, x, y, width)
        y += 14
        surface.blit(font(20).render("Costs", True, TEXT_COLOR), (x, y))
        y += 26
        for mat, need in mats.items():
            have = p.materials.get(mat, 0)
            line = font(19).render(f"{mat:<6} {have} / {need}", True,
                                   GOOD if have >= need else BAD)
            surface.blit(line, (x + 10, y))
            y += 22
        line = font(19).render(f"gold   {p.gold} / {gold}", True,
                               GOOD if p.gold >= gold else BAD)
        surface.blit(line, (x + 10, y))
        y += 34
        if not ok:
            surface.blit(font(18).render(why, True, BAD), (x, y))
