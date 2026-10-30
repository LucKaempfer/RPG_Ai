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
    SEWER_FLOOR, SEWER_FLOOR_CRACK, SEWER_FLOOR_MOSS, SEWER_FLOOR_PUDDLE,
    SEWER_FLOOR_DRAIN, SEWER_FLOOR_BONES, SEWER_WALL, SEWER_WALL_STAIN,
    SEWER_WALL_PIPE, SEWER_WALL_MOSS, SEWER_WALL_DARK, SEWER_GRATE,
    SEWER_WALKWAY, SEWER_GATE_N, SEWER_GATE_S, SEWER_GATE_W, SEWER_GATE_E,
    SEWER_COLS, SEWER_ROWS,
)

# Configuration constants
TILE_SIZE = 32
DUNGEON_WIDTH = 60   # in tiles
DUNGEON_HEIGHT = 44  # in tiles
MAX_ROOM_SIZE = 10   # max width/height in tiles
MIN_ROOM_SIZE = 4
NUM_ROOMS = 13
# Free tiles kept between rooms: room walls stay solid and a corridor
# (with wall on both sides) fits through every gap.
ROOM_GAP = 3
# Darkness (alpha 0-255) over cells seen before but not in sight now:
# dark enough that remembered rooms never look like you see into them.
MEMORY_SHADE = 215
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

