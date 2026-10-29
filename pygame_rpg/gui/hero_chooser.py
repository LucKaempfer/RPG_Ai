# pygame_rpg/gui/hero_chooser.py
"""Saved-hero chooser (V3 hero_chooser() is a broken stub; this is new).

Lists every saved character; picking one loads it and opens the Base.
"""

import pygame

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..savegame import list_players, load_player
from .screen import (
    Screen, Button,
    BG_COLOR, TEXT_COLOR, DIM_TEXT, GOLD, font,
)

PAGE_SIZE = 8
ROW_H = 48


class HeroChooserScreen(Screen):
    name = "hero_chooser"

    def __init__(self, screen):
        super().__init__(screen)
        self.names = list_players()
        self.page = 0
        self.error = ""
        self.hot = None
        self.rows = []  # name buttons, rebuilt in draw()
        cx = SCREEN_WIDTH // 2
        bottom = SCREEN_HEIGHT - 90
        self.btn_back = Button("< Prev", (cx - 280, bottom, 160, 44))
        self.btn_next = Button("Next >", (cx + 120, bottom, 160, 44))
        self.btn_cancel = Button("Cancel", (cx - 80, bottom, 160, 44))
        self.btn_new = Button("Create New Hero", (cx - 150, 330, 300, 52))

    def _pages(self) -> int:
        return max(1, (len(self.names) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _page_names(self) -> list:
        lo = self.page * PAGE_SIZE
        return self.names[lo:lo + PAGE_SIZE]

    def handle_event(self, event):
        request = super().handle_event(event)
        if request is not None:
            return request
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if not self.names:
                if self.btn_new.rect.collidepoint(pos):
                    return "hero_maker"
            else:
                for btn in self.rows:
                    if btn.rect.collidepoint(pos):
                        return self._open(btn.label)
                if (self.btn_back.rect.collidepoint(pos)
                        and self.page > 0):
                    self.page -= 1
                elif (self.btn_next.rect.collidepoint(pos)
                        and self.page < self._pages() - 1):
                    self.page += 1
                elif self.btn_cancel.rect.collidepoint(pos):
                    return "title"
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "title"
        return None

    def _open(self, name):
        """Load the picked character; refresh the list on a missing file."""
        try:
            player = load_player(name)
        except FileNotFoundError:
            self.error = f"No save found for {name}."
            self.names = list_players()
            self.page = 0
            return None
        return ("base", {"player": player})

    def _hover(self, pos):
        buttons = self.rows + [
            self.btn_back, self.btn_next, self.btn_cancel, self.btn_new,
        ]
        for btn in buttons:
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        title = font(40).render("Choose a Hero", True, GOLD)
        surface.blit(title,
                     title.get_rect(center=(SCREEN_WIDTH // 2, 70)))
        cx = SCREEN_WIDTH // 2

        if self.error:
            err = font(22).render(self.error, True, DIM_TEXT)
            surface.blit(err, err.get_rect(center=(cx, 110)))

        if not self.names:
            msg = font(26).render("No saved heroes yet.", True, DIM_TEXT)
            surface.blit(msg, msg.get_rect(center=(cx, 250)))
            self.btn_new.draw(surface, hot=(self.hot is self.btn_new))
            return

        self.rows = []
        top = 120
        for name in self._page_names():
            btn = Button(name, (cx - 220, top, 440, 40))
            self.rows.append(btn)
            btn.draw(surface, hot=(self.hot is btn))
            top += ROW_H

        if self.page > 0:
            self.btn_back.draw(surface, hot=(self.hot is self.btn_back))
        if self.page < self._pages() - 1:
            self.btn_next.draw(surface,
                               hot=(self.hot is self.btn_next))
        self.btn_cancel.draw(surface, hot=(self.hot is self.btn_cancel))
