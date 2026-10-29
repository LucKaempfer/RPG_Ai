# pygame_rpg/dungeon.py
"""Procedural dungeon generation for the Pygame RPG.

This module creates a set of rectangular rooms connected by corridors.
Each room has a unique ID, a Pygame Rect that defines its position in world space,
and a list of doors.  Doors are simply world coordinates that lie on a
room's wall.  Each door is linked to a door in another room, forming a graph.

The dungeon is rendered tile‑by‑tile with a single tile size
(`TILE_SIZE`).  The minimap shows visited rooms and walked corridors.
Room and corridor cells are walkable; everything else is wall.
"""

import random
import pygame
from typing import List, Tuple, Dict, Optional

from .assets import (
    assets,
    TILE_FLOOR, TILE_WALL, TILE_WALL_DARK, TILE_CORRIDOR, TILE_DOOR,
    TILESET_COLS, TILESET_ROWS,
)

# Configuration constants
TILE_SIZE = 32
DUNGEON_WIDTH = 80   # in tiles
DUNGEON_HEIGHT = 60  # in tiles
MAX_ROOM_SIZE = 10   # max width/height in tiles
MIN_ROOM_SIZE = 4
NUM_ROOMS = 15

class Room:
    """Represents a rectangular room in world coordinates."""

    def __init__(self, id: int, rect: pygame.Rect):
        self.id = id
        self.rect = rect
        self.doors: List[Tuple[int, int]] = []  # world coordinates of door tiles
        self.connections: Dict[Tuple[int, int], "Room"] = {}

    def add_door(self, pos: Tuple[int, int]):
        self.doors.append(pos)

    def connect(self, pos: Tuple[int, int], other: "Room"):
        self.connections[pos] = other

    def contains(self, world_pos: Tuple[int, int]) -> bool:
        return self.rect.collidepoint(world_pos)

