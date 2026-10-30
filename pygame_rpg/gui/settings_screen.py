# pygame_rpg/gui/settings_screen.py
"""Settings screen: brightness, volumes, fullscreen and key bindings.

Opened from the title screen and the Base; it goes back to the screen
it came from (``return_to``, resumed as it was).  Every change applies
at once (``settings.current``) and is written to disk on leaving.

Rows: three sliders, a fullscreen toggle, one row per action with two
key slots, then Reset keys and Back.  Keyboard: Up / Down pick a row,
Left / Right move a slider or pick a key slot, Enter starts listening
for a new key (Esc cancels, Backspace / Delete empties the slot).
The mouse can drag the sliders and click everything else.  The sewer
ambience plays here so its volume can be heard while it is set.
"""

import pygame

from .. import audio, settings
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from .screen import (
    draw_background, draw_bar, draw_panel, SHADOW_COLOR, QUIT, Screen,
    Button, font, PANEL_COLOR, PANEL_HOT, TEXT_COLOR, DIM_TEXT, GOLD,
    FOCUS_BORDER, BORDER_COLOR,
)

# Slider rows: attribute on settings.current, label, range, step.
SLIDERS = (
    ("brightness", "Brightness", settings.BRIGHTNESS_RANGE, 0.1),
    ("ambience_volume", "Ambience volume", (0.0, 1.0), 0.05),
    ("effects_volume", "Effects volume", (0.0, 1.0), 0.05),
)
ACTIONS = tuple(settings.ACTIONS)
ROW_H, TOP, KEYS_TOP = 32, 70, 236
LABEL_X, CONTROL_X, TRACK_W, SLOT_W = 70, 330, 300, 190
HINT = "Up/Down: row   Left/Right: change   Enter: set key   Esc: save & back"


