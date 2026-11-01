# pygame_rpg/gui/fountain_screen.py
"""Fountain screen: the floor's healing fountain offers one gift.

Two choices (``special_rooms.fountain_potion`` / ``fountain_heal``):

* Fill a flask: a Health Potion of the floor's tier goes into the
  backpack (greyed out when it is too heavy to carry).
* Drink: heal 50% of max HP (greyed out at full HP).

Picking one uses the fountain up for the floor (``DungeonScreen.
use_fountain``) and returns to the dungeon; Leave (or Esc / the touch B
button) goes back without using it.  Mouse / tap, or Up / Down + Enter
(the touch D-pad and A).
"""

import math

import pygame

from .. import audio
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT, FOUNTAIN_HEAL_PERCENT
from ..savegame import save_player
from .effects import Particles, menu_key
from .screen import (
    draw_background, QUIT, Screen, Button, font, TEXT_COLOR,
    DIM_TEXT, GOLD,
)

WATER = (90, 170, 240)
CHOICES = ("potion", "heal", "leave")


class FountainScreen(Screen):
    name = "fountain"

    @property
    def ambience(self):
        """Keep the dungeon's ambience going."""
        return getattr(self.return_to, "ambience", None)

    def __init__(self, screen, player, return_to):
        super().__init__(screen)
        self.player = player
        self.return_to = return_to      # the DungeonScreen (owns the rules)
        self.t = 0.0
        self.fx = Particles()
        x, w = SCREEN_WIDTH // 2 - 230, 460
        self.buttons = {
            "potion": Button("", (x, 250, w, 60), size=22),
            "heal": Button("", (x, 330, w, 60), size=22),
            "leave": Button("Leave", (x, 430, w, 46), size=22),
        }
        self.hot = None
        self.focus = None
        self._refresh()

    def _refresh(self):
        potion, fits, heal = self.return_to.fountain_options()
        self.enabled = {"potion": fits, "heal": heal > 0, "leave": True}
        self.buttons["potion"].label = f"Fill a flask: {potion.name}"
        self.buttons["heal"].label = f"Drink: heal {FOUNTAIN_HEAL_PERCENT}% of max HP"
        self.notes = {
            "potion": (f"Restores {potion.heal} HP when used." if fits
                       else "Too heavy to carry: make room first."),
            "heal": (f"+{heal} HP now  (HP {self.player.current_hp} / {self.player.max_hp})"
                     if heal > 0 else "You are already at full HP."),
        }

    # -- events ------------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            save_player(self.player)
            self.return_to.save_run()
            return QUIT
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._pick(self._hover(event.pos))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return self._leave()
        elif event.type == pygame.KEYDOWN:
            self.focus, activate = menu_key(event, len(CHOICES), self.focus)
            if self.focus is not None:
                self.hot = CHOICES[self.focus]
            if activate:
                return self._pick(CHOICES[self.focus])
        return None

    def _hover(self, pos):
        return next((k for k, b in self.buttons.items() if b.rect.collidepoint(pos)), None)

    def _pick(self, choice):
        if choice is None:
            return None
        if choice == "leave":
            return self._leave()
        if not self.enabled[choice]:
            audio.play("miss", volume=0.5)
            return None
        if not self.return_to.use_fountain(choice):
            return None
        audio.play("chest" if choice == "potion" else "level_up", volume=0.7)
        return self._leave()

    def _leave(self):
        return ("resume", {"screen": self.return_to})

    # -- Screen hooks --------------------------------------------------------
    def handle_update(self, dt):
        self.t += dt
        self.fx.update(dt)
        if int(self.t * 8) != int((self.t - dt) * 8):      # a few droplets
            self.fx.burst(SCREEN_WIDTH // 2, 150, WATER, count=2, speed=60,
                          life=0.6, size=2)

    def draw(self, surface):
        draw_background(surface)
        cx = SCREEN_WIDTH // 2
        title = font(34).render("Healing Fountain", True, GOLD)
        surface.blit(title, title.get_rect(midtop=(cx, 34)))
        sub = font(20).render("Clear water wells up from the old stone. "
                              "It will give one gift, then run dry.", True, DIM_TEXT)
        surface.blit(sub, sub.get_rect(midtop=(cx, 82)))
        # The basin, gently rippling.
        r = 3 * math.sin(self.t * 3)
        pygame.draw.ellipse(surface, (70, 72, 80), (cx - 90, 150, 180, 70))
        pygame.draw.ellipse(surface, (122, 124, 130), (cx - 90, 142, 180, 66))
        pygame.draw.ellipse(surface, WATER, (cx - 72, 154, 144, 40))
        pygame.draw.ellipse(surface, (200, 236, 255),
                            (cx - 40 - r, 164 - r / 3, 80 + 2 * r, 20 + r), 1)
        self.fx.draw(surface)

        for key, btn in self.buttons.items():
            on = self.enabled[key]
            btn.draw(surface, hot=(key == self.hot and on))
            if not on:      # grey out what can't be picked
                shade = pygame.Surface(btn.rect.size, pygame.SRCALPHA)
                shade.fill((10, 10, 16, 140))
                surface.blit(shade, btn.rect)
            if key in self.notes:
                color = TEXT_COLOR if key == self.hot and on else DIM_TEXT
                img = font(17).render(self.notes[key], True, color)
                surface.blit(img, img.get_rect(midtop=(cx, btn.rect.bottom + 2)))

        hint = font(18).render("Tap a choice, or Up/Down + Enter.  Esc: leave it for later",
                               True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(SCREEN_WIDTH - 20, SCREEN_HEIGHT - 14)))
