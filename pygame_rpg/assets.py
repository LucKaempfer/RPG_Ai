# pygame_rpg/assets.py
"""Asset manager for the Pygame RPG.

Loads sprites from the ``assets/`` directory inside this package
(``pygame_rpg/assets/``), with
caching.  When an image file is missing, a programmatically generated
placeholder is created *and saved* so that development never crashes on
missing art and the file layout is stable: drop real art with the same
filenames and it is picked up automatically.

Layouts (all frames are 32x32 pixels):

* ``tileset.png``          10 x 1 grid, one tile per index (see TILE_*);
  the original stone set, kept for real art / other screens
* ``sewer/tiles_v2.png``   20 x 1 grid, the dungeon's sewer set (SEWER_*)
* hero frames (``AssetManager.hero_frames(look)``, drawn in code per
  character look, not a file): 8 x 4 grid
    columns: 0-1 idle, 2-5 walk, 6-7 attack
    rows:    0 down, 1 up, 2 left, 3 right
* ``enemies/<name>.png``   8 x 1 grid:
    0-1 idle, 2-3 attack, 4-5 hurt, 6-7 death
* ``items/<key>.png``      single 32x32 icon
* ``ui/<name>.png``        single UI sprite
* ``objects/chest.png``    2 x 1 grid: 0 closed, 1 open
"""

import math
import pygame
from pathlib import Path

# All generated/loaded art lives here (sibling of this file).
ASSETS_DIR = Path(__file__).parent / "assets"

# Frame size for every sprite in the game.
FRAME_SIZE = 32

# ---------------------------------------------------------------------------
# Tileset layout: 10 x 1 grid, index == TILE_* constant.
# ---------------------------------------------------------------------------
TILE_FLOOR = 0
TILE_FLOOR_DARK = 1
TILE_WALL = 2
TILE_WALL_DARK = 3
TILE_CORRIDOR = 4
TILE_DOOR = 5
TILE_DOOR_OPEN = 6
TILE_STAIRS_DOWN = 7
TILE_BASE_FLOOR = 8
TILE_WATER = 9
TILESET_COLS, TILESET_ROWS = 10, 1

# ---------------------------------------------------------------------------
# Sewer tileset (the dungeon look): 16 x 1 grid, index == SEWER_* constant.
# Variants are picked per cell by dungeon.py (deterministic per position).
# ---------------------------------------------------------------------------
(SEWER_FLOOR, SEWER_FLOOR_CRACK, SEWER_FLOOR_MOSS, SEWER_FLOOR_PUDDLE,
 SEWER_FLOOR_DRAIN, SEWER_WALL, SEWER_WALL_STAIN, SEWER_WALL_PIPE,
 SEWER_WALL_MOSS, SEWER_GRATE, SEWER_WALKWAY, SEWER_GATE, SEWER_MANHOLE,
 SEWER_SLUDGE, SEWER_WALL_DARK, SEWER_FLOOR_BONES,
 # Doorways: floor with a thin iron gate along the side the corridor
 # leaves from (N = corridor above the door cell, and so on).
 SEWER_GATE_N, SEWER_GATE_S, SEWER_GATE_W, SEWER_GATE_E) = range(20)
SEWER_COLS, SEWER_ROWS = 20, 1

# ---------------------------------------------------------------------------
# Hero sheet layout: 8 x 4 grid.
# ---------------------------------------------------------------------------
HERO_COLS, HERO_ROWS = 8, 4
HERO_IDLE_COLS = (0, 1)
HERO_WALK_COLS = (2, 3, 4, 5)
HERO_ATTACK_COLS = (6, 7)
HERO_DIR_DOWN, HERO_DIR_UP, HERO_DIR_LEFT, HERO_DIR_RIGHT = 0, 1, 2, 3

# ---------------------------------------------------------------------------
# Enemy sheet layout: 8 x 1 grid.
# ---------------------------------------------------------------------------
ENEMY_COLS, ENEMY_ROWS = 8, 1
ENEMY_IDLE = (0, 1)
ENEMY_ATTACK = (2, 3)
ENEMY_HURT = (4, 5)
ENEMY_DEATH = (6, 7)

# Names of the enemies the game can spawn (one sheet file each).
ENEMY_NAMES = ("slime", "goblin", "bat", "rat", "skeleton", "rat_king")


