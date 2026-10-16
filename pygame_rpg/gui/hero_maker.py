# pygame_rpg/gui/hero_maker.py
"""Hero creation screen (port of the V3 hero_maker()).

Type a name, confirm it, and the character is written to disk with the
V3 starting stats plus the GUI starter gear (sword + potion).
"""

import pygame

from ..config import SCREEN_WIDTH, SCREEN_HEIGHT, START_LEVEL, START_HP
from ..player import Player
from ..items import STARTER_INVENTORY, item_by_id
from ..savegame import save_player, name_exists, _safe_name
from .screen import (
    Screen, Button,
    BG_COLOR, PANEL_COLOR, TEXT_COLOR, DIM_TEXT, GOLD,
    BORDER_COLOR, FOCUS_BORDER, font,
)

MAX_NAME_LEN = 20
ERROR_COLOR = (235, 110, 100)

NAME_HINT = "Letters, numbers, spaces, . _ -   (up to 20 characters)"


class HeroMakerScreen(Screen):
    name = "hero_maker"

    def __init__(self, screen):
        super().__init__(screen)
        cx = SCREEN_WIDTH // 2
        self.stage = "input"
        self.text = ""
        self.error = ""
        self.cursor_t = 0.0
        self.cursor_on = True
        self.hot = None
        self.input_rect = pygame.Rect(cx - 250, 170, 500, 56)
        bottom = SCREEN_HEIGHT - 90
        self.btn_create = Button("Create Hero", (cx - 270, bottom, 250, 48))
        self.btn_cancel = Button("Cancel", (cx + 20, bottom, 250, 48))
        self.btn_yes = Button("Yes", (cx - 230, bottom, 210, 48))
        self.btn_no = Button("No, retype", (cx + 20, bottom, 210, 48))

    def handle_update(self, dt):
        """Blink the text cursor about twice per second."""
        self.cursor_t += dt
        if self.cursor_t >= 0.5:
            self.cursor_t -= 0.5
            self.cursor_on = not self.cursor_on

    def handle_event(self, event):
        request = super().handle_event(event)
        if request is not None:
            return request
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.stage == "input":
                if self.btn_create.rect.collidepoint(pos):
                    return self._validate()
                if self.btn_cancel.rect.collidepoint(pos):
                    return "title"
            else:
                if self.btn_yes.rect.collidepoint(pos):
                    return self._create()
                if self.btn_no.rect.collidepoint(pos):
                    self.stage = "input"
                    self.error = ""
        elif event.type == pygame.KEYDOWN:
            if self.stage == "input":
                if event.key == pygame.K_RETURN:
                    return self._validate()
                elif event.key == pygame.K_ESCAPE:
                    return "title"
                elif event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
            else:
                if event.key == pygame.K_RETURN:
                    return self._create()
                elif event.key == pygame.K_ESCAPE:
                    self.stage = "input"
                    self.error = ""
        elif (event.type == pygame.TEXTINPUT
              and self.stage == "input"):
            self.text = (self.text + event.text)[:MAX_NAME_LEN]
        return None

    def _validate(self):
        """Check the typed name; on success move to the confirm stage."""
        name = self.text.strip()
        if not name:
            self.error = "Please enter a name first."
            return None
        try:
            _safe_name(name)
        except ValueError:
            self.error = "Only letters, numbers, spaces, . _ - (max 20)."
            return None
        if name_exists(name):
            self.error = f"{name} already exists. Choose another name."
            return None
        self.stage = "confirm"
        return None

    def _create(self):
        """Write the new character to disk and head for the Base."""
        name = _safe_name(self.text)
        player = Player(name=name)
        player.inventory = [item_by_id(i) for i in STARTER_INVENTORY]
        save_player(player)
        return ("base", {"player": player})

    def _hover(self, pos):
        if self.stage == "input":
            buttons = (self.btn_create, self.btn_cancel)
        else:
            buttons = (self.btn_yes, self.btn_no)
        for btn in buttons:
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def draw(self, surface):
        surface.fill(BG_COLOR)
        title = font(40).render("Create a New Hero", True, GOLD)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 70)))

        if self.stage == "input":
            label = font(24).render("Hero name", True, TEXT_COLOR)
            surface.blit(label,
                         (self.input_rect.x, self.input_rect.top - 34))
            pygame.draw.rect(surface, PANEL_COLOR, self.input_rect,
                             border_radius=8)
            hot = self.input_rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(surface,
                             FOCUS_BORDER if hot else BORDER_COLOR,
                             self.input_rect, width=2, border_radius=8)
            f = font(28)
            x = self.input_rect.x + 20
            y = self.input_rect.centery
            surface.blit(f.render(self.text, True, TEXT_COLOR),
                         (x, y - 18))
            if self.cursor_on:
                w = f.size(self.text)[0]
                pygame.draw.rect(surface, TEXT_COLOR,
                                 (x + w + 4, y - 16, 2, 24))
            hint = font(20).render(NAME_HINT, True, DIM_TEXT)
            surface.blit(hint,
                         (self.input_rect.x, self.input_rect.bottom + 10))
        else:
            name = self.text.strip()
            panel = pygame.Rect(150, 140, SCREEN_WIDTH - 300, 220)
            pygame.draw.rect(surface, PANEL_COLOR, panel, border_radius=10)
            pygame.draw.rect(surface, BORDER_COLOR, panel, width=2,
                             border_radius=10)
            q = font(28).render(f"Is '{name}' correct?", True, TEXT_COLOR)
            surface.blit(q,
                         q.get_rect(center=(panel.centerx, panel.top + 50)))
            info = font(22).render(
                f"Level {START_LEVEL}  -  {START_HP} HP  -  "
                f"starts with sword and potion", True, DIM_TEXT)
            surface.blit(info,
                         info.get_rect(center=(panel.centerx, panel.top + 110)))

        if self.error:
            err = font(24).render(self.error, True, ERROR_COLOR)
            surface.blit(err,
                         err.get_rect(center=(SCREEN_WIDTH // 2, 285)))

        if self.stage == "input":
            self.btn_create.draw(surface, hot=(self.hot is self.btn_create))
            self.btn_cancel.draw(surface, hot=(self.hot is self.btn_cancel))
        else:
            self.btn_yes.draw(surface, hot=(self.hot is self.btn_yes))
            self.btn_no.draw(surface, hot=(self.hot is self.btn_no))
