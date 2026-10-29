# pygame_rpg/dungeon.py
"""Procedural dungeon generation for the Pygame RPG.

This module creates a set of rectangular rooms connected by corridors.
Each room has a unique ID, a Pygame Rect that defines its position in world space,
and a list of doors.  Rooms keep ROOM_GAP free tiles between them; each
corridor leaves one room through a door on the wall facing its target,
is routed around every other room (never along a room's wall), and
enters the target through a door.  Corridors link each room to the
nearest earlier one, so the rooms form a tree and all are reachable.

The dungeon is rendered tile‑by‑tile with a single tile size
(`TILE_SIZE`).  The minimap shows visited rooms and walked corridors.
Room and corridor cells are walkable; everything else is wall.
"""

import heapq
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
# Free tiles kept between rooms: room walls stay solid and a corridor
# (with wall on both sides) fits through every gap.
ROOM_GAP = 3
# Extra cost of a corridor bend, so routes stay mostly straight.
TURN_COST = 3

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
            x = rng.randint(2, DUNGEON_WIDTH - w - 2)
            y = rng.randint(2, DUNGEON_HEIGHT - h - 2)
            new_rect = pygame.Rect(x, y, w, h)
            spaced = new_rect.inflate(2 * ROOM_GAP, 2 * ROOM_GAP)
            if any(spaced.colliderect(r.rect) for r in self.rooms):
                continue  # overlap or too close, try again
            room = Room(len(self.rooms), new_rect)
            self.rooms.append(room)
            # Map each tile to this room for quick lookup
            for rx in range(new_rect.left, new_rect.right):
                for ry in range(new_rect.top, new_rect.bottom):
                    self.room_map[(rx, ry)] = room

        self.door_tiles = set()
        # Rooms plus a one-tile ring around them: corridors never enter
        # it (except at their own door), so they can't run along a room
        # and open its wall.
        self._reserved = set()
        for room in self.rooms:
            r = room.rect.inflate(2, 2)
            self._reserved.update((x, y) for x in range(r.left, r.right)
                                  for y in range(r.top, r.bottom))
        self._connect_rooms()

    def _door_options(self, room, target):
        """(door cell, outside cell) pairs on ``room``'s walls, the side
        facing ``target`` first.  Doors sit in line with the target's
        centre where possible and never on a corner."""
        r = room.rect
        tx, ty = target.rect.center
        dx, dy = tx - r.centerx, ty - r.centery
        y = min(max(ty, r.top + 1), r.bottom - 2)
        x = min(max(tx, r.left + 1), r.right - 2)
        sides = {
            "E": ((r.right - 1, y), (r.right, y)),
            "W": ((r.left, y), (r.left - 1, y)),
            "S": ((x, r.bottom - 1), (x, r.bottom)),
            "N": ((x, r.top), (x, r.top - 1)),
        }
        # One door per wall: a wall that has a door already reuses it.
        for door in room.doors:
            k = ("E" if door[0] == r.right - 1 else "W" if door[0] == r.left
                 else "S" if door[1] == r.bottom - 1 else "N")
            out = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}[k]
            sides[k] = (door, (door[0] + out[0], door[1] + out[1]))
        horiz = ("E" if dx > 0 else "W", "S" if dy > 0 else "N")
        order = horiz if abs(dx) >= abs(dy) else horiz[::-1]
        rest = [k for k in "ESWN" if k not in order]
        return [sides[k] for k in (*order, *rest)]

    def _route(self, start, goal):
        """Corridor cells from ``start`` to ``goal`` (both outside cells)
        avoiding rooms and their ring; A* with a bend penalty.  None if
        there is no way through."""
        def free(c):
            return (c == goal or (1 <= c[0] < DUNGEON_WIDTH - 1
                                  and 1 <= c[1] < DUNGEON_HEIGHT - 1
                                  and c not in self._reserved))
        dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
        h = lambda c: abs(c[0] - goal[0]) + abs(c[1] - goal[1])
        todo = [(h(start), 0, start, None)]
        came, best = {}, {(start, None): 0}
        while todo:
            _, cost, cell, d = heapq.heappop(todo)
            if cell == goal:
                path = [cell]
                key = (cell, d)
                while key in came:
                    key = came[key]
                    path.append(key[0])
                return path[::-1]
            if cost > best.get((cell, d), cost):
                continue
            for nd in dirs:
                n = (cell[0] + nd[0], cell[1] + nd[1])
                if not free(n):
                    continue
                c = cost + 1 + (TURN_COST if d is not None and nd != d else 0)
                if c < best.get((n, nd), 1 << 30):
                    best[(n, nd)] = c
                    came[(n, nd)] = (cell, d)
                    heapq.heappush(todo, (c + h(n), c, n, nd))
        return None

    def _link(self, a, b) -> None:
        """One corridor from a door in ``a`` to a door in ``b``."""
        for door_a, out_a in self._door_options(a, b):
            for door_b, out_b in self._door_options(b, a):
                path = self._route(out_a, out_b)
                if path is None:
                    continue
                for cell in path:
                    self.room_map.setdefault(cell, None)
                for room, door in ((a, door_a), (b, door_b)):
                    if door not in self.door_tiles:
                        room.add_door(door)
                        self.door_tiles.add(door)
                a.connect(door_a, b)
                b.connect(door_b, a)
                return
        # Boxed in (very rare): straight corridor between the centres.
        self._create_corridor(a.rect.center, b.rect.center)

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
            self._link(room, nearest)

    @staticmethod
    def _distance(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    def _create_corridor(self, start: Tuple[int, int], end: Tuple[int, int]):
        """Carve a straight horizontal-then-vertical corridor between two
        points (fallback when ``_link`` finds no route)."""
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

    def door_outside(self, room: Room, near: Tuple[int, int]) -> Tuple[int, int]:
        """The corridor cell just outside the door of ``room`` closest to
        cell ``near`` (where a hero who flees ends up)."""
        best = None
        for door in room.doors:
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                out = (door[0] + d[0], door[1] + d[1])
                if out in self.room_map and self.room_map[out] is None:
                    dist = abs(door[0] - near[0]) + abs(door[1] - near[1])
                    if best is None or dist < best[0]:
                        best = (dist, out)
        return best[1] if best else room.rect.center

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

    def render(self, surface: pygame.Surface, camera_offset: Tuple[int, int],
               seen: Optional[set] = None,
               overrides: Optional[Dict[Tuple[int, int], int]] = None):
        """Render the visible part of the dungeon to the main surface.

        ``seen`` (fog of war): when given, only seen floor cells and the
        walls touching them are drawn; the rest stays black.
        ``overrides`` maps cells to a tile index drawn instead (stairs).
        """
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
                if seen is not None and cell not in seen and not (
                        cell not in self.room_map and any(
                            (x + dx, y + dy) in seen
                            for dx in (-1, 0, 1) for dy in (-1, 0, 1))):
                    continue
                if overrides and cell in overrides:
                    tile = overrides[cell]
                elif self.room_map.get(cell) is not None:
                    tile = TILE_DOOR if cell in self.door_tiles else TILE_FLOOR
                elif cell in self.room_map:
                    tile = TILE_CORRIDOR
                else:
                    # Unlit stone walls, with a deterministic dark variant.
                    tile = TILE_WALL if (x * 31 + y * 17) % 9 else TILE_WALL_DARK
                surface.blit(
                    tiles[tile], (x * TILE_SIZE - offset_x, y * TILE_SIZE - offset_y)
                )
