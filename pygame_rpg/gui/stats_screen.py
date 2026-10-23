# pygame_rpg/gui/stats_screen.py
"""Stats screen: read-only detail view of a character.

Mirrors the V3 xp_check() display: each stat's effective value (base +
equipment bonus) plus how many times it was already raised by level-ups.  Nothing is mutated
here — the player is only ever handed back to the Base.
"""

import pygame

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..player import UPGRADABLE_STATS
from ..savegame import save_player
from .screen import (
    QUIT, Screen, Button, font,
    BG_COLOR, PANEL_COLOR, TEXT_COLOR, DIM_TEXT, GOLD, BORDER_COLOR,
)

# Combat stats shown in the grid; hp gets its own row.
GRID_STATS = tuple(s for s in UPGRADABLE_STATS if s != "hp")
GRID_COLS = 3


def _bonus_text(player, stat) -> str:
    """" +N" for a stat's equipment bonus, or "" when there is none."""
    bonus = player.bonus(stat)
    return f" +{bonus}" if bonus else ""


class StatsScreen(Screen):
    name = "stats"

    def __init__(self, screen, player):
        super().__init__(screen)
        self.player = player
        self.hot = None
        x, w = 420, 340
        self.btn_back = Button("Back to Base", (x, 480, w, 52))

    def _save(self):
        save_player(self.player)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self._save()
            return QUIT
        if event.type == pygame.MOUSEMOTION:
            self.hot = (self.btn_back if
                        self.btn_back.rect.collidepoint(event.pos) else None)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.btn_back.rect.collidepoint(event.pos):
                return ("base", {"player": self.player})
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return ("base", {"player": self.player})
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        p = self.player
        header = font(32).render(f"Stats - {p.name}", True, GOLD)
        surface.blit(header,
                     header.get_rect(midtop=(SCREEN_WIDTH // 2, 24)))
        panel = pygame.Rect(30, 76, 740, 470)
        pygame.draw.rect(surface, PANEL_COLOR, panel, border_radius=8)
        pygame.draw.rect(surface, BORDER_COLOR, panel, width=2, border_radius=8)

        lvl = font(26).render(f"Level {p.lvl}", True, TEXT_COLOR)
        surface.blit(lvl, lvl.get_rect(midtop=(panel.centerx, 100)))
        bar = pygame.Rect(panel.centerx - 150, 140, 300, 12)
        pygame.draw.rect(surface, (15, 15, 20), bar, border_radius=6)
        if p.max_xp:
            fill = pygame.Rect(bar.x, bar.y,
                               int(bar.w * min(p.xp, p.max_xp) / p.max_xp),
                               bar.h)
            if fill.w >= 2:
                pygame.draw.rect(surface, GOLD, fill, border_radius=6)
        pygame.draw.rect(surface, BORDER_COLOR, bar, width=1, border_radius=6)
        xpt = font(20).render(f"XP {p.xp} / {p.max_xp}", True, DIM_TEXT)
        surface.blit(xpt, xpt.get_rect(midtop=(panel.centerx, 160)))

        hpt = font(24).render(
            f"HP {p.current_hp} / {p.max_hp}   "
            f"(base {p.hp}{_bonus_text(p, 'hp')}, "
            f"raised {p.lvl_up_counts.get('hp', 0)}x)",
            True, TEXT_COLOR)
        surface.blit(hpt, hpt.get_rect(midtop=(panel.centerx, 205)))

        y0 = 250
        for i, stat in enumerate(GRID_STATS):
            col, row = divmod(i, GRID_COLS)
            x = panel.centerx - 240 + col * 240
            y = y0 + row * 75
            label = font(24).render(stat.upper(), True, TEXT_COLOR)
            surface.blit(label, label.get_rect(midtop=(x, y)))
            val = font(20).render(
                f"{p.total(stat)}   ({getattr(p, stat)}"
                f"{_bonus_text(p, stat)}, "
                f"raised {p.lvl_up_counts.get(stat, 0)}x)",
                True, DIM_TEXT)
            surface.blit(val, val.get_rect(midtop=(x, y + 34)))

        wt = font(20).render(
            f"Weight {p.weight} / {p.max_weight}", True, DIM_TEXT)
        # Left of the Back button, which covers the panel's lower right.
        surface.blit(wt, wt.get_rect(midleft=(panel.x + 24,
                                              self.btn_back.rect.centery)))
        self.btn_back.draw(surface, hot=(self.btn_back is self.hot))
        hint = font(18).render(
            "Esc / Back: return to base", True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 20, SCREEN_HEIGHT - 14)))
