# pygame_rpg/dungeon.py
"""Procedural dungeon generation for the Pygame RPG.

This module creates a set of rectangular rooms connected by corridors.
Each room has a unique ID, a Pygame Rect that defines its position in world space,
and a list of doors.  Doors are simply world coordinates that lie on a
room's wall.  Each door is linked to a door in another room, forming a graph.

The dungeon is rendered tile‑by‑tile.  For the purposes of this demo
we use a single tile size (`TILE_SIZE`).  The minimap is drawn in the top
left corner as a small grid where each visited room is a coloured block.
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
        self.minimap_surface: Optional[pygame.Surface] = None
        self._tile_frames: Optional[List[pygame.Surface]] = None

    def generate(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
        self.rooms.clear()
        self.room_map.clear()
        attempts = 0
        while len(self.rooms) < NUM_ROOMS and attempts < NUM_ROOMS * 10:
            attempts += 1
            w = random.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE)
            h = random.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE)
            x = random.randint(1, DUNGEON_WIDTH - w - 1)
            y = random.randint(1, DUNGEON_HEIGHT - h - 1)
            new_rect = pygame.Rect(x, y, w, h)
            if any(new_rect.colliderect(r.rect) for r in self.rooms):
                continue  # overlap, try again
            room = Room(len(self.rooms), new_rect)
            self.rooms.append(room)
            # Map each tile to this room for quick lookup
            for rx in range(new_rect.left, new_rect.right):
                for ry in range(new_rect.top, new_rect.bottom):
                    self.room_map[(rx, ry)] = room

        # Add doors and corridors
        for room in self.rooms:
            self._add_doors(room)
        self.door_tiles = {pos for room in self.rooms for pos in room.doors}
        self._connect_rooms()

    def _add_doors(self, room: Room):
        """Place a random door on each side of the room."""
        sides = ['top', 'bottom', 'left', 'right']
        for side in sides:
            if random.random() < 0.5:  # 50% chance to add a door on this side
                if side in ('top', 'bottom'):
                    dx = random.randint(room.rect.left + 1, room.rect.right - 2)
                    dy = room.rect.top if side == 'top' else room.rect.bottom - 1
                else:
                    dx = room.rect.left if side == 'left' else room.rect.right - 1
                    dy = random.randint(room.rect.top + 1, room.rect.bottom - 2)
                pos = (dx, dy)
                room.add_door(pos)

    def _connect_rooms(self):
        """Connect each room to the nearest room by a straight corridor."""
        for i, room in enumerate(self.rooms):
            if i == 0:
                continue  # skip first room; it will get connected by others
            # Find nearest room
            nearest = min(
                (r for r in self.rooms if r != room),
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
        # Horizontal part
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.room_map[(x, y1)] = None  # corridor cell
        # Vertical part
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.room_map[(x2, y)] = None

    def get_room_at(self, world_pos: Tuple[int, int]) -> Optional[Room]:
        return self.room_map.get(world_pos)

    def draw_minimap(self, surface: pygame.Surface, visited: List[Room]):
        """Draw a tiny minimap in the top‑left corner."""
        scale = 0.1  # each dungeon tile -> 0.1 pixels
        minimap_size = (int(DUNGEON_WIDTH * scale), int(DUNGEON_HEIGHT * scale))
        if self.minimap_surface is None or self.minimap_surface.get_size() != minimap_size:
            self.minimap_surface = pygame.Surface(minimap_size, pygame.SRCALPHA)
        self.minimap_surface.fill((0, 0, 0, 0))  # clear
        # Draw visited rooms as white blocks
        for room in visited:
            w, h = room.rect.size
            rect = pygame.Rect(
                int(room.rect.left * scale),
                int(room.rect.top * scale),
                max(1, int(w * scale)),
                max(1, int(h * scale)),
            )
            pygame.draw.rect(self.minimap_surface, (200, 200, 200), rect)
        surface.blit(self.minimap_surface, (5, 5))

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
