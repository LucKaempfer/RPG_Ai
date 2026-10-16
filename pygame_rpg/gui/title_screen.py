# pygame_rpg/gui/title_screen.py
"""Title screen: logo + New Hero / Saved Heroes / Exit.

Port of the V3 start() prompt ("New or Saved Hero?").  Both hero routes
go through the tutorial screen first (V3 order: tutorial -> start),
carrying a ``next`` kwarg that the tutorial uses for its final route.
"""

import pygame

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from .screen import (
    Screen, Button, QUIT,
    BG_COLOR, TEXT_COLOR, DIM_TEXT, GOLD, font,
)

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
            Button("Exit", (cx - 130, cy + 88, 260, 48)),
        ]
        self.hot = None

    def handle_event(self, event):
        request = super().handle_event(event)
        if request is not None:
            return request
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            btn = self._hover(event.pos)
            if btn is self.buttons[0]:
                return ("tutorial", {"next": "hero_maker"})
            if btn is self.buttons[1]:
                return ("tutorial", {"next": "hero_chooser"})
            if btn is self.buttons[2]:
                return QUIT
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return QUIT
        return None

    def _hover(self, pos):
        for btn in self.buttons:
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        logo = font(72).render(TITLE, True, GOLD)
        surface.blit(logo, logo.get_rect(center=(SCREEN_WIDTH // 2, 180)))
        sub = font(28).render(SUBTITLE, True, DIM_TEXT)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 240)))
        for btn in self.buttons:
            btn.draw(surface, hot=(btn is self.hot))