class Dungeon:
    """Handles generation and storage of rooms and corridors."""

    def __init__(self):
        self.rooms: List[Room] = []
        self.room_map: Dict[Tuple[int, int], Room] = {}  # world cell -> room
        self.door_tiles: set = set()  # world cells holding a door
        self.visited_corridors: set = set()  # corridor cells seen (minimap)
        self.minimap_surface: Optional[pygame.Surface] = None
        self._tile_frames: Optional[List[pygame.Surface]] = None

    def generate(self, seed: Optional[int] = None):
        # A private RNG: the seed fully determines the floor and the
        # global random state is left alone (M5 saves store the seed).
        rng = self.rng = random.Random(seed)
        self.rooms.clear()
        self.room_map.clear()
        self.visited_corridors.clear()
        attempts = 0
        while len(self.rooms) < NUM_ROOMS and attempts < NUM_ROOMS * 10:
            attempts += 1
            w = rng.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE)
            h = rng.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE)
            x = rng.randint(1, DUNGEON_WIDTH - w - 1)
            y = rng.randint(1, DUNGEON_HEIGHT - h - 1)
            new_rect = pygame.Rect(x, y, w, h)
            if any(new_rect.colliderect(r.rect) for r in self.rooms):
                continue  # overlap, try again
            room = Room(len(self.rooms), new_rect)
            self.rooms.append(room)
            # Map each tile to this room for quick lookup
            for rx in range(new_rect.left, new_rect.right):
                for ry in range(new_rect.top, new_rect.bottom):
                    self.room_map[(rx, ry)] = room

        self._connect_rooms()
        self._add_doors()

    def _add_doors(self):
        """A door is a room cell next to a corridor cell: the spot where a
        corridor leaves the room."""
        self.door_tiles = set()
        for (x, y), room in self.room_map.items():
            if room is None:
                continue
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in self.room_map and self.room_map[n] is None:
                    room.add_door((x, y))
                    self.door_tiles.add((x, y))
                    break

    def _connect_rooms(self):
        """Connect each room to the nearest *earlier* room by a corridor.

        Linking only to earlier rooms builds a tree, so every room is
        reachable from room 0 (linking to the nearest room overall could
        leave separate clusters).
        """
        for i, room in enumerate(self.rooms):
            if i == 0:
                continue
            nearest = min(
                self.rooms[:i],
                key=lambda r: self._distance(room.rect.center, r.rect.center),
            )
            # Create corridor between centers
            self._create_corridor(room.rect.center, nearest.rect.center)

    @staticmethod
    def _distance(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    def _create_corridor(self, start: Tuple[int, int], end: Tuple[int, int]):
        """Carve a straight horizontal‑then‑vertical corridor between two points."""
        x1, y1 = start
        x2, y2 = end
        # Corridor cells map to None; cells already inside a room keep
        # their room.
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.room_map.setdefault((x, y1), None)
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.room_map.setdefault((x2, y), None)

    def get_room_at(self, world_pos: Tuple[int, int]) -> Optional[Room]:
        return self.room_map.get(world_pos)

    def is_walkable(self, cell: Tuple[int, int]) -> bool:
        """Room and corridor cells are floor; everything else is wall."""
        return cell in self.room_map

    def spawn_point(self) -> Tuple[int, int]:
        """World pixel centre of the first room (where the hero enters)."""
        cx, cy = self.rooms[0].rect.center
        return (cx * TILE_SIZE + TILE_SIZE // 2, cy * TILE_SIZE + TILE_SIZE // 2)

    def draw_minimap(self, surface: pygame.Surface, visited, pos,
                     player_cell: Tuple[int, int], scale: int = 2):
        """Draw the explored map at ``pos``: visited rooms, corridor
        cells the hero has walked, and the hero as a dot.  ``scale`` = pixels per
        tile."""
        size = (DUNGEON_WIDTH * scale, DUNGEON_HEIGHT * scale)
        if self.minimap_surface is None or self.minimap_surface.get_size() != size:
            self.minimap_surface = pygame.Surface(size, pygame.SRCALPHA)
        mm = self.minimap_surface
        mm.fill((0, 0, 0, 150))
        for room in visited:
            r = room.rect
            pygame.draw.rect(mm, (190, 190, 200),
                             (r.x * scale, r.y * scale, r.w * scale, r.h * scale))
        for cell in self.visited_corridors:
            pygame.draw.rect(mm, (120, 120, 135),
                             (cell[0] * scale, cell[1] * scale, scale, scale))
        px, py = player_cell
        pygame.draw.rect(mm, (230, 190, 90),
                         (px * scale - 1, py * scale - 1, scale + 2, scale + 2))
        surface.blit(mm, pos)
        pygame.draw.rect(surface, (92, 92, 118), (*pos, *size), width=1)

    def _tiles(self) -> List[pygame.Surface]:
        """Tileset frames (cached); index matches the TILE_* constants."""
        if self._tile_frames is None:
            self._tile_frames = assets.load_sheet(
                "tileset.png", TILESET_COLS, TILESET_ROWS
            )
        return self._tile_frames

    def render(self, surface: pygame.Surface, camera_offset: Tuple[int, int]):
        """Render the visible part of the dungeon to the main surface."""
        offset_x, offset_y = camera_offset
        tiles = self._tiles()
        surf_w, surf_h = surface.get_size()
        x0 = offset_x // TILE_SIZE
        y0 = offset_y // TILE_SIZE
        x1 = min(DUNGEON_WIDTH, x0 + (surf_w + TILE_SIZE - 1) // TILE_SIZE)
        y1 = min(DUNGEON_HEIGHT, y0 + (surf_h + TILE_SIZE - 1) // TILE_SIZE)
        for x in range(x0, x1):
            for y in range(y0, y1):
                cell = (x, y)
                if self.room_map.get(cell) is not None:
                    tile = TILE_DOOR if cell in self.door_tiles else TILE_FLOOR
                elif cell in self.room_map:
                    tile = TILE_CORRIDOR
                else:
                    # Unlit stone walls, with a deterministic dark variant.
                    tile = TILE_WALL if (x * 31 + y * 17) % 9 else TILE_WALL_DARK
                surface.blit(
                    tiles[tile], (x * TILE_SIZE - offset_x, y * TILE_SIZE - offset_y)
                )
