# pygame_rpg/gui/stats_screen.py
"""Stats screen: read-only detail view of a character.

Mirrors the V3 xp_check() display: each stat's effective value (base +
equipment bonus) plus how many times it was already raised by level-ups.  Nothing is mutated
here — the player is only ever handed back to the Base.
"""

import pygame

from ..classes import class_name
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..player import UPGRADABLE_STATS
from ..savegame import save_player
from ..stat_names import LABEL, ABOUT
from .inventory_screen import _wrap
from .screen import (
    draw_bar, draw_background, draw_panel, QUIT, Screen, Button, font,
    TEXT_COLOR, DIM_TEXT, GOLD,
)

# Combat stats shown in the grid (attacks left, defenses right); hp
# gets its own row.
GRID_STATS = tuple(s for s in UPGRADABLE_STATS if s != "hp")
GRID_ROWS = 3


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
        draw_background(surface)
        p = self.player
        header = font(32).render(f"Stats - {p.name}", True, GOLD)
        surface.blit(header,
                     header.get_rect(midtop=(SCREEN_WIDTH // 2, 24)))
        panel = pygame.Rect(30, 76, 740, 470)
        draw_panel(surface, panel, radius=8)

        lvl = font(26).render(f"Level {p.lvl} {class_name(p)}", True, TEXT_COLOR)
        surface.blit(lvl, lvl.get_rect(midtop=(panel.centerx, 100)))
        bar = pygame.Rect(panel.centerx - 150, 140, 300, 12)
        draw_bar(surface, bar, p.xp, p.max_xp, GOLD)
        xpt = font(20).render(f"XP {p.xp} / {p.max_xp}", True, DIM_TEXT)
        surface.blit(xpt, xpt.get_rect(midtop=(panel.centerx, 160)))

        hpt = font(24).render(
            f"{LABEL['hp']} {p.current_hp} / {p.max_hp}   "
            f"(base {p.hp}{_bonus_text(p, 'hp')}, "
            f"raised {p.lvl_up_counts.get('hp', 0)}x)"
            f"     {LABEL['mp']} {p.current_mp} / {p.max_mp}",
            True, TEXT_COLOR)
        surface.blit(hpt, hpt.get_rect(midtop=(panel.centerx, 196)))

        # Attack stats on the left, the matching defenses on the right:
        # name and value, what it does, where the value comes from.
        y0 = 236
        for i, stat in enumerate(GRID_STATS):
            col, row = divmod(i, GRID_ROWS)
            x = panel.x + 24 + col * 362
            y = y0 + row * 76
            label = font(24).render(LABEL[stat], True, TEXT_COLOR)
            surface.blit(label, (x, y))
            val = font(24).render(str(p.total(stat)), True, GOLD)
            surface.blit(val, (x + 170, y))
            for j, line in enumerate(_wrap(ABOUT[stat], 17, 330)[:2]):
                surface.blit(font(17).render(line, True, DIM_TEXT),
                             (x, y + 22 + j * 15))
            src = font(17).render(
                f"base {getattr(p, stat)}"
                + (f", +{p.bonus(stat)} from gear" if p.bonus(stat) else "")
                + f", raised {p.lvl_up_counts.get(stat, 0)}x",
                True, (130, 130, 150))
            surface.blit(src, (x, y + 54))

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
