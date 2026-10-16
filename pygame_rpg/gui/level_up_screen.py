# pygame_rpg/gui/level_up_screen.py
"""Level-up screen: bank pending level-ups, one stat pick at a time.

Mirrors V3 xp_check(): for every pending level the player chooses one
stat to raise by +LEVEL_UP_BONUS.  Each pick banks exactly one level
(one iteration of Player.add_xp's while-loop): the xp pool loses
max_xp_for(old level), the level rises, then apply_level_up() grants
the bonus.  When no level-ups remain, the screen returns to the Base.
"""

import pygame

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT, max_xp_for
from ..player import UPGRADABLE_STATS
from ..savegame import save_player
from .base_screen import pending_levels
from .screen import (
    QUIT, Screen, Button, font,
    BG_COLOR, PANEL_COLOR, TEXT_COLOR, DIM_TEXT, GOLD, BORDER_COLOR,
)


class LevelUpScreen(Screen):
    name = "level_up"

    def __init__(self, screen, player):
        super().__init__(screen)
        self.player = player
        self.hot = None
        self.stat_buttons = {}
        x, w, y = 420, 340, 120
        for i, stat in enumerate(UPGRADABLE_STATS):
            btn = Button("", (x, y + i * 52, w, 46))
            self.stat_buttons[stat] = btn
        self._refresh_labels()

    def _refresh_labels(self):
        p = self.player
        for stat, btn in self.stat_buttons.items():
            btn.label = (
                f"{stat.upper()}  {getattr(p, stat)}  "
                f"(raised {p.lvl_up_counts.get(stat, 0)}x)")

    def _bank(self, stat):
        """Bank one level into ``stat`` (one add_xp loop iteration)."""
        p = self.player
        p.xp -= max_xp_for(p.lvl)
        p.lvl += 1
        p.apply_level_up(stat)
        self._refresh_labels()

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            save_player(self.player)
            return QUIT
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            btn = self._hover(event.pos)
            if btn is None or pending_levels(self.player) <= 0:
                return None
            stat = next(s for s, b in self.stat_buttons.items()
                        if b is btn)
            self._bank(stat)
            if pending_levels(self.player) == 0:
                return ("base", {"player": self.player})
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return ("base", {"player": self.player})
        return None

    def _hover(self, pos):
        for btn in self.stat_buttons.values():
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        p = self.player
        ups = pending_levels(p)
        header = font(32).render("LEVEL UP!", True, GOLD)
        surface.blit(header, header.get_rect(midtop=(SCREEN_WIDTH // 2, 24)))
        plural = "s" if ups != 1 else ""
        note = font(24).render(
            f"{ups} level-up{plural} pending", True, TEXT_COLOR)
        surface.blit(note, note.get_rect(midtop=(SCREEN_WIDTH // 2, 66)))
        xpt = font(20).render(
            f"XP {p.xp} / {p.max_xp}   Level {p.lvl}", True, DIM_TEXT)
        surface.blit(xpt, xpt.get_rect(midtop=(SCREEN_WIDTH // 2, 96)))
        for btn in self.stat_buttons.values():
            btn.draw(surface, hot=(btn is self.hot))
        hint = font(18).render(
            "Pick a stat to raise (+1).  Esc: back to base", True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 20, SCREEN_HEIGHT - 14)))
