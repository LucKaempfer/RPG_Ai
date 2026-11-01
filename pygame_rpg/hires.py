"""High-resolution rendering: draw the whole game at ``SCALE`` x the
canvas resolution without changing any screen's layout.

Every screen and every sprite generator works in the 800 x 600 canvas
coordinates (``config.SCREEN_WIDTH`` x ``config.SCREEN_HEIGHT``) and a
32 px sprite grid.  :func:`install` swaps in :class:`HiSurface` for
``pygame.Surface`` and wraps the ``pygame.draw`` and ``pygame.transform``
functions, so that every surface the game makes holds ``SCALE`` x as
many real pixels per side while its methods still take and report the
old ("logical") sizes and positions.  The result:

* shapes (circles, ellipses, lines, polygons, rounded rects) are drawn
  at the real resolution, so curves and slopes are smooth instead of
  stair-stepped, and fractional positions / widths (0.5 = one real
  pixel at SCALE 2) can add finer detail;
* text is rendered by a font ``SCALE`` x the size (:class:`HiFont`);
* ``set_at`` paints a SCALE x SCALE block, so pixel-art masks keep
  their look;
* surfaces made outside the game's control (``pygame.image.load``,
  the window) stay plain and are enlarged pixel for pixel when blitted
  onto a high-resolution surface.

``gui/display.py`` scales the real pixels of the canvas into the window
(smoothly when shrinking, pixel for pixel when enlarging).

The window and the on-screen touch controls (``gui/touch.py``) work in
real pixels: they use plain surfaces (:data:`Plain`) and
``screen.window_font``.  On Android the window is SCALE x the canvas
size, so the phone gets the high-resolution picture too.
"""

import math
from contextlib import contextmanager

import pygame

SCALE = 1          # real pixels per logical pixel (set by install)

# The originals, for code that works on real pixels (gui/display.py).
Plain = pygame.Surface
_DRAW = {name: getattr(pygame.draw, name) for name in (
    "rect", "polygon", "circle", "ellipse", "arc", "line", "lines",
    "aaline", "aalines")}
_TRANSFORM = {name: getattr(pygame.transform, name) for name in (
    "scale", "smoothscale", "rotate", "flip", "scale_by", "rotozoom")}
orig_scale = _TRANSFORM["scale"]
orig_smoothscale = _TRANSFORM["smoothscale"]
_installed = False


def active():
    return _installed


def raw_size(surf):
    """The real pixel size of any surface."""
    return Plain.get_size(surf)


# -- coordinate helpers -------------------------------------------------
def _edge(v):
    """A logical edge position (rects) in real pixels."""
    return int(round(v * SCALE))


def _point(p):
    """A logical point (the centre of a pixel) in real pixels."""
    off = (SCALE - 1) / 2
    return (p[0] * SCALE + off, p[1] * SCALE + off)


def _rect(r):
    if not isinstance(r, (pygame.Rect, pygame.FRect)):
        r = pygame.FRect(r)
    x0, y0 = _edge(r.x), _edge(r.y)
    return pygame.Rect(x0, y0, _edge(r.x + r.w) - x0, _edge(r.y + r.h) - y0)


def _width(w):
    return 0 if w <= 0 else max(1, int(round(w * SCALE)))


def _logical(r):
    """A real-pixel rect back in logical pixels (rounded outwards)."""
    x0, y0 = math.floor(r.x / SCALE), math.floor(r.y / SCALE)
    x1 = math.ceil((r.x + r.w) / SCALE)
    y1 = math.ceil((r.y + r.h) / SCALE)
    return pygame.Rect(x0, y0, x1 - x0, y1 - y0)


def _alpha(surf):
    return bool(Plain.get_flags(surf) & pygame.SRCALPHA)