def _ring(cells):
    """``cells`` and their eight neighbours (a wall's look depends on
    the cells around it)."""
    return {(x + dx, y + dy) for x, y in cells
            for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


class Dungeon:
    """Handles generation and storage of rooms and corridors."""

    def __init__(self):
        self.rooms: List[Room] = []
        self.room_map: Dict[Tuple[int, int], Room] = {}  # world cell -> room
        self.door_tiles: set = set()  # world cells holding a door
        self.visited_corridors: set = set()  # corridor cells seen (minimap)
        self.minimap_surface: Optional[pygame.Surface] = None
        self._tile_frames: Optional[List[pygame.Surface]] = None
        self._shade: Optional[pygame.Surface] = None
        self._tile_cache: Dict[Tuple[int, int], int] = {}
        self._layer = None          # see render(): the whole floor, drawn

    def generate(self, seed: Optional[int] = None):
        # A private RNG: the seed fully determines the floor and the
        # global random state is left alone (M5 saves store the seed).
        rng = self.rng = random.Random(seed)
        self.rooms.clear()
        self.room_map.clear()
        self.visited_corridors.clear()
        self._tile_cache = {}
        self._layer = None
        attempts = 0
        while len(self.rooms) < NUM_ROOMS and attempts < NUM_ROOMS * 40:
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
        """Link the rooms with the shortest corridors that still reach
        every room: start from room 0 and keep adding the unlinked room
        whose walls are closest to an already linked room (Prim's minimum
        spanning tree over wall-to-wall gaps).  A tree, so every room is
        reachable and there are no long detours."""
        linked = [self.rooms[0]]
        rest = list(self.rooms[1:])
        while rest:
            room, near = min(((r, l) for r in rest for l in linked),
                             key=lambda p: self._gap(p[0].rect, p[1].rect))
            self._link(room, near)
            linked.append(room)
            rest.remove(room)

    @staticmethod
    def _gap(a, b) -> int:
        """Tiles of open ground between two rects (0 if they touch)."""
        dx = max(b.left - a.right, a.left - b.right, 0)
        dy = max(b.top - a.bottom, a.top - b.bottom, 0)
        return dx + dy

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

    def visible_from(self, cell: Tuple[int, int], radius: int) -> set:
        """Cells the hero at ``cell`` can see: within ``radius`` tiles and
        with a straight line to them that crosses only floor.  Walls and
        doors block sight (the wall or gate itself is seen); standing in a
        doorway, the hero sees both sides."""
        cx, cy = cell
        seen = set()
        r2 = radius * radius
        for tx in range(cx - radius, cx + radius + 1):
            for ty in range(cy - radius, cy + radius + 1):
                if (tx - cx) ** 2 + (ty - cy) ** 2 > r2:
                    continue
                if self._line_clear(cx, cy, tx, ty):
                    seen.add((tx, ty))
        return seen

    def _line_clear(self, x0, y0, x1, y1) -> bool:
        """Bresenham line: every cell strictly between the ends is floor
        and not a door, and no diagonal step slips between two blocked
        cells."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        opaque = lambda c: c not in self.room_map or c in self.door_tiles
        x, y = x0, y0
        while (x, y) != (x1, y1):
            px, py = x, y
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy
            # A diagonal step can't squeeze between two blocking cells
            # (e.g. past a gate and the wall beside it).
            if x != px and y != py and opaque((x, py)) and opaque((px, y)):
                return False
            if (x, y) != (x1, y1) and opaque((x, y)):
                return False
        return True

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
        """Sewer tileset frames (cached); index matches SEWER_*."""
        if self._tile_frames is None:
            self._tile_frames = assets.load_sheet(
                "sewer/tiles_v2.png", SEWER_COLS, SEWER_ROWS
            )
        return self._tile_frames

    def _tile_for(self, cell) -> int:
        """The sewer tile for ``cell``: doors are iron gates, corridors
        grates or walkways, room floors mostly flagstones with some moss,
        puddles, drains and bones; walls whose face shows (floor below)
        get slime stains, pipes and moss."""
        tile = self._tile_cache.get(cell)
        if tile is None:
            # Seeded per cell (not the floor's rng): the same spot always
            # looks the same, with no visible stripes or repeats.
            x, y = cell
            h = random.Random(x * 7919 + y * 104729).randrange(1 << 16)
            tile = self._tile_cache[cell] = self._pick_tile(cell, h)
        return tile

    def _pick_tile(self, cell, h) -> int:
        x, y = cell
        if self.room_map.get(cell) is not None:
            if cell in self.door_tiles:
                # The gate sits on the edge the corridor leaves from.
                for (dx, dy), gate in (((0, -1), SEWER_GATE_N), ((0, 1), SEWER_GATE_S),
                                       ((-1, 0), SEWER_GATE_W), ((1, 0), SEWER_GATE_E)):
                    n = (x + dx, y + dy)
                    if n in self.room_map and self.room_map[n] is None:
                        return gate
                return SEWER_GATE_N
            pick = h % 40
            return {0: SEWER_FLOOR_PUDDLE, 1: SEWER_FLOOR_PUDDLE,
                    2: SEWER_FLOOR_MOSS, 3: SEWER_FLOOR_MOSS, 4: SEWER_FLOOR_MOSS,
                    5: SEWER_FLOOR_CRACK, 6: SEWER_FLOOR_CRACK,
                    7: SEWER_FLOOR_DRAIN, 8: SEWER_FLOOR_BONES}.get(pick, SEWER_FLOOR)
        if cell in self.room_map:
            return SEWER_WALKWAY if h % 5 == 0 else SEWER_GRATE
        if (x, y + 1) in self.room_map:          # wall face over a floor
            pick = h % 12
            return {0: SEWER_WALL_PIPE, 1: SEWER_WALL_STAIN, 2: SEWER_WALL_STAIN,
                    3: SEWER_WALL_MOSS, 4: SEWER_WALL_MOSS}.get(pick, SEWER_WALL)
        return SEWER_WALL_DARK

    def _lit(self, cell, visible) -> bool:
        """In sight now: a visible cell, or a wall touching one."""
        if cell in visible:
            return True
        if cell in self.room_map:
            return False
        x, y = cell
        return any((x + dx, y + dy) in visible
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    def render(self, surface: pygame.Surface, camera_offset: Tuple[int, int],
               seen: Optional[set] = None,
               overrides: Optional[Dict[Tuple[int, int], int]] = None,
               visible: Optional[set] = None):
        """Render the visible part of the dungeon to the main surface.

        ``seen`` (fog of war): when given, only seen floor cells and the
        walls touching them are drawn; the rest stays black.
        ``overrides`` maps cells to a tile index drawn instead (stairs).
        ``visible``: cells in the hero's line of sight right now; seen
        cells outside it are drawn dimmed (remembered, not watched).

        The whole floor is kept drawn on one big surface (``_layer``) and
        only the cells whose look changed (newly seen, line of sight
        moved, an override) are redrawn there, so a frame is one blit:
        drawing every tile every frame was too slow for a phone.
        """
        vis = frozenset(visible) if visible is not None else None
        over = dict(overrides or {})
        layer = self._layer
        if (layer is None or layer["seen"] is not seen
                or (vis is None) != (layer["vis"] is None)):
            layer = self._layer = self._new_layer(seen)
            dirty = None                       # every cell
        else:
            dirty = set()
            if vis != layer["vis"]:
                dirty |= _ring(vis ^ layer["vis"])
            if seen is not None and len(seen) != len(layer["seen_copy"]):
                dirty |= _ring(seen - layer["seen_copy"])
            if over != layer["over"]:
                dirty |= set(over) ^ set(layer["over"])
                dirty |= {c for c in over if layer["over"].get(c) != over[c]}
        if dirty is None or dirty:
            self._redraw(layer, dirty, seen, vis, over)
        layer["vis"], layer["over"] = vis, over
        if seen is not None and len(seen) != len(layer["seen_copy"]):
            layer["seen_copy"] = set(seen)
        surface.blit(layer["surface"], (-camera_offset[0], -camera_offset[1]))

    def _new_layer(self, seen):
        size = (DUNGEON_WIDTH * TILE_SIZE, DUNGEON_HEIGHT * TILE_SIZE)
        surf = pygame.Surface(size)
        if pygame.display.get_init() and pygame.display.get_surface():
            surf = surf.convert()
        surf.fill((0, 0, 0))
        return {"surface": surf, "seen": seen, "seen_copy": set(),
                "vis": None, "over": {}}

    def _cell_look(self, cell, seen, vis, over):
        """(tile, dimmed) for a cell, or None when it stays black."""
        x, y = cell
        if seen is not None and cell not in seen and not (
                cell not in self.room_map and any(
                    (x + dx, y + dy) in seen
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1))):
            return None
        tile = over[cell] if cell in over else self._tile_for(cell)
        return tile, vis is not None and not self._lit(cell, vis)

    def _redraw(self, layer, cells, seen, vis, over):
        """Redraw ``cells`` (None: all) on the layer."""
        if self._shade is None:
            self._shade = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            self._shade.fill((0, 0, 0, MEMORY_SHADE))
        tiles = self._tiles()
        surf = layer["surface"]
        if cells is None:
            cells = [(x, y) for x in range(DUNGEON_WIDTH)
                     for y in range(DUNGEON_HEIGHT)]
        for cell in cells:
            x, y = cell
            if not (0 <= x < DUNGEON_WIDTH and 0 <= y < DUNGEON_HEIGHT):
                continue
            pos = (x * TILE_SIZE, y * TILE_SIZE)
            surf.fill((0, 0, 0), (pos, (TILE_SIZE, TILE_SIZE)))
            look = self._cell_look(cell, seen, vis, over)
            if look is None:
                continue
            tile, dim = look
            surf.blit(tiles[tile], pos)
            if dim:
                surf.blit(self._shade, pos)
