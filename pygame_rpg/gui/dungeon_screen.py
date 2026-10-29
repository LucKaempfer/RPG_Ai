# pygame_rpg/gui/dungeon_screen.py
"""Dungeon screen (M4 step 1): the hero walks a generated floor.

Revives the M1 crawler as a proper screen: ``dungeon.py`` builds and
draws the floor, this screen owns the hero's position, movement with
wall collision, the walk animation, the camera and a minimal overlay
(floor, HP/MP, minimap).  Enemies, battles, loot and the full HUD
follow in later M4 steps.

Arrows / WASD move.  Esc saves and returns to the Base; window close
saves, then quits.
"""

import pygame

from ..assets import (
    AssetManager, HERO_COLS, HERO_ROWS, HERO_IDLE_COLS, HERO_WALK_COLS,
    HERO_DIR_DOWN, HERO_DIR_UP, HERO_DIR_LEFT, HERO_DIR_RIGHT,
)
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..dungeon import Dungeon, TILE_SIZE, DUNGEON_WIDTH, DUNGEON_HEIGHT
from ..savegame import save_player
from .screen import QUIT, Screen, font, TEXT_COLOR, DIM_TEXT, GOLD

# Hero movement in pixels per second (trinket speed_bonus adds %).
WALK_SPEED = 160
# Collision box: smaller than a tile so the hero fits through
# one-tile corridors without snagging on corners.
HITBOX = 20
# Seconds per walk/idle animation frame.
FRAME_TIME = 0.12

MINIMAP_SCALE = 2


class DungeonScreen(Screen):
    name = "dungeon"

    def __init__(self, screen, player, floor=1, seed=None):
        super().__init__(screen)
        self.player = player
        self.floor = floor
        self.dungeon = Dungeon()
        self.dungeon.generate(seed)
        self.x, self.y = map(float, self.dungeon.spawn_point())
        self.facing = HERO_DIR_DOWN
        self.moving = False
        self.anim_t = 0.0
        self.visited = []
        self._mark_visited()
        self.frames = AssetManager().load_sheet(
            "player/hero_sheet.png", HERO_COLS, HERO_ROWS)

    # -- movement ------------------------------------------------------
    @property
    def speed(self) -> float:
        return WALK_SPEED * (1 + self.player.bonus("speed_bonus") / 100)

    def cell(self):
        """Tile the hero's centre stands on."""
        return (int(self.x // TILE_SIZE), int(self.y // TILE_SIZE))

    def _fits(self, x, y) -> bool:
        """Whether the hitbox centred on (x, y) touches only floor."""
        half = HITBOX / 2
        for cx in (x - half, x + half - 1):
            for cy in (y - half, y + half - 1):
                if not self.dungeon.is_walkable(
                        (int(cx // TILE_SIZE), int(cy // TILE_SIZE))):
                    return False
        return True

    def move(self, dx, dy, dt) -> None:
        """Move by direction (dx, dy) in -1..1 for ``dt`` seconds.

        Axes are resolved separately, so the hero slides along walls
        instead of sticking to them.
        """
        self.moving = bool(dx or dy)
        if not self.moving:
            return
        if dx and dy:  # same speed diagonally
            dx, dy = dx * 0.7071, dy * 0.7071
        step = self.speed * dt
        nx = self.x + dx * step
        if self._fits(nx, self.y):
            self.x = nx
        ny = self.y + dy * step
        if self._fits(self.x, ny):
            self.y = ny
        if abs(dx) >= abs(dy):
            self.facing = HERO_DIR_RIGHT if dx > 0 else HERO_DIR_LEFT
        else:
            self.facing = HERO_DIR_DOWN if dy > 0 else HERO_DIR_UP
        self._mark_visited()

    def _mark_visited(self):
        cell = self.cell()
        room = self.dungeon.get_room_at(cell)
        if room is not None:
            if room not in self.visited:
                self.visited.append(room)
        else:
            self.dungeon.visited_corridors.add(cell)

    def camera(self):
        """Top-left world pixel of the view, centred on the hero and
        clamped to the map."""
        max_x = DUNGEON_WIDTH * TILE_SIZE - SCREEN_WIDTH
        max_y = DUNGEON_HEIGHT * TILE_SIZE - SCREEN_HEIGHT
        cx = int(self.x) - SCREEN_WIDTH // 2
        cy = int(self.y) - SCREEN_HEIGHT // 2
        return (max(0, min(max_x, cx)), max(0, min(max_y, cy)))

    # -- Screen hooks ----------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            save_player(self.player)
            return QUIT
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            save_player(self.player)
            return ("base", {"player": self.player})
        return None

    def handle_update(self, dt):
        keys = pygame.key.get_pressed()
        dx = ((keys[pygame.K_RIGHT] or keys[pygame.K_d])
              - (keys[pygame.K_LEFT] or keys[pygame.K_a]))
        dy = ((keys[pygame.K_DOWN] or keys[pygame.K_s])
              - (keys[pygame.K_UP] or keys[pygame.K_w]))
        self.move(dx, dy, dt)
        self.anim_t += dt

    def draw(self, surface):
        surface.fill((0, 0, 0))
        ox, oy = self.camera()
        self.dungeon.render(surface, (ox, oy))

        cols = HERO_WALK_COLS if self.moving else HERO_IDLE_COLS
        col = cols[int(self.anim_t / FRAME_TIME) % len(cols)]
        frame = self.frames[self.facing * HERO_COLS + col]
        surface.blit(frame, frame.get_rect(
            center=(int(self.x) - ox, int(self.y) - oy)))

        # Overlay: floor + HP/MP (top-left), minimap (top-right).
        p = self.player
        lines = [
            (f"Floor {self.floor}", GOLD),
            (f"HP {p.current_hp} / {p.max_hp}", TEXT_COLOR),
            (f"MP {p.current_mp} / {p.max_mp}", TEXT_COLOR),
        ]
        y = 10
        for text, color in lines:
            img = font(22).render(text, True, color)
            surface.blit(img, (12, y))
            y += 24
        mm_w = DUNGEON_WIDTH * MINIMAP_SCALE
        self.dungeon.draw_minimap(
            surface, self.visited, (SCREEN_WIDTH - mm_w - 10, 10),
            self.cell(), scale=MINIMAP_SCALE)
        hint = font(18).render(
            "Arrows / WASD: move    Esc: back to base", True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 12, SCREEN_HEIGHT - 10)))
