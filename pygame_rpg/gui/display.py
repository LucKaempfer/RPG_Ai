"""The game window: a resizable window that shows the fixed-size canvas.

Every screen draws on an 800 x 600 canvas (``config.SCREEN_WIDTH`` x
``config.SCREEN_HEIGHT``) as before.  :class:`Display` owns the real
window, which opens as large as fits the desktop, can be resized or
maximised, and F11 toggles fullscreen.  Each frame the canvas is scaled
to the window with its aspect kept (black bars fill the rest), and
mouse positions are mapped back to canvas coordinates, so no screen
needs to know the window size.
"""

import pygame

from .. import config

# Share of the desktop the window may take when it opens (the rest is
# left for the title bar and the taskbar).
FIT_WIDTH, FIT_HEIGHT = 0.9, 0.85
MOUSE_EVENTS = (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEBUTTONUP)


def fit_scale(desktop, canvas=None):
    """Largest scale (in 0.25 steps, at least 1) at which ``canvas``
    fits ``desktop`` with room for the title bar and taskbar."""
    cw, ch = canvas or (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    dw, dh = desktop
    scale = min(dw * FIT_WIDTH / cw, dh * FIT_HEIGHT / ch)
    return max(1.0, int(scale * 4) / 4)


def letterbox(window, canvas=None):
    """Rect inside a ``window``-sized area where the canvas is shown:
    as large as fits, aspect kept, centred."""
    cw, ch = canvas or (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    ww, wh = window
    scale = min(ww / cw, wh / ch)
    w, h = max(1, round(cw * scale)), max(1, round(ch * scale))
    return pygame.Rect((ww - w) // 2, (wh - h) // 2, w, h)


class Display:
    """The window plus the canvas the screens draw on."""

    def __init__(self):
        self.canvas = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        sizes = pygame.display.get_desktop_sizes()
        desktop = sizes[0] if sizes else self.canvas.get_size()
        scale = fit_scale(desktop)
        self.window_size = (round(config.SCREEN_WIDTH * scale),
                            round(config.SCREEN_HEIGHT * scale))
        self.fullscreen = False
        self._open()

    def _open(self):
        if self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(self.window_size,
                                                  pygame.RESIZABLE)
        self._layout()

    def _layout(self):
        self.laid_out_for = self.window.get_size()
        self.view = letterbox(self.laid_out_for, self.canvas.get_size())
        self.scaled = pygame.Surface(self.view.size)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self._open()

    def handle_event(self, event):
        """Window housekeeping for one event.  Returns the event for the
        screens (mouse positions in canvas coordinates), or None when
        the event was only about the window."""
        if event.type == pygame.VIDEORESIZE:
            if not self.fullscreen:
                self.window_size = event.size
            self._layout()
            return None
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            self.toggle_fullscreen()
            return None
        if event.type in MOUSE_EVENTS:
            data = dict(event.dict, pos=self.to_canvas(event.pos))
            if "rel" in data:
                sx = self.canvas.get_width() / self.view.w
                sy = self.canvas.get_height() / self.view.h
                data["rel"] = (round(event.rel[0] * sx), round(event.rel[1] * sy))
            return pygame.event.Event(event.type, data)
        return event

    def to_canvas(self, pos):
        """Map a window position to the canvas (clamped to its edges)."""
        cw, ch = self.canvas.get_size()
        x = (pos[0] - self.view.x) * cw / self.view.w
        y = (pos[1] - self.view.y) * ch / self.view.h
        return (min(max(int(x), 0), cw - 1), min(max(int(y), 0), ch - 1))

    def present(self):
        """Scale the canvas into the window and show it."""
        if self.window.get_size() != self.laid_out_for:
            # A resize the event queue did not report (e.g. fullscreen).
            self._layout()
        if self.view.size == self.canvas.get_size():
            frame = self.canvas
        else:
            pygame.transform.smoothscale(self.canvas, self.view.size, self.scaled)
            frame = self.scaled
        self.window.fill((0, 0, 0))
        self.window.blit(frame, self.view)
        pygame.display.flip()
