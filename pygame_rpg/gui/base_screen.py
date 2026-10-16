# pygame_rpg/gui/base_screen.py
"""Base / Lobby screen (port of the V3 lobby()) — the in-game hub.

On entry it runs the V3 xp_check() equivalent *in read-only mode*:
pending level-ups are counted but not banked, so nothing is lost if
the player wanders off before resolving them.  The actual level-up
(banking XP and picking stats) happens on the level-up screen.

Buttons: Inventory, View Stats, Adventure (Phase 5, disabled),
Save & Exit.  Escape auto-saves and returns to the title screen.
"""

import pygame

from ..assets import AssetManager, HERO_COLS, HERO_ROWS
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT, max_xp_for
from ..savegame import save_player
from .screen import (
    QUIT, Screen, Button, font,
    BG_COLOR, PANEL_COLOR, TEXT_COLOR, DIM_TEXT, GOLD, BORDER_COLOR,
)

STATS = ("hp", "ap", "rap", "map", "dp", "rdp", "mdp")


def pending_levels(player) -> int:
    """How many level-ups the current xp would grant (pure, no mutation).

    Uses the >= semantics of Player.add_xp: reaching exactly max_xp
    counts as a level-up.
    """
    xp, lvl, ups = player.xp, player.lvl, 0
    while xp >= max_xp_for(lvl):
        xp -= max_xp_for(lvl)
        lvl += 1
        ups += 1
    return ups


class BaseScreen(Screen):
    name = "base"

    def __init__(self, screen, player):
        super().__init__(screen)
        self.player = player
        self.pending_ups = pending_levels(player)
        self.hot = None

        # Portrait: first idle frame of the hero sheet, scaled up 4x.
        frame = AssetManager().load_sheet(
            "player/hero_sheet.png", HERO_COLS, HERO_ROWS)[0]
        self.portrait = pygame.transform.scale(frame, (128, 128))

        x, w = 420, 340
        self.btn_inventory = Button("Inventory", (x, 120, w, 52))
        self.btn_stats = Button("View Stats", (x, 184, w, 52))
        self.btn_adventure = Button("Adventure", (x, 248, w, 52))
        self.btn_saveexit = Button("Save & Exit", (x, 312, w, 52))
        self.btn_choose = Button("Choose Stat", (x, 440, w, 52), size=28)

    # -- helpers ---------------------------------------------------------
    def _active_buttons(self):
        """Buttons that react to input; the rest are drawn disabled."""
        if self.pending_ups > 0:
            return [self.btn_choose]
        return [self.btn_inventory, self.btn_stats, self.btn_saveexit]

    def _hover(self, pos):
        for btn in self._active_buttons():
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def _save(self):
        save_player(self.player)

    # -- Screen hooks ------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self._save()
            return QUIT
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            btn = self._hover(event.pos)
            if btn is self.btn_choose:
                return ("level_up", {"player": self.player})
            if btn is self.btn_inventory:
                return ("inventory", {"player": self.player})
            if btn is self.btn_stats:
                return ("stats", {"player": self.player})
            if btn is self.btn_saveexit:
                self._save()
                return QUIT
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._save()
            return "title"
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        p = self.player

        header = font(32).render(
            f"Welcome in your Base, {p.name}.", True, GOLD)
        surface.blit(header, header.get_rect(midtop=(SCREEN_WIDTH // 2, 24)))

        # Left panel: portrait + summary.
        panel = pygame.Rect(30, 80, 330, 440)
        pygame.draw.rect(surface, PANEL_COLOR, panel, border_radius=8)
        pygame.draw.rect(surface, BORDER_COLOR, panel, width=2, border_radius=8)

        surface.blit(self.portrait, (45, 100))
        name = font(28).render(p.name, True, TEXT_COLOR)
        surface.blit(name, name.get_rect(midtop=(panel.centerx, 245)))
        lvl = font(22).render(f"Level {p.lvl}", True, DIM_TEXT)
        surface.blit(lvl, lvl.get_rect(midtop=(panel.centerx, 278)))

        # XP bar.
        bar = pygame.Rect(panel.centerx - 100, 305, 200, 12)
        pygame.draw.rect(surface, (15, 15, 20), bar, border_radius=6)
        if p.max_xp:
            fill = pygame.Rect(bar.x, bar.y,
                               int(bar.w * min(p.xp, p.max_xp) / p.max_xp),
                               bar.h)
            if fill.w >= 2:
                pygame.draw.rect(surface, GOLD, fill, border_radius=6)
        pygame.draw.rect(surface, BORDER_COLOR, bar, width=1, border_radius=6)
        xpt = font(18).render(f"XP {p.xp} / {p.max_xp}", True, DIM_TEXT)
        surface.blit(xpt, xpt.get_rect(midtop=(panel.centerx, 324)))

        # Stats in two columns.
        y0, rowh, cx = 365, 30, panel.centerx
        for i, stat in enumerate(STATS):
            col, row = divmod(i, 4)
            label = font(20).render(stat.upper(), True, DIM_TEXT)
            value = font(20).render(str(getattr(p, stat)), True, TEXT_COLOR)
            x = cx - 60 + col * 120
            surface.blit(label, label.get_rect(midright=(x, y0 + row * rowh)))
            surface.blit(value, value.get_rect(
                midleft=(x + 8, y0 + row * rowh)))
        wt = font(18).render(
            f"Weight {p.weight} / {p.max_weight}", True, DIM_TEXT)
        surface.blit(wt, wt.get_rect(midbottom=(panel.centerx, panel.bottom - 12)))

        # Right: menu buttons.
        active = set(map(id, self._active_buttons()))
        for btn in (self.btn_inventory, self.btn_stats,
                    self.btn_adventure, self.btn_saveexit):
            if id(btn) in active:
                btn.draw(surface, hot=(btn is self.hot))
            else:
                self._draw_disabled(surface, btn,
                                    "  (soon)" if btn is self.btn_adventure else "")
        if self.pending_ups > 0:
            note = font(26).render(
                f"LEVEL UP! ({self.pending_ups} pending)", True, GOLD)
            surface.blit(note, note.get_rect(
                midtop=(self.btn_choose.rect.centerx, 380)))
            self.btn_choose.draw(surface, hot=(self.btn_choose is self.hot))
        hint = font(18).render(
            "Esc: save & return to title", True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 20, SCREEN_HEIGHT - 14)))

    def _draw_disabled(self, surface, btn, suffix):
        """Draw a button in its inactive state (no input, dimmed)."""
        pygame.draw.rect(surface, (30, 30, 42), btn.rect, border_radius=6)
        pygame.draw.rect(surface, (60, 60, 80), btn.rect,
                         width=2, border_radius=6)
        text = font(btn.font_size).render(btn.label + suffix, True, DIM_TEXT)
        surface.blit(text, text.get_rect(center=btn.rect.center))
