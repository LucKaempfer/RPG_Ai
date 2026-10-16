# pygame_rpg/gui/tutorial_screen.py
"""Paginated tutorial screen.

Renders RPG_V3/tutorial.txt, one paragraph per page (paragraphs are the
blank-line blocks in the file).  Skippable every run: "Skip" (or ESC)
jumps straight to the screen this run is headed for.
"""

import re
from pathlib import Path

import pygame

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from .screen import (
    Screen, Button,
    BG_COLOR, PANEL_COLOR, TEXT_COLOR, DIM_TEXT, GOLD,
    BORDER_COLOR, font,
)

_TUTORIAL_PATH = (
    Path(__file__).resolve().parents[2] / "RPG_V3" / "tutorial.txt"
)
_FALLBACK_PAGES = [
    ["Open RPG_V3/tutorial.txt for the full tutorial."],
]


def load_pages() -> list:
    """Return the tutorial as a list of pages (list of text lines)."""
    try:
        text = _TUTORIAL_PATH.read_text(encoding="utf-8")
    except OSError:
        return _FALLBACK_PAGES
    pages = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if lines:
            pages.append(lines)
    return pages or _FALLBACK_PAGES


class TutorialScreen(Screen):
    name = "tutorial"

    def __init__(self, screen, next: str = "hero_maker"):
        super().__init__(screen)
        self.next_screen = next
        self.pages = load_pages()
        self.page = 0
        cx = SCREEN_WIDTH // 2
        bottom = SCREEN_HEIGHT - 90
        self.btn_back = Button("Back", (cx - 320, bottom, 160, 44))
        self.btn_skip = Button("Skip", (cx - 80, bottom, 160, 44))
        self.btn_next = Button("Next", (cx + 160, bottom, 160, 44))
        self.hot = None

    def _last(self) -> bool:
        return self.page >= len(self.pages) - 1

    def handle_event(self, event):
        request = super().handle_event(event)
        if request is not None:
            return request
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            btn = self._hover(event.pos)
            if btn is self.btn_back and self.page > 0:
                self.page -= 1
            elif btn is self.btn_next:
                req = self._advance()
                if req:
                    return req
            elif btn is self.btn_skip:
                return self.next_screen
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_RETURN):
                req = self._advance()
                if req:
                    return req
            elif event.key == pygame.K_LEFT and self.page > 0:
                self.page -= 1
            elif event.key == pygame.K_ESCAPE:
                return self.next_screen
        return None

    def _advance(self):
        if self._last():
            return self.next_screen
        self.page += 1

    def _hover(self, pos):
        for btn in (self.btn_back, self.btn_skip, self.btn_next):
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        title = font(40).render("Tutorial", True, GOLD)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 70)))

        # Page text panel
        panel = pygame.Rect(60, 110, SCREEN_WIDTH - 120, 340)
        pygame.draw.rect(surface, PANEL_COLOR, panel, border_radius=10)
        pygame.draw.rect(surface, BORDER_COLOR, panel, width=2,
                         border_radius=10)
        f = font(26)
        y = panel.top + 30
        for line in self.pages[self.page]:
            surface.blit(f.render(line, True, TEXT_COLOR),
                         (panel.x + 40, y))
            y += 34

        self.btn_back.draw(surface, hot=(self.hot is self.btn_back))
        self.btn_skip.draw(surface, hot=(self.hot is self.btn_skip))
        label = "Start" if self._last() else "Next"
        self.btn_next.label = label
        self.btn_next.draw(surface, hot=(self.hot is self.btn_next))
        count = font(20).render(
            f"{self.page + 1} / {len(self.pages)}", True, DIM_TEXT)
        surface.blit(count, count.get_rect(
            center=(SCREEN_WIDTH // 2, panel.bottom + 22)))
