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


class _Quit:
    """Sentinel returned from ``handle_event`` to close the game."""

    def __repr__(self):
        return "QUIT"


QUIT = _Quit()

# --- Fonts ---
_FONTS = {}


def font(size: int) -> pygame.font.Font:
    """Return a cached default pygame font for the given pixel size."""
    if size not in _FONTS:
        _FONTS[size] = pygame.font.Font(None, size)
    return _FONTS[size]


class Screen:
    """Base class for all GUI screens.

    Subclasses set ``name`` and override :meth:`draw` (and, when they
    take input, :meth:`handle_event`).  The state machine in ``main.py``
    calls the three hooks once per frame and inspects the return value
    of :meth:`handle_event` for a transition request.
    """

    name = "screen"

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
        pygame.draw.rect(surface, PANEL_HOT if hot else PANEL_COLOR,
                         self.rect, border_radius=6)
        pygame.draw.rect(surface, FOCUS_BORDER if hot else BORDER_COLOR,
                         self.rect, width=2, border_radius=6)
        text = font(self.font_size).render(self.label, True, TEXT_COLOR)
        surface.blit(text, text.get_rect(center=self.rect.center))