class HiSurface(Plain):
    """A surface with SCALE x the pixels, used through logical sizes."""

    def __init__(self, size, flags=0, *args, **kwargs):
        w, h = size
        self._lsize = (max(0, math.ceil(w)), max(0, math.ceil(h)))
        super().__init__((_edge(self._lsize[0]), _edge(self._lsize[1])),
                         flags, *args, **kwargs)

    # -- sizes -------------------------------------------------------
    def get_size(self):
        return self._lsize

    def get_width(self):
        return self._lsize[0]

    def get_height(self):
        return self._lsize[1]

    def get_rect(self, **kwargs):
        r = pygame.Rect((0, 0), self._lsize)
        for k, v in kwargs.items():
            setattr(r, k, v)
        return r

    def get_frect(self, **kwargs):
        r = pygame.FRect((0, 0), self._lsize)
        for k, v in kwargs.items():
            setattr(r, k, v)
        return r

    def get_bounding_rect(self, *args, **kwargs):
        return _logical(Plain.get_bounding_rect(self, *args, **kwargs))

    # -- drawing -----------------------------------------------------
    def blit(self, source, dest=(0, 0), area=None, special_flags=0):
        if not isinstance(source, HiSurface):
            # A plain surface (loaded image, window copy): pixel blocks.
            sw, sh = Plain.get_size(source)
            source = orig_scale(source, (_edge(sw), _edge(sh)))
        if area is not None:
            area = _rect(area)
        pos = (_edge(dest[0]), _edge(dest[1]))
        return _logical(Plain.blit(self, source, pos, area, special_flags))

    def blits(self, blit_sequence, doreturn=1):
        out = [self.blit(*item) for item in blit_sequence]
        return out if doreturn else None

    def fill(self, color, rect=None, special_flags=0):
        raw = None if rect is None else _rect(rect)
        return _logical(Plain.fill(self, color, raw, special_flags))

    def get_at(self, pos):
        return Plain.get_at(self, (_edge(int(pos[0])), _edge(int(pos[1]))))

    def set_at(self, pos, color):
        Plain.fill(self, color, _rect((int(pos[0]), int(pos[1]), 1, 1)))

    def get_clip(self):
        return _logical(Plain.get_clip(self))

    def set_clip(self, rect=None):
        Plain.set_clip(self, None if rect is None else _rect(rect))

    # -- copies ------------------------------------------------------
    def copy(self):
        return adopt(Plain.copy(self), self._lsize)

    def convert(self, *args):
        return self.copy()

    def convert_alpha(self, *args):
        out = HiSurface(self._lsize, pygame.SRCALPHA)
        Plain.blit(out, self, (0, 0), special_flags=pygame.BLEND_RGBA_MAX
                   if _alpha(self) else 0)
        return out

    def subsurface(self, *rect):
        """A *copy* of the area (sprite sheets are sliced and copied
        anyway), not a view sharing the pixels."""
        r = pygame.Rect(*rect)
        out = HiSurface(r.size, pygame.SRCALPHA if _alpha(self) else 0)
        Plain.blit(out, self, (0, 0), _rect(r),
                   special_flags=pygame.BLEND_RGBA_MAX if _alpha(self) else 0)
        return out


@contextmanager
def zoom(factor):
    """Draw at ``factor`` x the usual resolution inside the block: a
    32 px sprite drawn there has the real pixels of a ``32 * factor``
    px one.  :func:`rewrap` the results before using them outside."""
    global SCALE
    old = SCALE
    SCALE = old * factor
    try:
        yield
    finally:
        SCALE = old


def rewrap(surf, factor):
    """A surface made inside ``zoom(factor)`` as one ``factor`` x the
    logical size (same real pixels): the sprite enlarged, sharp."""
    w, h = surf._lsize
    surf._lsize = (round(w * factor), round(h * factor))
    return surf


def adopt(raw, size=None):
    """A HiSurface holding the real pixels of the plain surface ``raw``
    (logical ``size``, default: raw size / SCALE rounded up)."""
    if size is None:
        rw, rh = Plain.get_size(raw)
        size = (math.ceil(rw / SCALE), math.ceil(rh / SCALE))
    alpha = _alpha(raw)
    out = HiSurface(size, pygame.SRCALPHA if alpha else 0)
    Plain.blit(out, raw, (0, 0),
               special_flags=pygame.BLEND_RGBA_MAX if alpha else 0)
    return out


def silhouette(surf, color):
    """``surf``'s shape filled with ``color`` (alpha 255), at its real
    resolution."""
    sil = pygame.mask.from_surface(surf).to_surface(
        setcolor=tuple(color[:3]) + (255,), unsetcolor=(0, 0, 0, 0))
    return adopt(sil, surf.get_size()) if isinstance(surf, HiSurface) else sil


# -- text ---------------------------------------------------------------
class HiFont:
    """A font rendering at SCALE x the size, reporting logical sizes."""

    def __init__(self, path, size):
        self._font = pygame.font.Font(path, max(1, round(size * SCALE)))

    def render(self, text, antialias, color, bgcolor=None, *args):
        raw = self._font.render(text, antialias, color, bgcolor, *args)
        return adopt(raw)

    def size(self, text):
        w, h = self._font.size(text)
        return (math.ceil(w / SCALE), math.ceil(h / SCALE))

    def get_linesize(self):
        return round(self._font.get_linesize() / SCALE)

    def get_height(self):
        return round(self._font.get_height() / SCALE)

    def get_ascent(self):
        return round(self._font.get_ascent() / SCALE)

    def get_descent(self):
        return round(self._font.get_descent() / SCALE)

    def __getattr__(self, name):
        return getattr(self._font, name)


# -- pygame.draw ----------------------------------------------------------
def _draw_rect(surface, color, rect, width=0, border_radius=0,
               border_top_left_radius=-1, border_top_right_radius=-1,
               border_bottom_left_radius=-1, border_bottom_right_radius=-1):
    f = _DRAW["rect"]
    if not isinstance(surface, HiSurface):
        return f(surface, color, rect, width, border_radius,
                 border_top_left_radius, border_top_right_radius,
                 border_bottom_left_radius, border_bottom_right_radius)
    radii = [r if r < 0 else _edge(r) for r in (
        border_top_left_radius, border_top_right_radius,
        border_bottom_left_radius, border_bottom_right_radius)]
    return _logical(f(surface, color, _rect(rect), _width(width),
                      _edge(border_radius), *radii))