class AssetManager:
    """Loads, caches, and (when needed) generates sprite images."""

    def __init__(self, assets_dir: Path = ASSETS_DIR):
        self.assets_dir = assets_dir
        self._cache = {}

    # -- paths ---------------------------------------------------------
    def path(self, name: str) -> Path:
        return self.assets_dir / name

    def save_image(self, surface: pygame.Surface, name: str):
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(surface, str(p))

    # -- loading -------------------------------------------------------
    def load_image(self, name: str) -> pygame.Surface:
        """Return the (cached) surface for ``name``, generating a
        placeholder and saving it to disk if the file is missing."""
        key = ("img", name)
        if key not in self._cache:
            p = self.path(name)
            if p.exists():
                surf = pygame.image.load(str(p))
                # convert_alpha() needs a display; skip it in headless runs.
                if pygame.display.get_init():
                    surf = surf.convert_alpha()
            else:
                surf = self._generate(name)
                self.save_image(surf, name)
            self._cache[key] = surf
        return self._cache[key]

    def load_sheet(self, name: str, cols: int, rows: int):
        """Return a list of frames from a sheet, row-major."""
        key = ("sheet", name, cols, rows)
        if key not in self._cache:
            self._cache[key] = _slice(self.load_image(name), cols, rows)
        return self._cache[key]

    def hero_frames(self, look=None):
        """The hero's frames (HERO_COLS x HERO_ROWS, row-major) drawn in
        ``look`` (a ``Player.look`` dict).  Drawn in code and cached per
        look; nothing is saved to disk."""
        key = ("hero", tuple(sorted((look or {}).items())))
        if key not in self._cache:
            self._cache[key] = _slice(_gen_hero_sheet(look), HERO_COLS, HERO_ROWS)
        return self._cache[key]

    # -- placeholder generation ---------------------------------------
    def _generate(self, name: str) -> pygame.Surface:
        """Dispatch to the right generator for a missing file."""
        if name == "tileset.png":
            return _gen_tileset()
        if name == "sewer/tiles_v2.png":
            return _gen_sewer_tiles()
        if name.startswith("enemies/"):
            return _gen_enemy_sheet(name.rsplit("/", 1)[-1].removesuffix(".png"))
        if name.startswith("items/"):
            return _gen_item_icon(name.rsplit("/", 1)[-1].removesuffix(".png"))
        if name == "objects/chest.png":
            return _gen_chest()
        if name.startswith("ui/"):
            return _gen_ui(name.rsplit("/", 1)[-1].removesuffix(".png"))
        raise FileNotFoundError(f"no generator for asset: {name}")


def _slice(surf: pygame.Surface, cols: int, rows: int):
    """Cut a sheet into its frames, row-major."""
    w, h = surf.get_size()
    fw, fh = w // cols, h // rows
    return [surf.subsurface(pygame.Rect(c * fw, r * fh, fw, fh)).copy()
            for r in range(rows) for c in range(cols)]


# Module-level convenience instance.
assets = AssetManager()


# ---------------------------------------------------------------------------
# Placeholder generators
# ---------------------------------------------------------------------------

def _new_sheet(cols: int, rows: int) -> pygame.Surface:
    """Blank transparent sheet of the given frame count."""
    return pygame.Surface((cols * FRAME_SIZE, rows * FRAME_SIZE), pygame.SRCALPHA)


