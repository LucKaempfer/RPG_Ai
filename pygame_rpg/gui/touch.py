"""On-screen controls for touch screens: a D-pad and A / B / Bag / Menu.

In menus they sit in the black bars left and right of the canvas
(``Display`` keeps those bars wide enough when ``device.TOUCH`` is on);
in the dungeon, which fills the whole screen, they float over it
half see-through in the bottom corners.  They feed the same inputs as
the keyboard, so no screen needs to know about touch:

* In the dungeon the D-pad holds the move actions (``settings.held``
  sees them through ``settings.virtual_held``) and the buttons send a
  KEYDOWN carrying the action (``settings.pressed`` checks it): A
  attacks, B talks / uses, Bag opens the inventory, Menu is Escape.
* Everywhere else the D-pad sends arrow keys (repeating while held), A
  (OK) is Enter and B (Back) is Escape, which every menu already
  handles; Bag and Menu are hidden.

Taps on the canvas itself are left to SDL's touch-to-mouse events, so
buttons on the screens work by tapping them.  Each finger is tracked
on its own (FINGERDOWN / FINGERMOTION / FINGERUP), so the hero can walk
and attack at once.  With ``RPG_TOUCH=1`` on a desktop the mouse plays
one finger, to try the layout.
"""

import math

import pygame

from .. import settings
from .screen import font

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
ARROW_KEYS = {"up": pygame.K_UP, "down": pygame.K_DOWN,
              "left": pygame.K_LEFT, "right": pygame.K_RIGHT}
DEAD_ZONE = 0.25              # share of the D-pad radius that does nothing
REPEAT_DELAY, REPEAT_EVERY = 0.4, 0.12   # menu arrow repeat (seconds)
MOUSE_FINGER = "mouse"

PAD_COLOR = (44, 44, 60)
PAD_HOT = (215, 215, 245)
RIM_COLOR = (110, 110, 140)
LABEL_COLOR = (225, 225, 235)
OVERLAY_ALPHA = 140           # see-through over the dungeon
BUTTON_COLORS = {"a": (60, 120, 70), "b": (130, 60, 60),
                 "bag": (70, 70, 100), "menu": (70, 70, 100)}


def key_event(key, action=None):
    """A KEYDOWN as the keyboard would send it, plus the touch action."""
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="",
                              scancode=0, action=action)


def pad_dirs(dx, dy, radius, diagonal=True):
    """Directions held by a finger at (dx, dy) from the D-pad centre.
    ``diagonal=False`` keeps only the stronger axis (menus)."""
    if math.hypot(dx, dy) < radius * DEAD_ZONE:
        return frozenset()
    dirs = set()
    ax, ay = abs(dx), abs(dy)
    # Within ~22 degrees of an axis counts as straight.
    if ax > ay * 0.4142 and (diagonal or ax >= ay):
        dirs.add("right" if dx > 0 else "left")
    if ay > ax * 0.4142 and (diagonal or ay > ax):
        dirs.add("down" if dy > 0 else "up")
    return frozenset(dirs)


