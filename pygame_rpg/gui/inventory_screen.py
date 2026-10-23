# pygame_rpg/gui/inventory_screen.py
"""Inventory screen (port of the V3 inventory() + backpack() stubs, built
to the DEVELOPMENT.md M3 spec).

Left:  backpack list (icon, name, count, weight) + weight bar.
Right: equipment slots (weapon, head / torso / hands / feet armor,
       two trinkets) with icons, and a detail panel for the selected item: description, stat diffs vs
       the currently equipped item (green gain / red loss) and actions.

Actions per item:
- Equip   (weapon/armor/trinket in the backpack -> its slot)
- Unequip (equipped item -> back to the backpack)
- Use     (healing consumable outside battle: one charge, capped at
           max HP; new for the GUI -- V3 has no potion logic)
- Drop    (remove the item from the game)

Weight is invariant under equip/unequip (Player.weight counts both
backpack and equipment), so nothing here can exceed max_weight; the
weight gate (can_carry) applies once M4 adds pickups.

Esc / Back -> back to the Base.  Window close saves, then quits.
"""

import pygame

from ..assets import AssetManager
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..savegame import save_player
from .screen import (
    QUIT, Screen, Button, font,
    BG_COLOR, PANEL_COLOR, PANEL_HOT, TEXT_COLOR, DIM_TEXT, GOLD,
    BORDER_COLOR, FOCUS_BORDER,
)

# Green/red for stat diffs (not in the shared palette).
GOOD = (110, 200, 110)
BAD = (220, 110, 110)

# Kind-based slot border colors (no rarity data exists in V3).
KIND_BORDER = {
    "weapon": (180, 90, 90),
    "armor": (90, 130, 190),
    "trinket": (170, 140, 90),
    "consumable": (120, 120, 140),
}

from ..player import EQUIP_SLOTS as SLOTS
DIFF_STATS = ("hp", "ap", "rap", "map", "dp", "rdp", "mdp")
SLOT_LABELS = {"trinket1": "trinket", "trinket2": "trinket"}

ROW_H = 36
VISIBLE_ROWS = 10


