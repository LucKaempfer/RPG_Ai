# pygame_rpg/gui/story_screen.py
"""Paged story reader: the prologue after the hero is made, a lost
writing picked up in the dungeon, the epilogue, or an entry reopened
from the journal (``lore.py`` holds the text).

The text sits on a parchment page, wrapped to fit; "\\n" in a page
starts a new paragraph.  Left / Right (or Back / Next) turn the pages,
Enter / Space go on, Escape (B on a phone) closes it at once.  When it
closes it goes to ``next`` (a transition request), or back to the
``return_to`` screen that is still alive (a dungeon floor, the
journal), which also saves if the window closes or the app goes to the
background meanwhile.
"""

import pygame

from .. import audio
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from .inventory_screen import _wrap
from .screen import QUIT, Screen, Button, BG_COLOR, DIM_TEXT, GOLD, font

PAGE = pygame.Rect(70, 112, SCREEN_WIDTH - 140, 362)
PARCHMENT = (226, 210, 172)
PARCHMENT_EDGE = (150, 120, 76)
INK = (52, 38, 26)
TEXT_SIZE = 28
LINE_H = 30
PARAGRAPH_GAP = 10
MARGIN = 34


def layout(text, width=PAGE.w - 2 * MARGIN):
    """A page's text as lines that fit ``width`` ("" marks a paragraph
    break)."""
    lines = []
    for i, para in enumerate(text.split("\n")):
        if i:
            lines.append("")
        lines.extend(_wrap(para, TEXT_SIZE, width))
    return lines


class StoryScreen(Screen):
    name = "story"

    def __init__(self, screen, title, pages, next=None, heading="",
                 return_to=None):
        super().__init__(screen)
        self.title = title
        self.heading = heading                  # small line above the title
        self.pages = [layout(p) for p in pages] or [[]]
        self.page = 0
        self.return_to = return_to
        self.next_screen = (("resume", {"screen": return_to})
                            if return_to is not None else next)
        cx = SCREEN_WIDTH // 2
        bottom = SCREEN_HEIGHT - 92
        self.btn_back = Button("Back", (cx - 320, bottom, 160, 44))
        self.btn_skip = Button("Close", (cx - 80, bottom, 160, 44))
        self.btn_next = Button("Next", (cx + 160, bottom, 160, 44))
        self.hot = None
        self.ambience = getattr(return_to, "ambience", None)

    def _last(self) -> bool:
        return self.page >= len(self.pages) - 1

    def _turn(self, step):
        page = max(0, min(len(self.pages) - 1, self.page + step))
        if page != self.page:
            self.page = page
            audio.play("click", volume=0.5)

    def _advance(self):
        if self._last():
            return self.next_screen
        self._turn(1)
        return None

    def suspend(self):
        if self.return_to is not None:
            self.return_to.suspend()

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.suspend()
            return QUIT
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            btn = self._hover(event.pos)
            if btn is self.btn_back:
                self._turn(-1)
            elif btn is self.btn_next:
                return self._advance()
            elif btn is self.btn_skip:
                return self.next_screen
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_RETURN):
                return self._advance()
            if event.key == pygame.K_LEFT:
                self._turn(-1)
            elif event.key == pygame.K_ESCAPE:
                return self.next_screen
        return None

    def _hover(self, pos):
        for btn in (self.btn_back, self.btn_skip, self.btn_next):
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        if self.heading:
            head = font(22).render(self.heading, True, DIM_TEXT)
            surface.blit(head, head.get_rect(center=(SCREEN_WIDTH // 2, 42)))
        title = font(40).render(self.title, True, GOLD)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 76)))

        # The parchment: a soft shadow, the sheet, a darker rim.
        pygame.draw.rect(surface, (10, 10, 14), PAGE.move(5, 6), border_radius=8)
        pygame.draw.rect(surface, PARCHMENT, PAGE, border_radius=8)
        pygame.draw.rect(surface, PARCHMENT_EDGE, PAGE, width=3, border_radius=8)
        pygame.draw.rect(surface, (205, 186, 144), PAGE.inflate(-14, -14),
                         width=1, border_radius=6)
        f = font(TEXT_SIZE)
        y = PAGE.top + MARGIN - 6
        for line in self.pages[self.page]:
            if not line:
                y += PARAGRAPH_GAP
                continue
            surface.blit(f.render(line, True, INK), (PAGE.x + MARGIN, y))
            y += LINE_H

        if self.page > 0:
            self.btn_back.draw(surface, hot=(self.hot is self.btn_back))
        self.btn_skip.draw(surface, hot=(self.hot is self.btn_skip))
        self.btn_next.label = "Continue" if self._last() else "Next"
        self.btn_next.draw(surface, hot=(self.hot is self.btn_next))
        count = font(20).render(
            f"{self.page + 1} / {len(self.pages)}", True, DIM_TEXT)
        surface.blit(count, count.get_rect(
            center=(SCREEN_WIDTH // 2, PAGE.bottom + 18)))
