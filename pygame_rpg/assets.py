# pygame_rpg/assets.py
"""Asset manager for the Pygame RPG.

Loads sprites from the ``assets/`` directory inside this package
(``pygame_rpg/assets/``), with
caching.  When an image file is missing, a programmatically generated
placeholder is created *and saved* so that development never crashes on
missing art and the file layout is stable: drop real art with the same
filenames and it is picked up automatically.

Layouts (all frames are 32x32 pixels):

* ``tileset.png``          10 x 1 grid, one tile per index (see TILE_*)
* ``player/hero_sheet.png`` 8 x 4 grid
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
ENEMY_NAMES = ("slime", "goblin", "bat", "skeleton", "boss")


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
            surf = self.load_image(name)
            w, h = surf.get_size()
            fw, fh = w // cols, h // rows
            frames = [
                surf.subsurface(pygame.Rect(c * fw, r * fh, fw, fh)).copy()
                for r in range(rows)
                for c in range(cols)
            ]
            self._cache[key] = frames
        return self._cache[key]

    # -- placeholder generation ---------------------------------------
    def _generate(self, name: str) -> pygame.Surface:
        """Dispatch to the right generator for a missing file."""
        if name == "tileset.png":
            return _gen_tileset()
        if name == "player/hero_sheet.png":
            return _gen_hero_sheet()
        if name.startswith("enemies/"):
            return _gen_enemy_sheet(name.rsplit("/", 1)[-1].removesuffix(".png"))
        if name.startswith("items/"):
            return _gen_item_icon(name.rsplit("/", 1)[-1].removesuffix(".png"))
        if name == "objects/chest.png":
            return _gen_chest()
        if name.startswith("ui/"):
            return _gen_ui(name.rsplit("/", 1)[-1].removesuffix(".png"))
        raise FileNotFoundError(f"no generator for asset: {name}")


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


def _gen_hero_sheet() -> pygame.Surface:
    """Draw a simple knight figure for every (direction, phase) cell."""
    surf = _new_sheet(HERO_COLS, HERO_ROWS)
    for row in range(HERO_ROWS):
        for col in range(HERO_COLS):
            px, py = col * FRAME_SIZE, row * FRAME_SIZE
            _draw_hero_frame(surf, px, py, row, col)
    return surf


def _draw_hero_frame(surf: pygame.Surface, px: int, py: int,
                     direction: int, col: int):
    """Draw one 32x32 hero frame at (px, py) facing ``direction``."""
    x, y = px + 16, py + 16  # centre of the frame
    attacking = col in HERO_ATTACK_COLS
    # Bob the body slightly on alternate frames for a life-like idle/walk.
    bob = 1 if (col % 2 == 1) else 0
    body_c = (70, 130, 210) if not attacking else (220, 180, 60)
    pygame.draw.ellipse(surf, body_c, (x - 8, y - 4 - bob, 16, 18))  # torso
    pygame.draw.circle(surf, (235, 200, 160), (x, y - 10 - bob), 7)  # head
    # Helmet: arc over the head, tinted by facing direction.
    helm = (40, 90, 160)
    if direction == HERO_DIR_UP:
        pygame.draw.ellipse(surf, helm, (x - 8, y - 17 - bob, 16, 12))
    else:
        pygame.draw.arc(surf, helm, (x - 8, y - 18 - bob, 16, 14), 0, math.pi, 3)
    # Facing marker: a small notch on the side the hero faces.
    if direction == HERO_DIR_DOWN:
        pygame.draw.circle(surf, (20, 20, 20), (x - 3, y - 10 - bob), 1)
        pygame.draw.circle(surf, (20, 20, 20), (x + 3, y - 10 - bob), 1)
    elif direction == HERO_DIR_LEFT:
        pygame.draw.rect(surf, (20, 20, 20), (x - 8, y - 11 - bob, 4, 2))
    elif direction == HERO_DIR_RIGHT:
        pygame.draw.rect(surf, (20, 20, 20), (x + 4, y - 11 - bob, 4, 2))
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


# Placeholder body colours per enemy name: (body, outline).
ENEMY_COLORS = {
    "slime": ((90, 190, 90), (60, 140, 60)),
    "goblin": ((150, 170, 90), (110, 130, 60)),
    "bat": ((140, 100, 180), (100, 70, 140)),
    "skeleton": ((220, 220, 210), (170, 170, 160)),
    "boss": ((200, 70, 60), (150, 40, 35)),
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
        _draw_enemy_frame(surf, col * FRAME_SIZE, 0, body, dark, col)
    return surf


def _draw_enemy_frame(surf: pygame.Surface, px: int, py: int,
                      body, dark, col: int):
    """Draw one 32x32 enemy frame at (px, py) for animation column ``col``."""
    x, y = px + 16, py + 18
    phase = col % 2
    if col in ENEMY_DEATH:
        pygame.draw.ellipse(surf, dark, (px + 4, py + 22, 24, 7))
        return
    if col in ENEMY_HURT:
        x += 3 if phase else -3  # shake
        body = (255, 120, 120)   # red flash
    if col in ENEMY_IDLE:
        y += 1 if phase else 0   # breathing
    h = 18 if col in ENEMY_ATTACK else 16
    pygame.draw.ellipse(surf, body, (x - 10, y - 8, 20, h))
    pygame.draw.ellipse(surf, dark, (x - 10, y - 8, 20, h), 2)
    eye = (255, 60, 40) if col in ENEMY_ATTACK else (20, 20, 20)
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