class TouchControls:
    def __init__(self):
        self.context = None          # name of the screen shown
        self.window = (0, 0)
        self.view = pygame.Rect(0, 0, 0, 0)
        self.pad = None              # (centre, radius)
        self.buttons = {}            # name -> (centre, radius, label)
        self.fingers = {}            # finger id -> "pad" or a button name
        self.pad_fingers = {}        # finger id -> frozenset of directions
        self.repeat = None           # [direction, seconds to next repeat]
        self.overlay = False         # floating over the game, not in bars
        self._layer = None           # SRCALPHA surface for the overlay

    # -- layout ------------------------------------------------------------
    def layout(self, window, view, overlay=False):
        """Place the controls in the bars beside ``view`` (the canvas
        rect inside a ``window``-sized area), or with ``overlay`` over
        the game in the bottom corners (thumb reach)."""
        self.window, self.view = tuple(window), pygame.Rect(view)
        self.overlay = overlay
        ww, wh = self.window
        if overlay:
            m = int(wh * 0.05)
            r = int(wh * 0.19)
            self.pad = ((m + r, wh - m - r), r)
            rb = int(wh * 0.095)
            rs = int(rb * 0.75)
            ax, ay = ww - m - rb, wh - m - int(rb * 2.2)
            self.buttons = {
                "a": ((ax, ay), rb, "A"),
                "b": ((ax - int(rb * 2.3), ay + int(rb * 1.2)), rb, "B"),
                "bag": ((ax, ay - int(rb * 2.6)), rs, "Bag"),
                "menu": ((ax - int(rb * 2.3), ay - int(rb * 1.6)), rs, "Menu"),
            }
            return
        bar = max(1, self.view.x)
        r = int(min(bar * 0.4, wh * 0.22))
        self.pad = ((bar // 2, int(wh * 0.62)), r)
        rb = int(min(bar * 0.17, wh * 0.1))
        rs = int(rb * 0.7)
        rx = ww - bar // 2
        self.buttons = {
            "a": ((rx + int(rb * 1.15), int(wh * 0.58)), rb, "A"),
            "b": ((rx - int(rb * 1.15), int(wh * 0.58) + int(rb * 1.3)), rb, "B"),
            "bag": ((rx, int(wh * 0.18)), rs, "Bag"),
            "menu": ((bar // 2, int(wh * 0.18)), rs, "Menu"),
        }

    def visible_buttons(self):
        if self.context == "dungeon":
            return self.buttons
        # Menus only need OK and Back.
        return {k: v for k, v in self.buttons.items() if k in ("a", "b")}

    def hit(self, pos):
        """The control at window position ``pos`` (or None)."""
        x, y = pos
        for name, ((cx, cy), r, _) in self.visible_buttons().items():
            if math.hypot(x - cx, y - cy) <= r * 1.25:
                return name
        if self.pad:
            (cx, cy), r = self.pad
            if math.hypot(x - cx, y - cy) <= r * 1.3:
                return "pad"
        return None

    def on_control_side(self, pos):
        """Outside the game view (the bars), where taps never reach a
        screen.  With the overlay only the controls themselves count."""
        if self.overlay:
            return False
        return not self.view.collidepoint(pos)

    # -- input -------------------------------------------------------------
    def handle_event(self, event):
        """Returns True when the event belonged to the controls (the
        screens should not see it)."""
        t = event.type
        if t in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            ww, wh = self.window
            pos = (event.x * ww, event.y * wh)
            fid = (event.touch_id, event.finger_id)
            if t == pygame.FINGERDOWN:
                return self._down(fid, pos)
            if t == pygame.FINGERMOTION:
                return self._move(fid, pos)
            return self._up(fid)
        if t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            if getattr(event, "touch", False):
                # SDL's copy of a finger: the finger events handled it if
                # it was on the controls.
                return (self.on_control_side(event.pos)
                        or self.hit(event.pos) is not None
                        or bool(self.fingers))
            if t == pygame.MOUSEBUTTONDOWN and event.button == 1:
                return self._down(MOUSE_FINGER, event.pos)
            if t == pygame.MOUSEMOTION and MOUSE_FINGER in self.fingers:
                return self._move(MOUSE_FINGER, event.pos)
            if t == pygame.MOUSEBUTTONUP and MOUSE_FINGER in self.fingers:
                return self._up(MOUSE_FINGER)
            return False
        return False

    def _down(self, fid, pos):
        control = self.hit(pos)
        if control is None:
            return self.on_control_side(pos)
        self.fingers[fid] = control
        if control == "pad":
            self._pad(fid, pos)
        else:
            self._press(control)
        return True

    def _move(self, fid, pos):
        if self.fingers.get(fid) == "pad":
            self._pad(fid, pos)
            return True
        return fid in self.fingers

    def _up(self, fid):
        control = self.fingers.pop(fid, None)
        if control == "pad":
            self.pad_fingers.pop(fid, None)
            self._sync_held()
        return control is not None

    def _pad(self, fid, pos):
        (cx, cy), r = self.pad
        diagonal = self.context == "dungeon"
        dirs = pad_dirs(pos[0] - cx, pos[1] - cy, r, diagonal)
        old = self.pad_fingers.get(fid, frozenset())
        self.pad_fingers[fid] = dirs
        self._sync_held()
        if not diagonal and dirs and dirs != old:
            (d,) = dirs
            pygame.event.post(key_event(ARROW_KEYS[d], d))
            self.repeat = [d, REPEAT_DELAY]

    def _sync_held(self):
        held = set().union(*self.pad_fingers.values()) if self.pad_fingers else set()
        settings.virtual_held.clear()
        if self.context == "dungeon":
            settings.virtual_held.update(held)
        if not held:
            self.repeat = None

    def _press(self, name):
        if self.context == "dungeon":
            ev = {"a": key_event(pygame.K_UNKNOWN, "attack"),
                  "b": key_event(pygame.K_UNKNOWN, "interact"),
                  "bag": key_event(pygame.K_UNKNOWN, "inventory"),
                  "menu": key_event(pygame.K_ESCAPE)}[name]
        else:
            ev = key_event(pygame.K_RETURN if name == "a" else pygame.K_ESCAPE)
        pygame.event.post(ev)

    def set_context(self, name):
        """Tell the controls which screen is shown (call every frame)."""
        if name != self.context:
            self.context = name
            self.fingers.clear()
            self.pad_fingers.clear()
            self._sync_held()

    def update(self, dt):
        """Repeat a held menu arrow."""
        if self.repeat is None:
            return
        self.repeat[1] -= dt
        if self.repeat[1] <= 0:
            pygame.event.post(key_event(ARROW_KEYS[self.repeat[0]], self.repeat[0]))
            self.repeat[1] = REPEAT_EVERY

    # -- drawing -----------------------------------------------------------
    def draw(self, surface):
        if not self.pad:
            return
        if not self.overlay:
            self._draw(surface)
            return
        if self._layer is None or self._layer.get_size() != surface.get_size():
            self._layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        self._layer.fill((0, 0, 0, 0))
        self._draw(self._layer)
        self._layer.set_alpha(OVERLAY_ALPHA)
        surface.blit(self._layer, (0, 0))

    def _draw(self, surface):
        held = set().union(*self.pad_fingers.values()) if self.pad_fingers else set()
        (cx, cy), r = self.pad
        pygame.draw.circle(surface, PAD_COLOR, (cx, cy), r)
        pygame.draw.circle(surface, RIM_COLOR, (cx, cy), r, 2)
        for d, (dx, dy) in DIRS.items():
            tip = (cx + dx * r * 0.8, cy + dy * r * 0.8)
            base = (cx + dx * r * 0.45, cy + dy * r * 0.45)
            px, py = -dy * r * 0.2, dx * r * 0.2
            pygame.draw.polygon(surface, PAD_HOT if d in held else RIM_COLOR,
                                [tip, (base[0] + px, base[1] + py),
                                 (base[0] - px, base[1] - py)])
        pressed = set(self.fingers.values())
        for name, ((bx, by), br, label) in self.visible_buttons().items():
            color = BUTTON_COLORS[name]
            if name in pressed:
                color = tuple(min(255, c + 60) for c in color)
            pygame.draw.circle(surface, color, (bx, by), br)
            pygame.draw.circle(surface, RIM_COLOR, (bx, by), br, 2)
            if name == "b" and self.context != "dungeon":
                label = "Back"
            elif name == "a" and self.context != "dungeon":
                label = "OK"
            text = font(max(12, int(br * (0.9 if len(label) == 1 else 0.6)))).render(
                label, True, LABEL_COLOR)
            surface.blit(text, text.get_rect(center=(bx, by)))