def _draw_polygon(surface, color, points, width=0):
    f = _DRAW["polygon"]
    if not isinstance(surface, HiSurface):
        return f(surface, color, points, width)
    return _logical(f(surface, color, [_point(p) for p in points], _width(width)))


def _draw_circle(surface, color, center, radius, width=0, *corners, **kw):
    f = _DRAW["circle"]
    if not isinstance(surface, HiSurface):
        return f(surface, color, center, radius, width, *corners, **kw)
    return _logical(f(surface, color, _point(center),
                      radius * SCALE + (SCALE - 1) / 2, _width(width),
                      *corners, **kw))


def _draw_ellipse(surface, color, rect, width=0):
    f = _DRAW["ellipse"]
    if not isinstance(surface, HiSurface):
        return f(surface, color, rect, width)
    return _logical(f(surface, color, _rect(rect), _width(width)))


def _draw_arc(surface, color, rect, start_angle, stop_angle, width=1):
    f = _DRAW["arc"]
    if not isinstance(surface, HiSurface):
        return f(surface, color, rect, start_angle, stop_angle, width)
    return _logical(f(surface, color, _rect(rect), start_angle, stop_angle,
                      _width(width)))


def _draw_line(surface, color, start_pos, end_pos, width=1):
    f = _DRAW["line"]
    if not isinstance(surface, HiSurface):
        return f(surface, color, start_pos, end_pos, width)
    return _logical(f(surface, color, _point(start_pos), _point(end_pos),
                      _width(width)))


def _draw_lines(surface, color, closed, points, width=1):
    f = _DRAW["lines"]
    if not isinstance(surface, HiSurface):
        return f(surface, color, closed, points, width)
    return _logical(f(surface, color, closed, [_point(p) for p in points],
                      _width(width)))


def _draw_aaline(surface, color, start_pos, end_pos, *args, **kw):
    f = _DRAW["aaline"]
    if not isinstance(surface, HiSurface):
        return f(surface, color, start_pos, end_pos, *args, **kw)
    return _logical(f(surface, color, _point(start_pos), _point(end_pos)))


def _draw_aalines(surface, color, closed, points, *args, **kw):
    f = _DRAW["aalines"]
    if not isinstance(surface, HiSurface):
        return f(surface, color, closed, points, *args, **kw)
    return _logical(f(surface, color, closed, [_point(p) for p in points]))


# -- pygame.transform -------------------------------------------------
def _scale_with(name):
    f = _TRANSFORM[name]

    def scaled(surface, size, dest_surface=None):
        if not isinstance(surface, HiSurface):
            return f(surface, size) if dest_surface is None else \
                f(surface, size, dest_surface)
        w, h = size
        return adopt(f(surface, (_edge(w), _edge(h))), (w, h))
    return scaled


def _scale_by(surface, factor):
    if not isinstance(surface, HiSurface):
        return _TRANSFORM["scale_by"](surface, factor)
    fx, fy = (factor, factor) if isinstance(factor, (int, float)) else factor
    w, h = surface.get_size()
    return _transform_scale(surface, (round(w * fx), round(h * fy)))


def _passthrough(name):
    f = _TRANSFORM[name]

    def wrapped(surface, *args, **kw):
        out = f(surface, *args, **kw)
        return adopt(out) if isinstance(surface, HiSurface) else out
    return wrapped


_transform_scale = _scale_with("scale")


def _flip(surface, flip_x, flip_y):
    out = _TRANSFORM["flip"](surface, flip_x, flip_y)
    return adopt(out, surface.get_size()) if isinstance(surface, HiSurface) else out


_REPLACEMENTS = (
    (pygame.draw, {"rect": _draw_rect, "polygon": _draw_polygon,
                   "circle": _draw_circle, "ellipse": _draw_ellipse,
                   "arc": _draw_arc, "line": _draw_line, "lines": _draw_lines,
                   "aaline": _draw_aaline, "aalines": _draw_aalines}),
    (pygame.transform, {"scale": _transform_scale,
                        "smoothscale": _scale_with("smoothscale"),
                        "scale_by": _scale_by, "flip": _flip,
                        "rotate": _passthrough("rotate"),
                        "rotozoom": _passthrough("rotozoom")}),
)


def install(scale=2):
    """Draw everything made from now on at ``scale`` x resolution."""
    global SCALE, _installed
    if _installed or scale <= 1:
        return
    SCALE = scale
    pygame.Surface = HiSurface
    for module, funcs in _REPLACEMENTS:
        for name, fn in funcs.items():
            setattr(module, name, fn)
    _installed = True


def uninstall():
    """Back to plain 1x surfaces (tests)."""
    global SCALE, _installed
    if not _installed:
        return
    pygame.Surface = Plain
    for name, fn in _DRAW.items():
        setattr(pygame.draw, name, fn)
    for name, fn in _TRANSFORM.items():
        setattr(pygame.transform, name, fn)
    SCALE = 1
    _installed = False
