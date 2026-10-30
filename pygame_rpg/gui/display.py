"""The game window: a resizable window that shows the fixed-size canvas.

Every screen draws on an 800 x 600 canvas (``config.SCREEN_WIDTH`` x
``config.SCREEN_HEIGHT``) as before.  :class:`Display` owns the real
window, which opens as large as fits the desktop, can be resized or
maximised, and F11 toggles fullscreen.  Each frame the canvas is scaled
to the window with its aspect kept (black bars fill the rest), and
mouse positions are mapped back to canvas coordinates, so no screen
needs to know the window size.

The brightness and the fullscreen flag come from ``settings.current``
(the settings screen changes them; F11 flips fullscreen and saves).

Touch screens (``device.TOUCH``): the bars beside the canvas are kept at
least ``TOUCH_BAR`` x the window height wide and hold the on-screen
controls (``gui/touch.py``), which see the events first.  On Android the
window is always fullscreen and the GPU does the scaling (``SCALED``):
the window is a logical surface 600 px high (wider, to match the
phone's shape) with the canvas unscaled in the middle.  The phone's Back
button counts as Escape.
"""

import pygame

from .. import config, device, settings
from .touch import TouchControls

# Share of the desktop the window may take when it opens (the rest is
# left for the title bar and the taskbar).
FIT_WIDTH, FIT_HEIGHT = 0.9, 0.85
MOUSE_EVENTS = (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEBUTTONUP)
TOUCH_BAR = 0.28   # least width of each control bar, x window height


def fit_scale(desktop, canvas=None):
    """Largest scale (in 0.25 steps, at least 1) at which ``canvas``
    fits ``desktop`` with room for the title bar and taskbar."""
    cw, ch = canvas or (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    dw, dh = desktop
    scale = min(dw * FIT_WIDTH / cw, dh * FIT_HEIGHT / ch)
    return max(1.0, int(scale * 4) / 4)


def letterbox(window, canvas=None, side=0):
    """Rect inside a ``window``-sized area where the canvas is shown:
    as large as fits, aspect kept, centred.  ``side`` px are kept free
    on the left and the right (for touch controls)."""
    cw, ch = canvas or (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    ww, wh = window
    scale = min(max(1, ww - 2 * side) / cw, wh / ch)
    w, h = max(1, round(cw * scale)), max(1, round(ch * scale))
    return pygame.Rect((ww - w) // 2, (wh - h) // 2, w, h)


def android_size(desktop, canvas=None):
    """Logical window size on Android: the phone's shape (landscape),
    at least the canvas height and wide enough for both control bars,
    so the canvas is shown 1:1 and the GPU scales the whole window."""
    cw, ch = canvas or (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    dw, dh = max(desktop), min(desktop)
    aspect = dw / dh
    w = max(cw + 2 * round(ch * TOUCH_BAR), round(ch * aspect))
    return (w, max(ch, round(w / aspect)))


class Display:
    """The window plus the canvas the screens draw on."""

    def __init__(self):
        self.canvas = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        sizes = pygame.display.get_desktop_sizes()
        desktop = sizes[0] if sizes else self.canvas.get_size()
        scale = fit_scale(desktop)
        self.window_size = (round(config.SCREEN_WIDTH * scale),
                            round(config.SCREEN_HEIGHT * scale))
        self.android_size = android_size(desktop) if device.IS_ANDROID else None
        self.fullscreen = device.IS_ANDROID or settings.current.fullscreen
        self.touch = TouchControls() if device.TOUCH else None
        self.screen_name = None
        self._open()

    def _open(self):
        if self.android_size:
            self.window = pygame.display.set_mode(
                self.android_size, pygame.SCALED | pygame.FULLSCREEN)
        elif self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(self.window_size,
                                                  pygame.RESIZABLE)
        self._layout()

    def _layout(self):
        self.laid_out_for = self.window.get_size()
        side = round(self.laid_out_for[1] * TOUCH_BAR) if self.touch else 0
        self.view = letterbox(self.laid_out_for, self.canvas.get_size(), side)
        if self.touch:
            self.touch.layout(self.laid_out_for, self.view)
        self.scaled = pygame.Surface(self.view.size)
        self.boost = pygame.Surface(self.view.size)

    def toggle_fullscreen(self):
        if device.IS_ANDROID:
            return   # always fullscreen
        settings.current.fullscreen = not settings.current.fullscreen
        settings.save()

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
        if event.type == pygame.KEYDOWN and event.key == pygame.K_AC_BACK:
            return pygame.event.Event(pygame.KEYDOWN, dict(event.dict, key=pygame.K_ESCAPE))
        if self.touch and self.touch.handle_event(event):
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
        if (not device.IS_ANDROID
                and self.fullscreen != settings.current.fullscreen):
            self.fullscreen = settings.current.fullscreen
            self._open()
        if self.window.get_size() != self.laid_out_for:
            # A resize the event queue did not report (e.g. fullscreen).
            self._layout()
        if self.view.size == self.canvas.get_size():
            self.scaled.blit(self.canvas, (0, 0))
        else:
            pygame.transform.smoothscale(self.canvas, self.view.size, self.scaled)
        self._brighten(settings.current.brightness)
        self.window.fill((0, 0, 0))
        self.window.blit(self.scaled, self.view)
        if self.touch:
            self.touch.draw(self.window)
        pygame.display.flip()

    def update(self, dt, screen_name):
        """Once per frame: which screen is shown (the touch buttons
        change meaning with it; a screen change hides the on-screen
        keyboard) and the D-pad's menu repeat."""
        if screen_name != self.screen_name:
            self.screen_name = screen_name
            device.hide_keyboard()
        if self.touch:
            self.touch.set_context(screen_name)
            self.touch.update(dt)

    def _brighten(self, level):
        """Scale every colour of the frame by ``level`` (1 = unchanged).
        Black stays black, so the fog of war stays dark."""
        if level < 1:
            v = int(255 * level)
            self.scaled.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        elif level > 1:
            # frame + frame x (level - 1), clipped at white.
            v = min(255, int(255 * (level - 1)))
            self.boost.blit(self.scaled, (0, 0))
            self.boost.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            self.scaled.blit(self.boost, (0, 0),
                             special_flags=pygame.BLEND_RGB_ADD)