class InventoryScreen(Screen):
    name = "inventory"

    def __init__(self, screen, player):
        super().__init__(screen)
        self.player = player
        self.selected = None
        self.hot = None
        self.scroll = 0
        self.assets = AssetManager()
        self._icons = {}

        # Panels.
        self.backpack = pygame.Rect(24, 64, 430, 452)
        self.equip_panel = pygame.Rect(470, 64, 306, 200)
        self.detail_panel = pygame.Rect(470, 276, 306, 240)

        # Equipment slot boxes: 4 on the first row, 3 on the second.
        self.slot_rects = [
            pygame.Rect(486 + (i % 4) * 72, 96 + (i // 4) * 80, 56, 56)
            for i in range(len(SLOTS))
        ]

        self.btn_back = Button("Back", (24, 548, 140, 40), size=22)
        self.btn_equip = Button("Equip", (286, 548, 120, 40), size=22)
        self.btn_unequip = Button("Unequip", (416, 548, 120, 40), size=22)
        self.btn_use = Button("Use", (546, 548, 120, 40), size=22)
        self.btn_drop = Button("Drop", (666, 548, 110, 40), size=22)

    # -- geometry ------------------------------------------------------
    def _row_rects(self):
        """Rects of the visible backpack rows (recomputed: list changes)."""
        rects = []
        top = 96
        lo = self.scroll
        hi = min(len(self.player.inventory), lo + VISIBLE_ROWS)
        for _ in range(lo, hi):
            rects.append(pygame.Rect(40, top, 398, ROW_H - 4))
            top += ROW_H
        return rects

    # -- selection / actions --------------------------------------------
    def _enabled_actions(self):
        """Action buttons that react to input for the current selection."""
        if self.selected is None:
            return set()
        sel = self.selected
        if sel in self.player.inventory:
            acts = {self.btn_drop}
            if self.player.slot_for(sel) is not None:
                acts.add(self.btn_equip)
            if self.player.can_use(sel):
                acts.add(self.btn_use)
            return acts
        if self.player.slot_of(sel) is not None:
            return {self.btn_unequip, self.btn_drop}
        return set()

    def _hover(self, pos):
        for i, r in enumerate(self._row_rects()):
            if r.collidepoint(pos):
                return ("row", i + self.scroll)
        for i, r in enumerate(self.slot_rects):
            if r.collidepoint(pos):
                return ("slot", i)
        enabled = self._enabled_actions()
        for btn in (self.btn_back, self.btn_equip, self.btn_unequip,
                    self.btn_use, self.btn_drop):
            if btn.rect.collidepoint(pos):
                if btn is self.btn_back or btn in enabled:
                    return ("btn", btn)
        return None

    # -- mutations -------------------------------------------------------
    def _equip(self):
        self.player.equip(self.selected)
        self.selected = None

    def _unequip(self):
        self.player.unequip(self.player.slot_of(self.selected))
        self.selected = None

    def _use(self):
        sel = self.selected
        self.player.use(sel)
        # Keep a stack selected while it still has charges.
        if sel not in self.player.inventory:
            self.selected = None

    def _drop(self):
        self.player.drop(self.selected)
        self.selected = None

    # -- Screen hooks ------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            save_player(self.player)
            return QUIT
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                hit = self._hover(event.pos)
                if hit is None:
                    return None
                kind, val = hit
                if kind == "row":
                    item = self.player.inventory[val]
                    self.selected = (
                        None if self.selected is item else item)
                elif kind == "slot":
                    item = self.player.equipment.get(SLOTS[val])
                    if item is not None:
                        self.selected = (
                            None if self.selected is item else item)
                elif val is self.btn_back:
                    return ("base", {"player": self.player})
                elif val is self.btn_equip:
                    self._equip()
                elif val is self.btn_unequip:
                    self._unequip()
                elif val is self.btn_use:
                    self._use()
                elif val is self.btn_drop:
                    self._drop()
            elif event.button in (4, 5):
                step = -1 if event.button == 4 else 1
                max_scroll = max(0, len(self.player.inventory) - VISIBLE_ROWS)
                self.scroll = max(0, min(max_scroll, self.scroll + step))
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return ("base", {"player": self.player})
            elif event.key in (pygame.K_UP, pygame.K_DOWN):
                step = -1 if event.key == pygame.K_UP else 1
                max_scroll = max(0,
                                 len(self.player.inventory) - VISIBLE_ROWS)
                self.scroll = max(0, min(max_scroll, self.scroll + step))
        return None

    # -- drawing helpers ---------------------------------------------
    def _icon(self, item, size=32):
        """Item icon scaled to ``size`` pixels (cached per id+size)."""
        key = (item.id, size)
        if key not in self._icons:
            surf = self.assets.load_image(f"items/{item.id}.png")
            if surf.get_size() != (size, size):
                surf = pygame.transform.scale(surf, (size, size))
            self._icons[key] = surf
        return self._icons[key]

    def _diffs(self):
        """(stat, old, new) rows: selected item vs its slot's occupant.

        Empty when nothing is selected, the item has no slot, or the
        selected item is the one currently equipped in that slot.
        """
        sel = self.selected
        if sel is None or self.player.slot_of(sel) is not None:
            return []
        slot = self.player.slot_for(sel)
        if slot is None:
            return []
        cur = self.player.equipment.get(slot)
        rows = []
        for stat in DIFF_STATS:
            old, new = getattr(cur, stat, 0), getattr(sel, stat, 0)
            if old or new:
                rows.append((stat, old, new))
        return rows

    def _dim_button(self, surface, btn):
        """Draw an action button in its inactive state (no input)."""
        pygame.draw.rect(surface, (30, 30, 42), btn.rect, border_radius=6)
        pygame.draw.rect(surface, (60, 60, 80), btn.rect,
                         width=2, border_radius=6)
        text = font(btn.font_size).render(btn.label, True, DIM_TEXT)
        surface.blit(text, text.get_rect(center=btn.rect.center))

    def draw(self, surface):
        surface.fill(BG_COLOR)
        p = self.player
        hover = self.hot
        hot_btn = hover[1] if hover is not None and hover[0] == "btn" else None

        title = font(28).render(f"Inventory — {p.name}", True, GOLD)
        surface.blit(title, title.get_rect(midtop=(SCREEN_WIDTH // 2, 24)))

        # Backpack panel.
        pygame.draw.rect(surface, PANEL_COLOR, self.backpack, border_radius=8)
        pygame.draw.rect(surface, BORDER_COLOR, self.backpack,
                         width=2, border_radius=8)
        head = font(22).render("Backpack", True, TEXT_COLOR)
        surface.blit(head, (36, 70))
        wt = font(18).render(
            f"{p.weight} / {p.max_weight} kg    HP {p.current_hp} / {p.max_hp}",
            True, DIM_TEXT)
        surface.blit(wt, wt.get_rect(
            midbottom=(self.backpack.centerx, self.backpack.bottom - 10)))

        for i, r in enumerate(self._row_rects()):
            item = p.inventory[self.scroll + i]
            idx = self.scroll + i
            is_sel = self.selected is item
            is_hot = (hover is not None and hover[0] == "row"
                      and hover[1] == idx)
            if is_sel:
                pygame.draw.rect(surface, PANEL_HOT, r, border_radius=4)
                pygame.draw.rect(surface, FOCUS_BORDER, r,
                                 width=2, border_radius=4)
            elif is_hot:
                pygame.draw.rect(surface, PANEL_HOT, r, border_radius=4)
            surface.blit(self._icon(item, 24), (r.x + 5, r.y + 4))
            nm = font(20).render(item.name, True,
                                 TEXT_COLOR if is_sel else DIM_TEXT)
            surface.blit(nm, (r.x + 38, r.y + 6))
            uses = f" · x{item.charges}" if item.charges > 1 else ""
            tag = font(16).render(
                f"{item.kind} · {item.weight} kg{uses}", True, DIM_TEXT)
            surface.blit(tag, tag.get_rect(midright=(r.right - 8, r.centery)))

        # Equipment panel.
        pygame.draw.rect(surface, PANEL_COLOR, self.equip_panel, border_radius=8)
        pygame.draw.rect(surface, BORDER_COLOR, self.equip_panel,
                         width=2, border_radius=8)
        head = font(22).render("Equipped", True, TEXT_COLOR)
        surface.blit(head, (482, 70))
        for i, box in enumerate(self.slot_rects):
            item = p.equipment.get(SLOTS[i])
            is_sel = item is not None and self.selected is item
            is_hot = (hover is not None and hover[0] == "slot"
                      and hover[1] == i and item is not None)
            border = (KIND_BORDER.get(item.kind, BORDER_COLOR)
                      if item is not None else BORDER_COLOR)
            if is_sel:
                pygame.draw.rect(surface, PANEL_HOT, box, border_radius=6)
                pygame.draw.rect(surface, FOCUS_BORDER, box,
                                 width=2, border_radius=6)
            else:
                pygame.draw.rect(
                    surface, PANEL_HOT if is_hot else (30, 30, 42),
                    box, border_radius=6)
                pygame.draw.rect(surface, border, box,
                                 width=2, border_radius=6)
            if item is not None:
                cx, cy = box.center
                surface.blit(self._icon(item, 36), (cx - 18, cy - 18))
            label = font(16).render(
                SLOT_LABELS.get(SLOTS[i], SLOTS[i]), True, DIM_TEXT)
            surface.blit(label, label.get_rect(
                midtop=(box.centerx, box.bottom + 3)))

        # Detail panel.
        pygame.draw.rect(surface, PANEL_COLOR, self.detail_panel, border_radius=8)
        pygame.draw.rect(surface, BORDER_COLOR, self.detail_panel,
                         width=2, border_radius=8)
        head = font(22).render("Details", True, TEXT_COLOR)
        surface.blit(head, (482, 282))
        sel = self.selected
        if sel is None:
            note = font(18).render("Select an item.", True, DIM_TEXT)
            surface.blit(note, note.get_rect(
                midtop=(self.detail_panel.centerx, 320)))
        else:
            nm = font(22).render(sel.name, True, GOLD)
            surface.blit(nm, (482, 314))
            if sel.description:
                desc = font(18).render(sel.description, True, DIM_TEXT)
                surface.blit(desc, (482, 344))
            y = 372
            for stat, old, new in self._diffs():
                color = (GOOD if new > old else
                         BAD if new < old else TEXT_COLOR)
                txt = font(18).render(
                    f"{stat.upper():>3}  {old} -> {new}", True, color)
                surface.blit(txt, (500, y))
                y += 22
            if p.slot_of(sel) is not None:
                eq = font(18).render("Currently equipped.", True, GOOD)
                surface.blit(eq, (500, y))

        # Action buttons + back.
        enabled = self._enabled_actions()
        for btn in (self.btn_equip, self.btn_unequip, self.btn_use,
                    self.btn_drop):
            if btn in enabled:
                btn.draw(surface, hot=(btn is hot_btn))
            else:
                self._dim_button(surface, btn)
        self.btn_back.draw(surface, hot=(self.btn_back is hot_btn))

        hint = font(16).render(
            "Esc: back to base    wheel / Up Down: scroll", True, DIM_TEXT)
        surface.blit(hint, (24, 522))
