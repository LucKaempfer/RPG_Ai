# pygame_rpg/gui/title_screen.py
"""Title screen: logo + New Hero / Saved Heroes / Settings / Exit.

The logo is drawn in code (outlined title, crossed swords, rising
embers) so it needs no asset file.  Mouse or keyboard (Up / Down +
Enter, Esc quits).

Port of the V3 start() prompt ("New or Saved Hero?").  Both hero routes
go through the tutorial screen first (V3 order: tutorial -> start),
carrying a ``next`` kwarg that the tutorial uses for its final route.
"""

import math

import pygame

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from .screen import (
    Screen, Button, QUIT,
    BG_COLOR, TEXT_COLOR, DIM_TEXT, GOLD, font,
)
from .effects import Particles, menu_key

EMBER = (240, 140, 60)
STEEL, HILT = (200, 205, 220), (150, 100, 50)

TITLE = "Dungeon RPG"
SUBTITLE = "a roguelike dungeon battler"


class TitleScreen(Screen):
    name = "title"

    def __init__(self, screen):
        super().__init__(screen)
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        self.buttons = [
            Button("New Hero", (cx - 130, cy - 40, 260, 48)),
            Button("Saved Heroes", (cx - 130, cy + 24, 260, 48)),
            Button("Settings", (cx - 130, cy + 88, 260, 48)),
            Button("Exit", (cx - 130, cy + 152, 260, 48)),
        ]
        self.hot = None
        self.focus = None
        self.t = 0.0
        self.fx = Particles()
        self.ember_t = 0.0

    def handle_event(self, event):
        request = super().handle_event(event)
        if request is not None:
            return request
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._press(self._hover(event.pos))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return QUIT
        elif event.type == pygame.KEYDOWN:
            self.focus, activate = menu_key(event, len(self.buttons), self.focus)
            if self.focus is not None:
                self.hot = self.buttons[self.focus]
            if activate:
                return self._press(self.buttons[self.focus])
        return None

    def _press(self, btn):
        if btn is self.buttons[0]:
            return ("tutorial", {"next": "hero_maker"})
        if btn is self.buttons[1]:
            return ("tutorial", {"next": "hero_chooser"})
        if btn is self.buttons[2]:
            return ("settings", {"return_to": self})
        if btn is self.buttons[3]:
            return QUIT
        return None

    def handle_update(self, dt):
        self.t += dt
        self.fx.update(dt)
        # A slow trickle of embers rising past the logo.
        self.ember_t += dt
        while self.ember_t > 0.12:
            self.ember_t -= 0.12
            x = self.fx.rng.uniform(80, SCREEN_WIDTH - 80)
            self.fx.items.append([x, 240, self.fx.rng.uniform(-15, 15),
                                  self.fx.rng.uniform(-90, -50), 0.0,
                                  self.fx.rng.uniform(1.2, 2.0), EMBER, 2])

    def _hover(self, pos):
        for btn in self.buttons:
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        self.fx.draw(surface)
        cx = SCREEN_WIDTH // 2
        # A sword on each side of the title, pointing up.
        for side in (-1, 1):
            x = cx + side * 300
            pygame.draw.line(surface, STEEL, (x, 105), (x, 185), 6)
            pygame.draw.polygon(surface, STEEL, [(x - 3, 105), (x, 95), (x + 3, 105)])
            pygame.draw.line(surface, HILT, (x - 14, 185), (x + 14, 185), 6)
            pygame.draw.line(surface, HILT, (x, 185), (x, 205), 5)
        # Outlined title with a slow golden pulse.
        pulse = 0.85 + 0.15 * math.sin(self.t * 2)
        color = tuple(int(c * pulse) for c in GOLD)
        text = font(72).render(TITLE, True, color)
        outline = font(72).render(TITLE, True, (20, 15, 10))
        rect = text.get_rect(center=(cx, 160))
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (3, 4)):
            surface.blit(outline, rect.move(dx, dy))
        surface.blit(text, rect)
        sub = font(28).render(SUBTITLE, True, DIM_TEXT)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 225)))
        for btn in self.buttons:
            btn.draw(surface, hot=(btn is self.hot))
