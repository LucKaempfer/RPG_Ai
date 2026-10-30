# pygame_rpg/gui/screen.py
"""Base class, palette and shared helpers for GUI screens.

Transition protocol
-------------------
Screens never reference each other.  ``Screen.handle_event`` returns one
of:

* ``None``             - stay on this screen
* :data:`QUIT`         - close the game
* ``"screen_name"``    - switch to another screen
* ``("name", kwargs)`` - switch with constructor keyword arguments

The state machine in ``main.py`` performs the actual swap.
"""

from pathlib import Path

import pygame
from pygame import Rect

# --- Palette (shared by all screens) ---
BG_COLOR = (22, 22, 30)
PANEL_COLOR = (38, 38, 52)
PANEL_HOT = (50, 50, 70)
TEXT_COLOR = (235, 235, 240)
DIM_TEXT = (170, 170, 185)
GOLD = (230, 190, 90)
FOCUS_BORDER = (215, 215, 240)
BORDER_COLOR = (92, 92, 118)
SHADOW_COLOR = (8, 8, 12)
TROUGH_COLOR = (15, 15, 20)


class _Quit:
    """Sentinel returned from ``handle_event`` to close the game."""

    def __repr__(self):
        return "QUIT"


QUIT = _Quit()

# --- Fonts ---
# Inter SemiBold (OFL, see assets/fonts/OFL.txt): much crisper than
# pygame's default font at small sizes.  ``size`` keeps meaning the
# default font's size, so FONT_SCALE maps it to the same text height
# (Inter is a little narrower, so nothing laid out for the old font
# overflows).
FONT_FILE = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Inter-SemiBold.ttf"
FONT_SCALE = 0.62
_FONTS = {}


def font(size: int) -> pygame.font.Font:
    """Return a cached game font for the given pixel size (pygame's
    default font if the font file is missing)."""
    if size not in _FONTS:
        try:
            _FONTS[size] = pygame.font.Font(FONT_FILE, max(1, round(size * FONT_SCALE)))
        except (OSError, pygame.error):
            _FONTS[size] = pygame.font.Font(None, size)
    return _FONTS[size]


# --- Shared drawing (the polished look every screen uses) ---
_BACKGROUNDS = {}
VIGNETTE = 110   # alpha of the darkening in the very corners


def _lighter(color, amount):
    return tuple(min(255, c + amount) for c in color[:3])


def draw_background(surface):
    """Fill ``surface`` with the menu background: BG_COLOR, a touch
    lighter at the top and darker at the bottom, with dark corners."""
    size = surface.get_size()
    if size not in _BACKGROUNDS:
        w, h = size
        bg = pygame.Surface(size)
        for y in range(h):
            t = y / max(1, h - 1)
            d = round(8 * (1 - t)) - round(6 * t)
            bg.fill(tuple(max(0, min(255, c + d)) for c in BG_COLOR), (0, y, w, 1))
        # Vignette: a small map of how dark each spot is (darkest in
        # the corners), smoothly stretched over the whole screen.
        gw, gh = 100, 75
        small = pygame.Surface((gw, gh), pygame.SRCALPHA)
        for gy in range(gh):
            for gx in range(gw):
                dx, dy = (gx + 0.5) / gw * 2 - 1, (gy + 0.5) / gh * 2 - 1
                d = min(1.0, (dx * dx + dy * dy) / 2) ** 1.5
                small.set_at((gx, gy), (0, 0, 0, round(VIGNETTE * d)))
        shade = pygame.transform.smoothscale(small, size)
        bg.blit(shade, (0, 0))
        _BACKGROUNDS[size] = bg
    surface.blit(_BACKGROUNDS[size], (0, 0))


def draw_panel(surface, rect, color=PANEL_COLOR, border=BORDER_COLOR,
               radius=8, width=2, shadow=True):
    """A raised panel: soft drop shadow, the fill, a faint highlight
    along the top edge and the border."""
    rect = Rect(rect)
    if shadow:
        pygame.draw.rect(surface, SHADOW_COLOR, rect.move(0, 3), border_radius=radius)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if rect.h > 2 * radius and rect.w > 2 * radius:
        pygame.draw.line(surface, _lighter(color, 14),
                         (rect.x + radius, rect.y + width),
                         (rect.right - radius - 1, rect.y + width))
    if width:
        pygame.draw.rect(surface, border, rect, width=width, border_radius=radius)


def draw_bar(surface, rect, value, maximum, color, radius=None,
             border=BORDER_COLOR):
    """A meter: dark trough, the filled part with a light stripe along
    its top (so it reads as glossy) and a thin border."""
    rect = Rect(rect)
    radius = rect.h // 2 if radius is None else radius
    pygame.draw.rect(surface, TROUGH_COLOR, rect, border_radius=radius)
    if maximum > 0 and value > 0:
        fill = rect.copy()
        fill.w = max(2, int(rect.w * min(value, maximum) / maximum))
        pygame.draw.rect(surface, color, fill, border_radius=radius)
        if fill.h >= 6 and fill.w > 2 * radius:
            gloss = Rect(fill.x + radius, fill.y + 2, fill.w - 2 * radius,
                         max(1, fill.h // 4))
            surface.fill(_lighter(color, 45), gloss)
    pygame.draw.rect(surface, border, rect, width=1, border_radius=radius)


class Screen:
    """Base class for all GUI screens.

    Subclasses set ``name`` and override :meth:`draw` (and, when they
    take input, :meth:`handle_event`).  The state machine in ``main.py``
    calls the three hooks once per frame and inspects the return value
    of :meth:`handle_event` for a transition request.
    """

    name = "screen"
    # Ambient loop while this screen shows ("sewer") or None.
    ambience = None

    def __init__(self, screen: pygame.Surface):
        self.screen = screen

    # -- hooks called by the state machine -------------------------------
    def handle_event(self, event):
        """Handle one pygame event; return a transition request or None."""
        if event.type == pygame.QUIT:
            return QUIT
        return None

    def handle_update(self, dt):
        """Per-frame logic (timers, animations).  May return a transition
        request like ``handle_event``.  Default: nothing."""

    def suspend(self):
        """The app is going to the background (Android may close it
        there without a QUIT): save anything that must survive.
        Default: nothing."""

    def draw(self, surface):
        """Draw the screen.  Subclasses must override."""
        raise NotImplementedError


class Button:
    """A simple mouse-driven rectangular button."""

    def __init__(self, label, rect, size=24):
        self.label = label
        self.rect = Rect(rect)
        self.font_size = size

    def draw(self, surface, hot=False):
        draw_panel(surface, self.rect, PANEL_HOT if hot else PANEL_COLOR,
                   FOCUS_BORDER if hot else BORDER_COLOR, radius=6)
        if hot:   # gold marker on the focused button's left edge
            mark = Rect(self.rect.x + 6, self.rect.y + 7, 3, self.rect.h - 14)
            if mark.h > 0:
                pygame.draw.rect(surface, GOLD, mark, border_radius=1)
        text = font(self.font_size).render(self.label, True, TEXT_COLOR)
        surface.blit(text, text.get_rect(center=self.rect.center))
