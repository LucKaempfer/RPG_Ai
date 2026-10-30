# pygame_rpg/gui/journal_screen.py
"""The journal (from the Base): the prologue, every lost writing of
floors 1-LORE_FLOORS in story order (the ones not found yet show as
"? ? ?") and, once seen, the epilogue.  Enter or a tap rereads one in
the story reader, which comes back here; Escape returns to the Base.
"""

import pygame

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..lore import (LORE, CHAPTERS, EPILOGUE, EPILOGUE_TITLE, prologue)
from .effects import menu_key
from .screen import (
    QUIT, Screen, font,
    BG_COLOR, PANEL_COLOR, PANEL_HOT, TEXT_COLOR, DIM_TEXT, GOLD,
    BORDER_COLOR, FOCUS_BORDER,
)

ROW_H = 25
LIST = pygame.Rect(60, 96, SCREEN_WIDTH - 120, ROW_H * (len(LORE) + 2) + 12)


class JournalScreen(Screen):
    name = "journal"

    def __init__(self, screen, player):
        super().__init__(screen)
        self.player = player
        self.focus = 0
        self.rows = self._rows()

    def _rows(self):
        """(label, heading, title, pages or None if not found yet)."""
        found = set(self.player.lore)
        rows = [("Prologue", "Brackmoor", "Prologue", prologue(self.player.name))]
        for e in LORE:
            label = f"Floor {e.floor}: {e.title if e.id in found else '? ? ?'}"
            heading = f"Floor {e.floor}: {CHAPTERS[e.floor]}"
            rows.append((label, heading, e.title,
                         list(e.pages) if e.id in found else None))
        seen = "epilogue" in found
        rows.append(("Epilogue" if seen else "Epilogue: ? ? ?", "Brackmoor",
                     EPILOGUE_TITLE, list(EPILOGUE) if seen else None))
        return rows

    @property
    def found_count(self) -> int:
        return sum(1 for e in LORE if e.id in self.player.lore)

    def open(self, index):
        """Reread row ``index``; a transition, or None if not found yet."""
        _, heading, title, pages = self.rows[index]
        if pages is None:
            return None
        return ("story", {"title": title, "pages": pages, "heading": heading,
                          "return_to": self})

    def _row_rect(self, i):
        return pygame.Rect(LIST.x + 6, LIST.y + 6 + i * ROW_H, LIST.w - 12, ROW_H - 2)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return QUIT
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return ("base", {"player": self.player})
        if event.type == pygame.KEYDOWN:
            self.focus, activate = menu_key(event, len(self.rows), self.focus)
            if activate:
                return self.open(self.focus)
        elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            for i in range(len(self.rows)):
                if self._row_rect(i).collidepoint(event.pos):
                    self.focus = i
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        return self.open(i)
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        title = font(40).render("Journal", True, GOLD)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 40)))
        count = font(20).render(
            f"Writings found: {self.found_count} / {len(LORE)}", True, DIM_TEXT)
        surface.blit(count, count.get_rect(center=(SCREEN_WIDTH // 2, 76)))
        pygame.draw.rect(surface, PANEL_COLOR, LIST, border_radius=8)
        pygame.draw.rect(surface, BORDER_COLOR, LIST, width=2, border_radius=8)
        for i, (label, _, _, pages) in enumerate(self.rows):
            rect = self._row_rect(i)
            if i == self.focus:
                pygame.draw.rect(surface, PANEL_HOT, rect, border_radius=4)
                pygame.draw.rect(surface, FOCUS_BORDER, rect, width=1, border_radius=4)
            img = font(22).render(label, True, TEXT_COLOR if pages else DIM_TEXT)
            surface.blit(img, img.get_rect(midleft=(rect.x + 12, rect.centery)))
        hint = font(18).render("Up/Down + Enter or tap: read    Esc: back to the Base",
                               True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 20, SCREEN_HEIGHT - 14)))