def _gen_tileset() -> pygame.Surface:
    surf = _new_sheet(TILESET_COLS, TILESET_ROWS)
    # -- floors: dark stone with speckles
    for idx, base in (
        (TILE_FLOOR, (70, 66, 60)),
        (TILE_FLOOR_DARK, (56, 53, 49)),
        (TILE_CORRIDOR, (46, 43, 40)),
    ):
        r = pygame.Rect(idx * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
        surf.fill(base, r)
        for dx, dy in ((6, 8), (21, 14), (10, 24), (25, 27)):
            pygame.draw.circle(surf, tuple(c - 14 for c in base), (r.x + dx, r.y + dy), 2)
    # -- walls: brick pattern
    for idx, base, line in (
        (TILE_WALL, (110, 105, 100), (80, 76, 72)),
        (TILE_WALL_DARK, (85, 81, 78), (60, 57, 54)),
    ):
        r = pygame.Rect(idx * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
        surf.fill(base, r)
        for row in range(4):
            y = r.y + row * 8 + 7
            pygame.draw.line(surf, line, (r.x, y), (r.x + FRAME_SIZE - 1, y), 2)
            offset = 8 if row % 2 else 16
            for col in range(2):
                x = r.x + offset + col * 16
                pygame.draw.line(surf, line, (x, r.y + row * 8), (x, y - 1), 2)
    # -- door: planks + knob
    r = pygame.Rect(TILE_DOOR * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
    surf.fill((94, 66, 42), r)
    for x in range(6, FRAME_SIZE, 8):
        pygame.draw.line(surf, (70, 48, 30), (r.x + x, r.y + 2), (r.x + x, r.y + FRAME_SIZE - 2))
    pygame.draw.rect(surf, (60, 42, 26), r, 2)
    pygame.draw.circle(surf, (220, 190, 90), (r.x + 26, r.y + 17), 2)
    # -- open door: dark opening in the frame
    r = pygame.Rect(TILE_DOOR_OPEN * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
    surf.fill((0, 0, 0), r)
    pygame.draw.rect(surf, (94, 66, 42), r, 3)
    # -- stairs down: three descending steps
    r = pygame.Rect(TILE_STAIRS_DOWN * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
    surf.fill((70, 66, 60), r)
    for i, shade in enumerate((52, 40, 28)):
        pygame.draw.rect(surf, (shade, shade - 4, shade - 8),
                         (r.x + 4, r.y + 3 + i * 9, FRAME_SIZE - 8, 8))
    # -- base floor: warm wood planks
    r = pygame.Rect(TILE_BASE_FLOOR * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
    surf.fill((150, 128, 96), r)
    pygame.draw.line(surf, (172, 150, 118), (r.x + 4, r.y + 24), (r.x + 24, r.y + 4))
    pygame.draw.line(surf, (118, 98, 72), (r.x + 8, r.y + 28), (r.x + 28, r.y + 8))
    pygame.draw.line(surf, (172, 150, 118), (r.x + 14, r.y + 28), (r.x + 28, r.y + 14))
    # -- water: blue with wave arcs
    r = pygame.Rect(TILE_WATER * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
    surf.fill((40, 80, 140), r)
    for x, y in ((4, 10), (18, 14), (8, 24), (20, 26)):
        pygame.draw.arc(surf, (95, 145, 205), (r.x + x, r.y + y - 3, 12, 8), 0, math.pi, 2)
    return surf


def _sewer_floor(surf, r, rng):
    """Mossy flagstones: grey-green slabs with dark joints."""
    surf.fill((58, 64, 56), r)
    for (x, y, w, h) in ((0, 0, 15, 15), (16, 0, 16, 11), (0, 16, 11, 16),
                         (12, 16, 20, 16), (16, 12, 16, 3)):
        shade = rng.randint(-6, 6)
        pygame.draw.rect(surf, (62 + shade, 68 + shade, 58 + shade),
                         (r.x + x + 1, r.y + y + 1, w - 2, h - 2))
    for _ in range(6):
        pygame.draw.circle(surf, (48, 54, 46),
                           (r.x + rng.randint(2, 29), r.y + rng.randint(2, 29)), 1)


def _sewer_wall(surf, r, rng, base=(64, 72, 62), mortar=(36, 42, 36)):
    """Slimy bricks: staggered courses, dark mortar, a lighter top lip."""
    surf.fill(mortar, r)
    for row in range(4):
        off = 0 if row % 2 else 8
        for col in range(-1, 3):
            x = col * 16 + off
            shade = rng.randint(-8, 8)
            pygame.draw.rect(surf, tuple(max(0, c + shade) for c in base),
                             (r.x + max(0, x) + 1, r.y + row * 8 + 1,
                              min(15, 32 - max(0, x)) - 1 if x >= 0 else 15 + x - 1, 6))
    pygame.draw.line(surf, tuple(c + 18 for c in base), (r.x, r.y), (r.right - 1, r.y), 1)


def _gen_sewer_tiles() -> pygame.Surface:
    import random
    rng = random.Random(7)              # same art on every machine
    surf = _new_sheet(SEWER_COLS, SEWER_ROWS)
    cell = lambda i: pygame.Rect(i * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
    slime, slime_dark = (96, 150, 60), (60, 104, 40)
    rust, rust_dark = (140, 82, 44), (92, 52, 30)

    for i in (SEWER_FLOOR, SEWER_FLOOR_CRACK, SEWER_FLOOR_MOSS,
              SEWER_FLOOR_PUDDLE, SEWER_FLOOR_DRAIN, SEWER_FLOOR_BONES):
        _sewer_floor(surf, cell(i), rng)
    r = cell(SEWER_FLOOR_CRACK)
    pygame.draw.lines(surf, (34, 38, 32), False,
                      [(r.x + 5, r.y + 4), (r.x + 12, r.y + 13), (r.x + 10, r.y + 20),
                       (r.x + 19, r.y + 27)], 2)
    r = cell(SEWER_FLOOR_MOSS)
    for (x, y, rad) in ((8, 9, 6), (14, 13, 5), (22, 22, 7), (6, 25, 4)):
        pygame.draw.circle(surf, slime_dark, (r.x + x, r.y + y), rad)
        pygame.draw.circle(surf, slime, (r.x + x - 1, r.y + y - 1), rad - 2)
    r = cell(SEWER_FLOOR_PUDDLE)
    pygame.draw.ellipse(surf, (44, 66, 50), (r.x + 4, r.y + 8, 24, 16))
    pygame.draw.ellipse(surf, (62, 92, 66), (r.x + 7, r.y + 11, 18, 10))
    pygame.draw.line(surf, (120, 160, 120), (r.x + 11, r.y + 13), (r.x + 16, r.y + 13), 1)
    r = cell(SEWER_FLOOR_DRAIN)
    pygame.draw.circle(surf, (30, 32, 30), r.center, 11)
    pygame.draw.circle(surf, (96, 100, 96), r.center, 11, 2)
    for dx in (-6, -2, 2, 6):
        pygame.draw.line(surf, (96, 100, 96), (r.centerx + dx, r.centery - 9),
                         (r.centerx + dx, r.centery + 9), 2)
    r = cell(SEWER_FLOOR_BONES)
    bone = (214, 206, 186)
    pygame.draw.line(surf, bone, (r.x + 7, r.y + 20), (r.x + 20, r.y + 12), 3)
    for (x, y) in ((6, 21), (8, 18), (20, 11), (21, 14)):
        pygame.draw.circle(surf, bone, (r.x + x, r.y + y), 2)
    pygame.draw.circle(surf, bone, (r.x + 23, r.y + 23), 4)
    pygame.draw.circle(surf, (40, 40, 40), (r.x + 22, r.y + 22), 1)

    for i in (SEWER_WALL, SEWER_WALL_STAIN, SEWER_WALL_PIPE, SEWER_WALL_MOSS):
        _sewer_wall(surf, cell(i), rng)
    _sewer_wall(surf, cell(SEWER_WALL_DARK), rng, base=(44, 50, 44), mortar=(26, 30, 26))
    r = cell(SEWER_WALL_STAIN)
    for x, length in ((7, 18), (16, 26), (24, 12)):
        pygame.draw.line(surf, slime_dark, (r.x + x, r.y), (r.x + x, r.y + length), 3)
        pygame.draw.circle(surf, slime, (r.x + x, r.y + length), 2)
    r = cell(SEWER_WALL_PIPE)
    pygame.draw.rect(surf, rust_dark, (r.x + 8, r.y + 8, 16, 14), border_radius=3)
    pygame.draw.rect(surf, rust, (r.x + 9, r.y + 9, 14, 12), border_radius=3)
    pygame.draw.circle(surf, (20, 24, 20), (r.centerx, r.y + 15), 5)
    pygame.draw.line(surf, slime, (r.centerx, r.y + 18), (r.centerx, r.bottom - 1), 3)
    r = cell(SEWER_WALL_MOSS)
    for x in range(0, 32, 5):
        h = rng.randint(4, 11)
        pygame.draw.ellipse(surf, slime_dark, (r.x + x - 2, r.bottom - h, 8, h + 4))
        pygame.draw.ellipse(surf, slime, (r.x + x - 1, r.bottom - h + 2, 5, h))

    # Corridors: a metal grate over sludge, and a wet stone walkway.
    r = cell(SEWER_GRATE)
    surf.fill((34, 56, 34), r)
    for y in range(2, 32, 6):
        pygame.draw.line(surf, (54, 84, 48), (r.x + 2, r.y + y + 2), (r.x + 10, r.y + y + 2), 1)
    for x in range(1, 32, 6):
        pygame.draw.line(surf, (92, 96, 92), (r.x + x, r.y), (r.x + x, r.bottom - 1), 3)
    for y in (0, 31):
        pygame.draw.line(surf, (70, 74, 70), (r.x, r.y + y), (r.right - 1, r.y + y), 2)
    r = cell(SEWER_WALKWAY)
    surf.fill((52, 58, 52), r)
    for (x, y) in ((4, 6), (18, 10), (10, 22), (24, 26)):
        pygame.draw.ellipse(surf, (66, 86, 70), (r.x + x, r.y + y, 7, 3))
    pygame.draw.line(surf, (40, 44, 40), (r.x, r.y + 16), (r.right - 1, r.y + 16), 1)

    # Door: rusty iron gate.
    r = cell(SEWER_GATE)
    surf.fill((20, 24, 20), r)
    for x in range(3, 32, 6):
        pygame.draw.line(surf, rust, (r.x + x, r.y + 1), (r.x + x, r.bottom - 2), 3)
    for y in (5, 26):
        pygame.draw.line(surf, rust_dark, (r.x, r.y + y), (r.right - 1, r.y + y), 3)
    pygame.draw.rect(surf, rust_dark, r, 2)

    # Doorways: flagstone floor with a thin gate on one edge.  Drawn once
    # for the top edge, then rotated for the other three.
    gate = pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA)
    _sewer_floor(gate, gate.get_rect(), rng)
    pygame.draw.rect(gate, (16, 18, 16), (0, 0, 32, 8))                 # shadowed gap
    for x in range(6, 27, 4):
        pygame.draw.line(gate, rust, (x, 1), (x, 6), 2)                 # bars
    pygame.draw.line(gate, rust_dark, (0, 1), (31, 1), 2)               # top rail
    pygame.draw.line(gate, rust_dark, (0, 6), (31, 6), 2)               # bottom rail
    for x in (0, 27):
        pygame.draw.rect(gate, (88, 92, 86), (x, 0, 5, 9))              # stone posts
        pygame.draw.rect(gate, (60, 64, 58), (x, 0, 5, 9), 1)
    for idx, angle in ((SEWER_GATE_N, 0), (SEWER_GATE_W, 90),
                       (SEWER_GATE_S, 180), (SEWER_GATE_E, -90)):
        surf.blit(pygame.transform.rotate(gate, angle), cell(idx))

    # Stairs down: an open manhole with a ladder.
    r = cell(SEWER_MANHOLE)
    _sewer_floor(surf, r, rng)
    pygame.draw.circle(surf, (110, 110, 104), r.center, 14)
    pygame.draw.circle(surf, (8, 10, 8), r.center, 11)
    for y in (-6, -1, 4):
        pygame.draw.line(surf, rust, (r.centerx - 6, r.centery + y), (r.centerx + 6, r.centery + y), 2)
    for x in (-6, 6):
        pygame.draw.line(surf, rust_dark, (r.centerx + x, r.centery - 9), (r.centerx + x, r.centery + 8), 2)

    # Sludge: green water with ripples.
    r = cell(SEWER_SLUDGE)
    surf.fill((44, 84, 40), r)
    for x, y in ((3, 8), (16, 12), (7, 22), (19, 26)):
        pygame.draw.arc(surf, (96, 150, 70), (r.x + x, r.y + y - 3, 11, 7), 0, math.pi, 2)
    return surf


# ---------------------------------------------------------------------------
# Hero looks (character customization).  A look is a dict of option
# indices, one per LOOK_OPTIONS key (``player.LOOK_KEYS``); the hero is
# drawn from it in code, so every look gets its own frames.
# ---------------------------------------------------------------------------
LOOK_OPTIONS = {
    "skin": (("Pale", (245, 216, 192)), ("Light", (235, 200, 160)),
             ("Tan", (205, 160, 115)), ("Brown", (152, 106, 72)),
             ("Dark", (102, 70, 50))),
    "hair": (("Short", "short"), ("Long", "long"), ("Spiky", "spiky"),
             ("Bald", "bald"), ("Helmet", "helmet"), ("Hood", "hood")),
    "hair_color": (("Brown", (112, 74, 42)), ("Black", (42, 38, 38)),
                   ("Blond", (226, 196, 112)), ("Red", (178, 72, 40)),
                   ("Grey", (150, 150, 156)), ("White", (236, 236, 230))),
    "tunic": (("Blue", (70, 130, 210)), ("Red", (190, 62, 60)),
              ("Green", (72, 150, 82)), ("Purple", (132, 82, 172)),
              ("Brown", (132, 96, 62)), ("Black", (58, 58, 68))),
}
LOOK_LABELS = {"skin": "Skin", "hair": "Hair", "hair_color": "Hair colour",
               "tunic": "Tunic"}


def look_choice(look, key):
    """(label, value) of the option ``look`` picks for ``key`` (index
    wraps, a missing key means the first option)."""
    options = LOOK_OPTIONS[key]
    return options[int((look or {}).get(key, 0)) % len(options)]


def _shade(color, d):
    return tuple(max(0, min(255, c + d)) for c in color)


def _gen_hero_sheet(look=None) -> pygame.Surface:
    """Draw the hero in ``look`` for every (direction, phase) cell."""
    surf = _new_sheet(HERO_COLS, HERO_ROWS)
    for row in range(HERO_ROWS):
        for col in range(HERO_COLS):
            px, py = col * FRAME_SIZE, row * FRAME_SIZE
            _draw_hero_frame(surf, px, py, row, col, look or {})
    return surf


def _draw_hero_frame(surf: pygame.Surface, px: int, py: int,
                     direction: int, col: int, look: dict):
    """Draw one 32x32 hero frame at (px, py) facing ``direction``."""
    skin = look_choice(look, "skin")[1]
    tunic = look_choice(look, "tunic")[1]
    x, y = px + 16, py + 16  # centre of the frame
    attacking = col in HERO_ATTACK_COLS
    # Bob the body slightly on alternate frames for a life-like idle/walk.
    bob = 1 if (col % 2 == 1) else 0
    side_view = direction in (HERO_DIR_LEFT, HERO_DIR_RIGHT)
    # Legs and boots.
    for lx in ((x,) if side_view else (x - 3, x + 3)):
        pygame.draw.rect(surf, (62, 54, 48), (lx - 2, y + 6, 4, 6))
        pygame.draw.rect(surf, (46, 32, 24), (lx - 2, y + 11, 4, 3))
    # Tunic with a belt.
    top = y - 3 - bob
    width = 10 if side_view else 12
    body = pygame.Rect(x - width // 2, top, width, 11)
    pygame.draw.rect(surf, tunic, body, border_radius=3)
    pygame.draw.rect(surf, _shade(tunic, -50), body, 1, border_radius=3)
    pygame.draw.line(surf, (92, 62, 36), (body.left, top + 7),
                     (body.right - 1, top + 7), 2)
    # Arms: both at the sides from the front / back, one from the side.
    if side_view:
        ax = x + (2 if direction == HERO_DIR_RIGHT else -2)
        pygame.draw.rect(surf, _shade(tunic, -25), (ax - 1, top + 1, 3, 6))
        pygame.draw.rect(surf, skin, (ax - 1, top + 7, 3, 2))
    else:
        for ax in (x - 8, x + 6):
            pygame.draw.rect(surf, _shade(tunic, -25), (ax, top + 1, 3, 6))
            pygame.draw.rect(surf, skin, (ax, top + 7, 3, 2))
    # Head.
    hy = y - 9 - bob
    pygame.draw.circle(surf, skin, (x, hy), 6)
    _draw_hair(surf, x, hy, direction, look, tunic, skin)
    if direction == HERO_DIR_DOWN:
        for ex in (x - 2, x + 2):
            pygame.draw.rect(surf, (25, 20, 20), (ex, hy, 1, 2))
    elif side_view:
        ex = x + (3 if direction == HERO_DIR_RIGHT else -4)
        pygame.draw.rect(surf, (25, 20, 20), (ex, hy, 1, 2))
    # Attack: a slash line extending from the weapon hand.
    if attacking:
        slash = (240, 240, 240)
        if direction == HERO_DIR_DOWN:
            pygame.draw.line(surf, slash, (x + 8, y), (x + 8, y + 12), 2)
        elif direction == HERO_DIR_UP:
            pygame.draw.line(surf, slash, (x + 8, y - 12), (x + 8, y - 24), 2)
        elif direction == HERO_DIR_LEFT:
            pygame.draw.line(surf, slash, (x - 6, y - 2), (x - 16, y - 6), 2)
        else:
            pygame.draw.line(surf, slash, (x + 6, y - 2), (x + 16, y - 6), 2)


def _draw_hair(surf, x, hy, direction, look, tunic, skin):
    """Hair or headgear over a head of radius 6 centred on (x, hy)."""
    style = look_choice(look, "hair")[1]
    color = look_choice(look, "hair_color")[1]
    back = direction == HERO_DIR_UP
    lean = {HERO_DIR_LEFT: 1, HERO_DIR_RIGHT: -1}.get(direction, 0)
    if style == "bald":
        pygame.draw.circle(surf, _shade(skin, 30), (x - 2, hy - 3), 1)
        return
    if style == "helmet":
        steel = (156, 160, 170)
        pygame.draw.ellipse(surf, steel, (x - 7, hy - 8, 14, 10 if not back else 14))
        pygame.draw.line(surf, _shade(steel, -50), (x - 7, hy), (x + 6, hy), 1)
        if direction == HERO_DIR_DOWN:
            pygame.draw.line(surf, _shade(steel, -40), (x, hy), (x, hy + 3), 1)
        return
    if style == "hood":
        cloth = _shade(tunic, -35)
        pygame.draw.circle(surf, cloth, (x, hy), 7)
        if not back:
            # The face shows through the hood's opening.
            fx = x - 2 * lean
            pygame.draw.circle(surf, skin, (fx, hy + 1), 4)
            if direction == HERO_DIR_DOWN:
                for ex in (x - 2, x + 2):
                    pygame.draw.rect(surf, (25, 20, 20), (ex, hy + 1, 1, 2))
        return
    # Hair: a cap over the top (the whole head from behind).
    if back:
        pygame.draw.circle(surf, color, (x, hy), 6)
    else:
        pygame.draw.ellipse(surf, color, (x - 6 + lean, hy - 7, 12, 6))
        if lean:   # side view: hair covers the back of the head
            bx = x + 2 * lean
            pygame.draw.ellipse(surf, color, (bx - 3, hy - 6, 6, 9))
    if style == "long":
        if back:
            pygame.draw.rect(surf, color, (x - 6, hy, 12, 7), border_radius=2)
        elif lean:
            pygame.draw.rect(surf, color, (x + 3 * lean - 2, hy - 2, 4, 9))
        else:
            for sx in (x - 7, x + 5):
                pygame.draw.rect(surf, color, (sx, hy - 3, 2, 9))
    elif style == "spiky":
        for dx in (-5, -2, 1, 4):
            pygame.draw.polygon(surf, color, [(x + dx - 1, hy - 4),
                                              (x + dx + 1, hy - 10),
                                              (x + dx + 3, hy - 4)])


# Placeholder body colours per enemy name: (body, outline).
ENEMY_COLORS = {
    "slime": ((90, 190, 90), (60, 140, 60)),
    "goblin": ((150, 170, 90), (110, 130, 60)),
    "bat": ((140, 100, 180), (100, 70, 140)),
    "rat": ((120, 96, 80), (80, 62, 52)),
    "skeleton": ((220, 220, 210), (170, 170, 160)),
    "rat_king": ((110, 100, 96), (70, 62, 60)),
    "boss": ((110, 100, 96), (70, 62, 60)),
}
_DEFAULT_ENEMY = ((160, 160, 160), (120, 120, 120))

# Placeholder tint per item key.
ITEM_COLORS = {
    "potion": (220, 60, 70),
    "health_potion": (220, 60, 70),
    "bloodcrystal": (200, 30, 60),
    "key": (220, 200, 90),
    "saber": (180, 190, 210),
    "spear": (160, 150, 130),
    "dagger": (170, 180, 200),
}


def _gen_enemy_sheet(name: str) -> pygame.Surface:
    body, dark = ENEMY_COLORS.get(name, _DEFAULT_ENEMY)
    surf = _new_sheet(ENEMY_COLS, ENEMY_ROWS)
    for col in range(ENEMY_COLS):
        # Draw each frame on its own surface so wings / horns that reach
        # past the edge (hurt shake) are clipped instead of bleeding
        # into the neighbouring frame.
        frame = pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA)
        _draw_enemy_frame(frame, 0, 0, body, dark, col, name)
        surf.blit(frame, (col * FRAME_SIZE, 0))
    return surf


def _draw_enemy_frame(surf: pygame.Surface, px: int, py: int,
                      body, dark, col: int, name: str = "slime"):
    """Draw one 32x32 enemy frame at (px, py) for animation column ``col``.

    Every enemy shares the animation rules (idle bob, attack lunge with
    red eyes, hurt shake + red flash, death puddle); ``name`` picks the
    silhouette so each type reads differently at a glance."""
    x, y = px + 16, py + 18
    phase = col % 2
    if col in ENEMY_DEATH:
        pygame.draw.ellipse(surf, dark, (px + 4, py + 22, 24, 7))
        if name == "skeleton":                 # a few bones left
            pygame.draw.line(surf, body, (px + 9, py + 24), (px + 15, py + 22), 2)
            pygame.draw.line(surf, body, (px + 18, py + 25), (px + 24, py + 23), 2)
        return
    if col in ENEMY_HURT:
        x += 3 if phase else -3  # shake
        body = (255, 120, 120)   # red flash
    if col in ENEMY_IDLE:
        y += 1 if phase else 0   # breathing
    attack = col in ENEMY_ATTACK
    eye = (255, 60, 40) if attack else (20, 20, 20)

    if name in ("rat", "rat_king", "boss"):
        # A rat in profile: long body, head with a round ear, pink tail.
        # The boss is the Rat King: bigger, with a gold crown.
        big = name != "rat"
        k = 1.35 if big else 1.0
        lunge = 3 if attack else 0
        bx, by = x - (7 if big else 2) + lunge, y + 2
        bw, bh = int(20 * k), int(12 * k)
        tail = (220, 140, 150)
        pygame.draw.lines(surf, tail, False,
                          [(bx - bw // 2, by + 2), (bx - bw // 2 - 5, by + 5),
                           (bx - bw // 2 - 8, by + (1 if phase else 4))], 2)
        pygame.draw.ellipse(surf, body, (bx - bw // 2, by - bh // 2, bw, bh))
        pygame.draw.ellipse(surf, dark, (bx - bw // 2, by - bh // 2, bw, bh), 1)
        hx, hy = bx + bw // 2 - 1, by - int(3 * k)
        pygame.draw.polygon(surf, body, [(hx - 4, hy - 4), (hx + int(8 * k), hy + 1), (hx - 3, hy + 5)])
        pygame.draw.circle(surf, tail, (hx + int(8 * k), hy + 1), 2)            # nose
        pygame.draw.circle(surf, body, (hx - 2, hy - 5), int(3 * k))          # ear
        pygame.draw.circle(surf, tail, (hx - 2, hy - 5), max(1, int(2 * k) - 1))
        pygame.draw.circle(surf, eye, (hx + 2, hy - 1), 1 if not big else 2)
        for fx in (-bw // 3, bw // 4):
            pygame.draw.line(surf, dark, (bx + fx, by + bh // 2 - 1), (bx + fx, by + bh // 2 + 2), 2)
        if big:
            cx0, cy0 = hx - 6, hy - 10
            pygame.draw.polygon(surf, (230, 190, 90), [
                (cx0, cy0 + 6), (cx0, cy0), (cx0 + 3, cy0 + 3), (cx0 + 6, cy0 - 1),
                (cx0 + 9, cy0 + 3), (cx0 + 12, cy0), (cx0 + 12, cy0 + 6)])
            pygame.draw.circle(surf, (200, 40, 50), (cx0 + 6, cy0 + 4), 1)
    elif name == "bat":
        # Small round body, two wings that flap with the frame.
        up = -5 if phase else 2
        for side in (-1, 1):
            tip = (x + side * 15, y + up - 4)
            wing = [(x + side * 4, y - 3), tip, (x + side * 11, y + 4),
                    (x + side * 6, y + 2)]
            pygame.draw.polygon(surf, body, wing)
            pygame.draw.polygon(surf, dark, wing, 1)
        pygame.draw.ellipse(surf, body, (x - 6, y - 7, 12, 13))
        pygame.draw.ellipse(surf, dark, (x - 6, y - 7, 12, 13), 1)
        pygame.draw.polygon(surf, dark, [(x - 5, y - 6), (x - 3, y - 11), (x - 1, y - 6)])
        pygame.draw.polygon(surf, dark, [(x + 1, y - 6), (x + 3, y - 11), (x + 5, y - 6)])
        pygame.draw.circle(surf, eye, (x - 2, y - 2), 1)
        pygame.draw.circle(surf, eye, (x + 2, y - 2), 1)
    elif name == "goblin":
        # Body + big head with pointy ears, a club when attacking.
        pygame.draw.rect(surf, dark, (x - 6, y + 2, 12, 10), border_radius=3)
        pygame.draw.ellipse(surf, body, (x - 7, y - 10, 14, 13))
        pygame.draw.ellipse(surf, dark, (x - 7, y - 10, 14, 13), 1)
        pygame.draw.polygon(surf, body, [(x - 6, y - 5), (x - 13, y - 9), (x - 7, y - 1)])
        pygame.draw.polygon(surf, body, [(x + 6, y - 5), (x + 13, y - 9), (x + 7, y - 1)])
        pygame.draw.circle(surf, eye, (x - 3, y - 4), 1)
        pygame.draw.circle(surf, eye, (x + 3, y - 4), 1)
        club = (x + 9, y - 6) if attack else (x + 10, y + 6)
        pygame.draw.line(surf, (110, 80, 50), (x + 6, y + 6), club, 3)
    elif name == "skeleton":
        # Skull, rib cage, thin limbs.
        pygame.draw.circle(surf, body, (x, y - 6), 6)
        pygame.draw.circle(surf, dark, (x, y - 6), 6, 1)
        pygame.draw.circle(surf, eye if attack else (30, 30, 30), (x - 2, y - 7), 2)
        pygame.draw.circle(surf, eye if attack else (30, 30, 30), (x + 2, y - 7), 2)
        pygame.draw.line(surf, body, (x, y), (x, y + 10), 2)
        for dy in (2, 5, 8):
            pygame.draw.line(surf, body, (x - 5, y + dy), (x + 5, y + dy), 1)
        reach = 9 if attack else 6
        pygame.draw.line(surf, body, (x - 2, y + 2), (x - reach, y + 7), 2)
        pygame.draw.line(surf, body, (x + 2, y + 2), (x + reach, y + 7), 2)
        pygame.draw.line(surf, body, (x - 1, y + 10), (x - 4, y + 13), 2)
        pygame.draw.line(surf, body, (x + 1, y + 10), (x + 4, y + 13), 2)
    else:
        # Slime (and any unknown name): a jelly blob.
        h = 18 if attack else 16
        pygame.draw.ellipse(surf, body, (x - 10, y - 8, 20, h))
        pygame.draw.ellipse(surf, dark, (x - 10, y - 8, 20, h), 2)
        pygame.draw.circle(surf, eye, (x - 4, y - 2), 2)
        pygame.draw.circle(surf, eye, (x + 4, y - 2), 2)


def _gen_item_icon(key: str) -> pygame.Surface:
    color = ITEM_COLORS.get(key, (180, 140, 90))
    surf = pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA)
    pygame.draw.rect(surf, (30, 30, 35, 255), (1, 1, 30, 30), border_radius=6)
    pygame.draw.rect(surf, (*color, 255), (5, 5, 22, 22), border_radius=4)
    pygame.draw.line(surf, (255, 255, 255, 120), (8, 9), (13, 9), 2)  # sheen
    return surf


def _gen_chest() -> pygame.Surface:
    """Two 32x32 frames: closed chest, open chest."""
    surf = _new_sheet(2, 1)
    wood, dark, gold = (150, 95, 45), (95, 60, 30), (230, 190, 90)
    for col in range(2):
        px = col * FRAME_SIZE
        pygame.draw.rect(surf, wood, (px + 5, 14, 22, 13), border_radius=2)
        pygame.draw.rect(surf, dark, (px + 5, 14, 22, 13), 2, border_radius=2)
        if col == 0:   # closed lid + lock
            pygame.draw.rect(surf, wood, (px + 5, 8, 22, 8), border_radius=3)
            pygame.draw.rect(surf, dark, (px + 5, 8, 22, 8), 2, border_radius=3)
            pygame.draw.rect(surf, gold, (px + 14, 13, 4, 5))
        else:          # lid flipped back, dark inside
            pygame.draw.rect(surf, dark, (px + 7, 15, 18, 5))
            pygame.draw.rect(surf, wood, (px + 5, 4, 22, 6), border_radius=3)
            pygame.draw.rect(surf, dark, (px + 5, 4, 22, 6), 2, border_radius=3)
    return surf


def _gen_ui(name: str) -> pygame.Surface:
    """64x64 placeholder panel; real art may be any size."""
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.rect(surf, (40, 40, 50, 230), (2, 2, 60, 60), border_radius=8)
    pygame.draw.rect(surf, (120, 120, 140, 255), (2, 2, 60, 60), 2, border_radius=8)
    return surf
