# pygame_rpg/gui/journal_screen.py
"""The journal (from the Base): the prologue, every lost writing of
floors 1-LORE_FLOORS in story order, each floor followed by what its
miniboss left behind (the ones not found yet show as "? ? ?") and,
once seen, the epilogue.  Enter or a tap rereads one in the story
reader, which comes back here; Escape returns to the Base.  The list
scrolls with the focus (arrows / D-pad) or the mouse wheel.
"""

import pygame

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..lore import (LORE, MINIBOSS_LORE, CHAPTERS, EPILOGUE, EPILOGUE_TITLE,
                    prologue)
from .effects import menu_key
from .screen import (
    draw_background, draw_panel, QUIT, Screen, font,
    PANEL_HOT, TEXT_COLOR, DIM_TEXT, GOLD, FOCUS_BORDER,
)

ROW_H = 25
VISIBLE_ROWS = 17
LIST = pygame.Rect(60, 96, SCREEN_WIDTH - 120, ROW_H * VISIBLE_ROWS + 12)
# Every writing in journal order: each floor's, then its miniboss's.
WRITINGS = [e for f in sorted({e.floor for e in LORE})
            for e in ([x for x in LORE if x.floor == f]
                      + ([MINIBOSS_LORE[f]] if f in MINIBOSS_LORE else []))]


class JournalScreen(Screen):
    name = "journal"

    def __init__(self, screen, player):
        super().__init__(screen)
        self.player = player
        self.focus = 0
        self.scroll = 0           # first row shown
        self.rows = self._rows()

    def _rows(self):
        """(label, heading, title, pages or None if not found yet)."""
        found = set(self.player.lore)
        rows = [("Prologue", "Brackmoor", "Prologue", prologue(self.player.name))]
        minis = {e.id for e in MINIBOSS_LORE.values()}
        for e in WRITINGS:
            title = e.title if e.id in found else "? ? ?"
            label = (f"Floor {e.floor} miniboss: {title}" if e.id in minis
                     else f"Floor {e.floor}: {title}")
            heading = f"Floor {e.floor}: {CHAPTERS[e.floor]}"
            rows.append((label, heading, e.title,
                         list(e.pages) if e.id in found else None))
        seen = "epilogue" in found
        rows.append(("Epilogue" if seen else "Epilogue: ? ? ?", "Brackmoor",
                     EPILOGUE_TITLE, list(EPILOGUE) if seen else None))
        return rows

    @property
    def found_count(self) -> int:
        return sum(1 for e in WRITINGS if e.id in self.player.lore)

    def open(self, index):
        """Reread row ``index``; a transition, or None if not found yet."""
        _, heading, title, pages = self.rows[index]
        if pages is None:
            return None
        return ("story", {"title": title, "pages": pages, "heading": heading,
                          "return_to": self})

    def _row_rect(self, i):
        """Where row ``i`` of the whole list is drawn (off the panel when
        scrolled out of view)."""
        i -= self.scroll
        return pygame.Rect(LIST.x + 6, LIST.y + 6 + i * ROW_H, LIST.w - 12, ROW_H - 2)

    def _shown(self):
        return range(self.scroll, min(len(self.rows), self.scroll + VISIBLE_ROWS))

    def _follow_focus(self):
        """Scroll so the focused row is in view."""
        top = max(0, len(self.rows) - VISIBLE_ROWS)
        if self.focus < self.scroll:
            self.scroll = self.focus
        elif self.focus >= self.scroll + VISIBLE_ROWS:
            self.scroll = self.focus - VISIBLE_ROWS + 1
        self.scroll = max(0, min(top, self.scroll))

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return QUIT
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return ("base", {"player": self.player})
        if event.type == pygame.KEYDOWN:
            self.focus, activate = menu_key(event, len(self.rows), self.focus)
            self._follow_focus()
            if activate:
                return self.open(self.focus)
        elif event.type == pygame.MOUSEWHEEL:
            top = max(0, len(self.rows) - VISIBLE_ROWS)
            self.scroll = max(0, min(top, self.scroll - event.y))
            self.focus = max(self.scroll, min(self.focus, self.scroll + VISIBLE_ROWS - 1))
        elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            for i in self._shown():
                if self._row_rect(i).collidepoint(event.pos):
                    self.focus = i
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        return self.open(i)
        return None

    def draw(self, surface):
        draw_background(surface)
        title = font(40).render("Journal", True, GOLD)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 40)))
        count = font(20).render(
            f"Writings found: {self.found_count} / {len(WRITINGS)}", True, DIM_TEXT)
        surface.blit(count, count.get_rect(center=(SCREEN_WIDTH // 2, 76)))
        draw_panel(surface, LIST)
        for i in self._shown():
            label, _, _, pages = self.rows[i]
            rect = self._row_rect(i)
            if i == self.focus:
                pygame.draw.rect(surface, PANEL_HOT, rect, border_radius=4)
                pygame.draw.rect(surface, FOCUS_BORDER, rect, width=1, border_radius=4)
            img = font(22).render(label, True, TEXT_COLOR if pages else DIM_TEXT)
            surface.blit(img, img.get_rect(midleft=(rect.x + 12, rect.centery)))
        if self.scroll > 0:
            pygame.draw.polygon(surface, DIM_TEXT, [
                (LIST.right - 20, LIST.y + 10), (LIST.right - 28, LIST.y + 18),
                (LIST.right - 12, LIST.y + 18)])
        if self.scroll + VISIBLE_ROWS < len(self.rows):
            pygame.draw.polygon(surface, DIM_TEXT, [
                (LIST.right - 20, LIST.bottom - 10), (LIST.right - 28, LIST.bottom - 18),
                (LIST.right - 12, LIST.bottom - 18)])
        hint = font(18).render("Up/Down + Enter or tap: read    Esc: back to the Base",
                               True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 20, SCREEN_HEIGHT - 14)))