class SettingsScreen(Screen):
    name = "settings"
    ambience = "sewer"

    def __init__(self, screen, return_to=None):
        super().__init__(screen)
        self.return_to = return_to
        self.rows = ([("slider", s) for s in SLIDERS] + [("fullscreen",)]
                     + [("keys", a) for a in ACTIONS]
                     + [("reset",), ("back",)])
        self.row, self.col = 0, 0
        self.listening = None       # (action, slot) waiting for a key
        self.dragging = None        # slider row index being dragged
        self.message = ""
        y = KEYS_TOP + len(ACTIONS) * ROW_H + 24
        self.btn_reset = Button("Reset keys", (SCREEN_WIDTH // 2 - 210, y, 200, 44))
        self.btn_back = Button("Back", (SCREEN_WIDTH // 2 + 10, y, 200, 44))

    # -- layout ----------------------------------------------------------
    def row_y(self, i):
        kind = self.rows[i][0]
        if kind in ("reset", "back"):
            return self.btn_reset.rect.y
        if kind == "keys":
            return KEYS_TOP + (i - len(SLIDERS) - 1) * ROW_H
        return TOP + i * ROW_H

    def track(self, i):
        return pygame.Rect(CONTROL_X, self.row_y(i) + 12, TRACK_W, 8)

    def slot_rect(self, i, slot):
        return pygame.Rect(CONTROL_X + slot * (SLOT_W + 16), self.row_y(i),
                           SLOT_W, 28)

    def toggle_rect(self, i):
        return pygame.Rect(CONTROL_X, self.row_y(i), 120, 28)

    # -- changing values ---------------------------------------------------
    def set_slider(self, spec, value):
        attr, _, (lo, hi), step = spec
        value = round(min(max(value, lo), hi) / step) * step
        setattr(settings.current, attr, round(value, 2))
        if attr == "ambience_volume":
            audio.refresh_volume()

    def nudge(self, spec, direction):
        self.set_slider(spec, getattr(settings.current, spec[0])
                        + direction * spec[3])
        if spec[0] == "effects_volume":
            audio.play("click")

    def slider_at(self, i, x):
        spec = self.rows[i][1]
        lo, hi = spec[2]
        t = (x - CONTROL_X) / TRACK_W
        self.set_slider(spec, lo + t * (hi - lo))

    def leave(self):
        settings.save()
        if self.return_to is None:
            return "title"
        return ("resume", {"screen": self.return_to})

    def activate(self):
        kind = self.rows[self.row][0]
        if kind == "fullscreen":
            settings.current.fullscreen = not settings.current.fullscreen
        elif kind == "keys":
            self.listening = (self.rows[self.row][1], self.col)
            self.message = ""
        elif kind == "reset":
            settings.current.reset_keys()
            self.message = "Keys reset to the defaults."
        elif kind == "back":
            return self.leave()
        return None

    def bind(self, key):
        action, slot = self.listening
        self.listening = None
        if key in settings.RESERVED_KEYS:
            self.message = "Esc, F11 and M keep their jobs."
            return
        settings.current.bind(action, slot, key)
        self.message = ""

    # -- Screen hooks ------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            settings.save()
            return QUIT
        if self.listening is not None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.listening = None
                elif event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                    settings.current.bind(*self.listening, None)
                    self.listening = None
                else:
                    self.bind(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.listening = None
            return None
        if event.type == pygame.KEYDOWN:
            return self._key(event.key)
        if event.type == pygame.MOUSEMOTION:
            if self.dragging is not None:
                self.slider_at(self.dragging, event.pos[0])
            else:
                self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hover(event.pos):
                kind = self.rows[self.row][0]
                if kind == "slider":
                    self.dragging = self.row
                    self.slider_at(self.row, event.pos[0])
                else:
                    return self.activate()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if (self.dragging is not None
                    and self.rows[self.dragging][1][0] == "effects_volume"):
                audio.play("click")
            self.dragging = None
        return None

    def _key(self, k):
        kind = self.rows[self.row][0]
        if k == pygame.K_ESCAPE:
            return self.leave()
        if k in (pygame.K_UP, pygame.K_DOWN):
            self.row = (self.row + (-1 if k == pygame.K_UP else 1)) % len(self.rows)
        elif k in (pygame.K_LEFT, pygame.K_RIGHT):
            direction = -1 if k == pygame.K_LEFT else 1
            if kind == "slider":
                self.nudge(self.rows[self.row][1], direction)
            elif kind == "fullscreen":
                settings.current.fullscreen = direction > 0
            elif kind == "keys":
                self.col = 0 if direction < 0 else 1
            else:
                self.row = self.rows.index(("reset",) if direction < 0
                                           else ("back",))
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            return self.activate()
        return None

    def _hover(self, pos):
        """Focus the row (and key slot) under ``pos``; True if any."""
        for i, row in enumerate(self.rows):
            kind = row[0]
            if kind == "slider":
                hit = self.track(i).inflate(24, 24).collidepoint(pos)
            elif kind == "fullscreen":
                hit = self.toggle_rect(i).collidepoint(pos)
            elif kind == "keys":
                for slot in (0, 1):
                    if self.slot_rect(i, slot).collidepoint(pos):
                        self.row, self.col = i, slot
                        return True
                hit = False
            else:
                btn = self.btn_reset if kind == "reset" else self.btn_back
                hit = btn.rect.collidepoint(pos)
            if hit:
                self.row = i
                return True
        return False

    # -- drawing -----------------------------------------------------------
    def draw(self, surface):
        draw_background(surface)
        header = font(36).render("Settings", True, GOLD)
        surface.blit(header, header.get_rect(midtop=(SCREEN_WIDTH // 2, 20)))
        keys_label = font(24).render("Key bindings", True, GOLD)
        surface.blit(keys_label, (LABEL_X, KEYS_TOP - 30))
        for i, row in enumerate(self.rows):
            kind, focused = row[0], i == self.row
            if kind in ("reset", "back"):
                btn = self.btn_reset if kind == "reset" else self.btn_back
                btn.draw(surface, hot=focused)
                continue
            y = self.row_y(i)
            label = (row[1][1] if kind == "slider" else
                     "Fullscreen (F11)" if kind == "fullscreen" else
                     settings.ACTIONS[row[1]])
            text = font(24).render(label, True,
                                   TEXT_COLOR if focused else DIM_TEXT)
            surface.blit(text, text.get_rect(midleft=(LABEL_X, y + 14)))
            if focused:
                pygame.draw.polygon(surface, GOLD, [
                    (LABEL_X - 18, y + 8), (LABEL_X - 8, y + 14),
                    (LABEL_X - 18, y + 20)])
            if kind == "slider":
                self._draw_slider(surface, i, row[1], focused)
            elif kind == "fullscreen":
                on = settings.current.fullscreen
                self._box(surface, self.toggle_rect(i), "On" if on else "Off",
                          focused)
            else:
                for slot in (0, 1):
                    listening = self.listening == (row[1], slot)
                    shown = ("press a key..." if listening else
                             settings.key_label(settings.current.keys[row[1]][slot]))
                    self._box(surface, self.slot_rect(i, slot), shown,
                              focused and self.col == slot, listening)
        if self.message:
            msg = font(20).render(self.message, True, GOLD)
            surface.blit(msg, msg.get_rect(
                midtop=(SCREEN_WIDTH // 2, self.btn_back.rect.bottom + 8)))
        hint = font(18).render(HINT, True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(
            bottomright=(SCREEN_WIDTH - 20, SCREEN_HEIGHT - 10)))

    def _draw_slider(self, surface, i, spec, focused):
        attr, _, (lo, hi), _ = spec
        value = getattr(settings.current, attr)
        track = self.track(i)
        draw_bar(surface, track, value - lo, hi - lo, GOLD, radius=4)
        knob = (track.x + int(track.w * (value - lo) / (hi - lo)), track.centery)
        pygame.draw.circle(surface, SHADOW_COLOR, (knob[0], knob[1] + 2), 10)
        pygame.draw.circle(surface, FOCUS_BORDER if focused else TEXT_COLOR,
                           knob, 9)
        pygame.draw.circle(surface, BORDER_COLOR, knob, 9, width=1)
        pct = font(22).render(f"{round(value * 100)}%", True, TEXT_COLOR)
        surface.blit(pct, pct.get_rect(midleft=(track.right + 20, track.centery)))

    def _box(self, surface, rect, text, focused, listening=False):
        draw_panel(surface, rect, PANEL_HOT if focused else PANEL_COLOR,
                   GOLD if listening else FOCUS_BORDER if focused else BORDER_COLOR,
                   radius=6)
        label = font(22).render(text, True, GOLD if listening else TEXT_COLOR)
        surface.blit(label, label.get_rect(center=rect.center))
