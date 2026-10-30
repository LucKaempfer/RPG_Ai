# pygame_rpg/gui/hero_maker.py
"""Hero creation screen (port of the V3 hero_maker()).

Four stages: type a name, choose a class (``classes.py``: warrior,
archer, mage, rogue; it sets the starting stats and gear), pick the
hero's look (skin, hair, hair colour, tunic, with a live walking
preview holding the class's weapon), confirm.  The character is then
written to disk with the class's stats and starter kit.

Class stage: tap a card or Left / Right, Enter goes on, Esc goes back.

Look stage keys: Up / Down pick a row, Left / Right change it, R rolls
a random look, Enter goes on, Esc goes back to the name.

On Android the on-screen keyboard shows during the name stage (tap the
name box to bring it back); ``Display`` hides it when the screen goes.
"""

import random

import pygame

from .. import device
from ..assets import (
    AssetManager, LOOK_OPTIONS, LOOK_LABELS, look_choice,
    HERO_COLS, HERO_WALK_COLS, gear_of, upscale,
)
from ..classes import CLASSES, CLASS_ORDER, make_hero
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT, START_LEVEL, START_MP
from ..player import LOOK_KEYS
from ..items import item_by_id
from ..stat_names import LABEL
from .inventory_screen import _wrap
from ..savegame import save_player, name_exists, _safe_name
from .screen import (
    draw_background, draw_panel, Screen, Button, PANEL_COLOR, TEXT_COLOR,
    DIM_TEXT, GOLD, BORDER_COLOR, FOCUS_BORDER, font,
)

MAX_NAME_LEN = 20
ERROR_COLOR = (235, 110, 100)

NAME_HINT = "Letters, numbers, spaces, . _ -   (up to 20 characters)"
CLASS_HINT = "Tap a class or Left/Right: choose   Enter: next   Esc: back"
CLASS_STATS = ("hp", "ap", "rap", "map", "dp", "rdp", "mdp")
LOOK_HINT = "Up/Down: choose   Left/Right: change   R: random   Enter: next   Esc: back"
# Preview: the hero walks and turns to a new direction every TURN_TIME s.
PREVIEW_FRAME = 0.11
TURN_TIME = 1.2


