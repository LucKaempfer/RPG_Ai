# pygame_rpg/gui/level_up_screen.py
"""Level-up screen: bank pending level-ups, one stat pick at a time.

Mirrors V3 xp_check(): for every pending level the player chooses one
stat to raise by +LEVEL_UP_BONUS.  Each pick banks exactly one level
(one iteration of Player.add_xp's while-loop): the xp pool loses
max_xp_for(old level), the level rises, then apply_level_up() grants
the bonus.  When no level-ups remain, the screen returns to the Base
(or to the dungeon floor in ``return_to``).  Mouse or keyboard (Up /
Down + Enter); each pick bursts gold sparks from its button.
"""

import pygame

from .. import audio
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT, MP_PER_LEVEL, max_xp_for
from ..player import UPGRADABLE_STATS
from ..savegame import save_player
from ..stat_names import LABEL, ABOUT
from .inventory_screen import _wrap
from .base_screen import pending_levels
from .effects import Particles, menu_key
from .screen import (
    draw_background, QUIT, Screen, Button, font, TEXT_COLOR, DIM_TEXT, GOLD,
)


class LevelUpScreen(Screen):
    name = "level_up"

    @property
    def ambience(self):
        """Keep the dungeon's ambience going when opened from a floor."""
        return getattr(self.return_to, "ambience", None)

    def __init__(self, screen, player, return_to=None):
        super().__init__(screen)
        self.player = player
        # Screen to resume when done (the dungeon, mid-run); None = Base.
        self.return_to = return_to
        self.hot = None
        self.focus = None
        self.fx = Particles()
        # Fanfare on arrival: the header pulses and sparks fly.
        self.glow_t = 0.8
        self.fx.burst(SCREEN_WIDTH // 2, 44, GOLD, count=30, speed=200)
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
                f"{LABEL[stat]}  {getattr(p, stat)}  "
                f"(raised {p.lvl_up_counts.get(stat, 0)}x)")

    def _bank(self, stat):
        """Bank one level into ``stat`` (one add_xp loop iteration)."""
        p = self.player
        p.xp -= max_xp_for(p.lvl)
        p.lvl += 1
        p.restore_mp(MP_PER_LEVEL)  # max MP grew; so does what is left
        p.apply_level_up(stat)
        self._refresh_labels()
        self.fx.burst(*self.stat_buttons[stat].rect.center, GOLD, count=24)
        self.glow_t = 0.6
        audio.play("level_up")

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            save_player(self.player)
            return QUIT
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._pick(self._hover(event.pos))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return self._leave()
        elif event.type == pygame.KEYDOWN:
            buttons = list(self.stat_buttons.values())
            self.focus, activate = menu_key(event, len(buttons), self.focus)
            if self.focus is not None:
                self.hot = buttons[self.focus]
            if activate:
                return self._pick(buttons[self.focus])
        return None

    def _pick(self, btn):
        if btn is None or pending_levels(self.player) <= 0:
            return None
        stat = next(s for s, b in self.stat_buttons.items() if b is btn)
        self._bank(stat)
        if pending_levels(self.player) == 0:
            return self._leave()
        return None

    def handle_update(self, dt):
        self.fx.update(dt)
        self.glow_t = max(0.0, self.glow_t - dt)

    def _leave(self):
        if self.return_to is not None:
            return ("resume", {"screen": self.return_to})
        return ("base", {"player": self.player})

    def _hover(self, pos):
        for btn in self.stat_buttons.values():
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def draw(self, surface):
        draw_background(surface)
        p = self.player
        ups = pending_levels(p)
        header = font(32 + int(16 * self.glow_t)).render("LEVEL UP!", True, GOLD)
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
        # What each stat does, beside its button (readable on touch
        # screens too, where nothing hovers).
        for stat, btn in self.stat_buttons.items():
            color = TEXT_COLOR if btn is self.hot else DIM_TEXT
            lines = _wrap(ABOUT[stat], 17, 370)[:2]
            y = btn.rect.centery - 8 * len(lines)
            for line in lines:
                img = font(17).render(line, True, color)
                surface.blit(img, img.get_rect(topright=(btn.rect.x - 14, y)))
                y += 16
        self.fx.draw(surface)
        hint = font(18).render(
            "Pick a stat to raise (+1), mouse or Up/Down + Enter.  Esc: "
            + ("back to the dungeon" if self.return_to else "back to base"),
            True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 20, SCREEN_HEIGHT - 14)))