class HeroMakerScreen(Screen):
    name = "hero_maker"

    def __init__(self, screen):
        super().__init__(screen)
        cx = SCREEN_WIDTH // 2
        self.stage = "input"
        self.keyboard = False       # on-screen keyboard shown (Android)
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
        self.btn_no = Button("No, go back", (cx + 20, bottom, 210, 48))
        # Class stage: one card per class, details below.
        self.hero_class = CLASS_ORDER[0]
        self.class_cards = [pygame.Rect(40 + i * 185, 130, 170, 96)
                            for i in range(len(CLASS_ORDER))]
        self.btn_class_back = Button("Back", (cx - 230, bottom, 210, 48))
        self.btn_class_next = Button("Next", (cx + 20, bottom, 210, 48))
        # Look stage.
        self.look = {k: 0 for k in LOOK_KEYS}
        self.row = 0
        self.preview_t = 0.0
        self.assets = AssetManager()
        self.btn_random = Button("Random", (cx - 345, bottom, 210, 48))
        self.btn_next = Button("Next", (cx - 105, bottom, 210, 48))
        self.btn_back = Button("Back", (cx + 135, bottom, 210, 48))
        # One row per look key: (row rect, "<" rect, ">" rect).
        self.look_rows = []
        for i in range(len(LOOK_KEYS)):
            y = 150 + i * 70
            self.look_rows.append((pygame.Rect(360, y, 380, 54),
                                   pygame.Rect(530, y + 7, 40, 40),
                                   pygame.Rect(690, y + 7, 40, 40)))

    def handle_update(self, dt):
        """Blink the text cursor about twice per second; animate the
        look preview."""
        self.preview_t += dt
        self.cursor_t += dt
        typing = self.stage == "input"
        if typing != self.keyboard:
            self.keyboard = typing
            device.show_keyboard() if typing else device.hide_keyboard()
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
                if self.input_rect.collidepoint(pos):
                    device.show_keyboard()
                if self.btn_create.rect.collidepoint(pos):
                    return self._validate()
                if self.btn_cancel.rect.collidepoint(pos):
                    return "title"
            elif self.stage == "class":
                self._click_class(pos)
            elif self.stage == "look":
                self._click_look(pos)
            else:
                if self.btn_yes.rect.collidepoint(pos):
                    return self._create()
                if self.btn_no.rect.collidepoint(pos):
                    self.stage = "look"
        elif event.type == pygame.KEYDOWN:
            if self.stage == "input":
                if event.key == pygame.K_RETURN:
                    return self._validate()
                elif event.key == pygame.K_ESCAPE:
                    return "title"
                elif event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
            elif self.stage == "class":
                self._class_key(event.key)
            elif self.stage == "look":
                self._look_key(event.key)
            else:
                if event.key == pygame.K_RETURN:
                    return self._create()
                elif event.key == pygame.K_ESCAPE:
                    self.stage = "look"
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
        self.error = ""
        self.stage = "class"
        return None

    # -- class stage -------------------------------------------------------
    def pick_class(self, step) -> None:
        i = CLASS_ORDER.index(self.hero_class)
        self.hero_class = CLASS_ORDER[(i + step) % len(CLASS_ORDER)]

    def _class_key(self, key) -> None:
        if key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
            self.pick_class(-1)
        elif key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s):
            self.pick_class(1)
        elif pygame.K_1 <= key < pygame.K_1 + len(CLASS_ORDER):
            self.hero_class = CLASS_ORDER[key - pygame.K_1]
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.stage = "look"
        elif key == pygame.K_ESCAPE:
            self.stage = "input"

    def _click_class(self, pos) -> None:
        for key, card in zip(CLASS_ORDER, self.class_cards):
            if card.collidepoint(pos):
                self.hero_class = key
        if self.btn_class_next.rect.collidepoint(pos):
            self.stage = "look"
        elif self.btn_class_back.rect.collidepoint(pos):
            self.stage = "input"

    # -- look stage --------------------------------------------------------
    def change(self, key, step) -> None:
        """Cycle the option for look ``key`` by ``step`` (wraps)."""
        self.look[key] = (self.look[key] + step) % len(LOOK_OPTIONS[key])

    def randomize(self, rng=random) -> None:
        self.look = {k: rng.randrange(len(LOOK_OPTIONS[k])) for k in LOOK_KEYS}

    def _look_key(self, key) -> None:
        if key in (pygame.K_UP, pygame.K_w):
            self.row = (self.row - 1) % len(LOOK_KEYS)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.row = (self.row + 1) % len(LOOK_KEYS)
        elif key in (pygame.K_LEFT, pygame.K_a):
            self.change(LOOK_KEYS[self.row], -1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.change(LOOK_KEYS[self.row], 1)
        elif key == pygame.K_r:
            self.randomize()
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.stage = "confirm"
        elif key == pygame.K_ESCAPE:
            self.stage = "class"

    def _click_look(self, pos) -> None:
        for i, (row, left, right) in enumerate(self.look_rows):
            if left.collidepoint(pos):
                self.row = i
                self.change(LOOK_KEYS[i], -1)
            elif right.collidepoint(pos):
                self.row = i
                self.change(LOOK_KEYS[i], 1)
            elif row.collidepoint(pos):
                self.row = i
        if self.btn_random.rect.collidepoint(pos):
            self.randomize()
        elif self.btn_next.rect.collidepoint(pos):
            self.stage = "confirm"
        elif self.btn_back.rect.collidepoint(pos):
            self.stage = "class"

    def _create(self):
        """Write the new character to disk and head for the Base."""
        player = make_hero(_safe_name(self.text), self.look, self.hero_class)
        save_player(player)
        return ("base", {"player": player})

    def _hover(self, pos):
        if self.stage == "input":
            buttons = (self.btn_create, self.btn_cancel)
        elif self.stage == "class":
            buttons = (self.btn_class_back, self.btn_class_next)
        elif self.stage == "look":
            buttons = (self.btn_random, self.btn_next, self.btn_back)
        else:
            buttons = (self.btn_yes, self.btn_no)
        for btn in buttons:
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def draw(self, surface):
        draw_background(surface)
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
        elif self.stage == "class":
            self._draw_class(surface)
        elif self.stage == "look":
            self._draw_look(surface)
        else:
            name = self.text.strip()
            panel = pygame.Rect(150, 140, SCREEN_WIDTH - 300, 220)
            draw_panel(surface, panel, radius=10)
            q = font(28).render(f"Is '{name}' correct?", True, TEXT_COLOR)
            surface.blit(q,
                         q.get_rect(center=(panel.centerx, panel.top + 50)))
            cls = CLASSES[self.hero_class]
            info = font(22).render(
                f"Level {START_LEVEL} {cls.name}  -  {cls.stats['hp']} health  -  "
                f"{START_MP + cls.mp_bonus} mana", True, DIM_TEXT)
            surface.blit(info,
                         info.get_rect(center=(panel.centerx, panel.top + 110)))
            hero = self._preview_frame(0)
            surface.blit(hero, hero.get_rect(center=(panel.centerx, panel.top + 170)))

        if self.error:
            err = font(24).render(self.error, True, ERROR_COLOR)
            surface.blit(err,
                         err.get_rect(center=(SCREEN_WIDTH // 2, 285)))

        if self.stage == "input":
            self.btn_create.draw(surface, hot=(self.hot is self.btn_create))
            self.btn_cancel.draw(surface, hot=(self.hot is self.btn_cancel))
        elif self.stage == "class":
            for btn in (self.btn_class_back, self.btn_class_next):
                btn.draw(surface, hot=(self.hot is btn))
        elif self.stage == "look":
            for btn in (self.btn_random, self.btn_next, self.btn_back):
                btn.draw(surface, hot=(self.hot is btn))
        else:
            self.btn_yes.draw(surface, hot=(self.hot is self.btn_yes))
            self.btn_no.draw(surface, hot=(self.hot is self.btn_no))

    def _preview_frame(self, direction=None, size=64):
        """The hero in the chosen look, walking; ``direction`` None turns
        through all four directions over time."""
        weapon = item_by_id(CLASSES[self.hero_class].kit[0])
        frames = self.assets.hero_frames(self.look, gear_of({"weapon": weapon}))
        if direction is None:
            direction = (0, 3, 1, 2)[int(self.preview_t / TURN_TIME) % 4]
        col = HERO_WALK_COLS[int(self.preview_t / PREVIEW_FRAME)
                             % len(HERO_WALK_COLS)]
        frame = frames[direction * HERO_COLS + col]
        return upscale(frame, size, outline=True)

    def _draw_class(self, surface):
        """Class cards across the top, the chosen class's details below:
        how it plays, its starting stats as bars, its starter kit."""
        sub = font(26).render("Choose your class", True, DIM_TEXT)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 108)))
        for key, card in zip(CLASS_ORDER, self.class_cards):
            cls, chosen = CLASSES[key], key == self.hero_class
            pygame.draw.rect(surface, PANEL_COLOR, card, border_radius=8)
            pygame.draw.rect(surface, FOCUS_BORDER if chosen else BORDER_COLOR,
                             card, width=3 if chosen else 2, border_radius=8)
            name = font(28).render(cls.name, True, GOLD if chosen else TEXT_COLOR)
            surface.blit(name, name.get_rect(midtop=(card.centerx, card.y + 14)))
            for i, line in enumerate(_wrap(cls.blurb, 18, card.w - 16)[:2]):
                img = font(18).render(line, True, DIM_TEXT)
                surface.blit(img, img.get_rect(midtop=(card.centerx, card.y + 48 + i * 18)))

        cls = CLASSES[self.hero_class]
        panel = pygame.Rect(40, 240, 725, 228)
        draw_panel(surface, panel, radius=10)
        hero = self._preview_frame(0, size=96)
        surface.blit(hero, (panel.x + 14, panel.y + 12))
        x, y = panel.x + 120, panel.y + 16
        for line in _wrap(cls.about, 20, 240):
            surface.blit(font(20).render(line, True, TEXT_COLOR), (x, y))
            y += 21
        y = max(y + 10, panel.y + 120)
        surface.blit(font(19).render("Starts with:", True, GOLD), (panel.x + 16, y))
        kit = ", ".join(dict.fromkeys(item_by_id(i).name for i in cls.kit))
        extra = f", {cls.gold} gold" if cls.gold else ""
        for line in _wrap(kit + extra, 19, 330):
            y += 20
            surface.blit(font(19).render(line, True, DIM_TEXT), (panel.x + 16, y))
        # Stat bars on the right.
        sx, sy = panel.x + 390, panel.y + 16
        for i, stat in enumerate(CLASS_STATS):
            value = cls.stats[stat]
            top = 150 if stat == "hp" else 12
            yy = sy + i * 26
            surface.blit(font(19).render(LABEL[stat], True, DIM_TEXT), (sx, yy))
            bar = pygame.Rect(sx + 130, yy + 3, 150, 12)
            pygame.draw.rect(surface, (15, 15, 20), bar, border_radius=5)
            fill = bar.copy()
            fill.w = max(2, int(bar.w * min(1, value / top)))
            pygame.draw.rect(surface, GOLD, fill, border_radius=5)
            surface.blit(font(19).render(str(value), True, TEXT_COLOR), (bar.right + 8, yy))
        mana = font(19).render(f"{LABEL['mp']}  {START_MP + cls.mp_bonus}", True, DIM_TEXT)
        surface.blit(mana, (sx, sy + len(CLASS_STATS) * 26))
        hint = font(18).render(CLASS_HINT, True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(midtop=(SCREEN_WIDTH // 2, 476)))

    def _draw_look(self, surface):
        """Preview on the left, one option row per look key on the right."""
        sub = font(26).render("Choose your look", True, DIM_TEXT)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 112)))
        box = pygame.Rect(60, 150, 260, 260)
        draw_panel(surface, box, radius=10)
        hero = self._preview_frame(size=192)
        surface.blit(hero, hero.get_rect(center=box.center))
        name = font(26).render(self.text.strip(), True, TEXT_COLOR)
        surface.blit(name, name.get_rect(midtop=(box.centerx, box.bottom + 10)))
        for i, (key, (row, left, right)) in enumerate(zip(LOOK_KEYS, self.look_rows)):
            focused = i == self.row
            pygame.draw.rect(surface, PANEL_COLOR, row, border_radius=8)
            pygame.draw.rect(surface, FOCUS_BORDER if focused else BORDER_COLOR,
                             row, width=2, border_radius=8)
            label = font(24).render(LOOK_LABELS[key], True,
                                    GOLD if focused else DIM_TEXT)
            surface.blit(label, label.get_rect(midleft=(row.x + 16, row.centery)))
            for rect, arrow in ((left, "<"), (right, ">")):
                pygame.draw.rect(surface, BORDER_COLOR, rect, width=1, border_radius=6)
                a = font(28).render(arrow, True, TEXT_COLOR)
                surface.blit(a, a.get_rect(center=rect.center))
            choice, value = look_choice(self.look, key)
            mid = (left.right + right.left) // 2
            text = font(24).render(choice, True, TEXT_COLOR)
            surface.blit(text, text.get_rect(center=(mid, row.centery)))
            if isinstance(value, tuple):        # a colour: show a swatch
                pygame.draw.rect(surface, value, (row.x + 140, row.centery - 9, 18, 18),
                                 border_radius=4)
        hint = font(18).render(LOOK_HINT, True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(midtop=(SCREEN_WIDTH // 2, 440)))
