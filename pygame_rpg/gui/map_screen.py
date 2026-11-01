# pygame_rpg/gui/map_screen.py
"""The full map of the current floor (M in the dungeon, or the Map
button on a touch screen).

It shows only what the hero has found: every floor cell seen so far
(dim), the rooms walked into (bright), the corridor cells walked, the
walls around them, the shop and forge, unopened chests seen, the
stairs once open, and the hero as a blinking dot.  M, Esc or Back
returns to the floor exactly as it was (the dungeon is paused).
"""

import pygame

from .. import settings
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..dungeon import DUNGEON_WIDTH, DUNGEON_HEIGHT
from .screen import (
    draw_background, draw_panel, QUIT, Screen, font,
    TEXT_COLOR, DIM_TEXT, GOLD,
)

MAP_AREA = pygame.Rect(30, 92, SCREEN_WIDTH - 60, SCREEN_HEIGHT - 92 - 64)
SEEN_COLOR = (70, 74, 92)        # floor seen but not walked
ROOM_COLOR = (178, 178, 192)     # rooms walked into
CORRIDOR_COLOR = (124, 124, 140)  # corridor cells walked
WALL_COLOR = (66, 62, 80)         # walls next to seen floor
HERO_COLOR = (110, 215, 255)
CHEST_COLOR = (200, 150, 60)
STAIRS_COLOR = (90, 200, 120)
MARK_COLORS = {"shop": (230, 190, 90), "anvil": (240, 120, 50)}
MARK_NAMES = {"shop": "Merchant", "anvil": "Forge"}


def map_scale(area=MAP_AREA):
    """Whole pixels per tile so the floor fits ``area``."""
    return max(1, min(area.w // DUNGEON_WIDTH, area.h // DUNGEON_HEIGHT))


class MapScreen(Screen):
    name = "map"
    ambience = "sewer"

    def __init__(self, screen, dungeon_screen):
        super().__init__(screen)
        self.ds = dungeon_screen
        self.t = 0.0
        self._base = None            # the map without the blinking hero

    @property
    def explored(self):
        return len(self.ds.visited), len(self.ds.dungeon.rooms)

    def back(self):
        return ("resume", {"screen": self.ds})

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            # Let the floor save the hero and the run on the way out.
            return self.ds.handle_event(event)
        if settings.pressed(event, "map"):
            return self.back()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return self.back()
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            return self.back()
        return None

    def suspend(self):
        self.ds.suspend()

    def handle_update(self, dt):
        self.t += dt
        return None

    # -- drawing ---------------------------------------------------------
    def _render_map(self):
        """The explored floor on its own surface (drawn once)."""
        ds, d = self.ds, self.ds.dungeon
        s = map_scale()
        img = pygame.Surface((DUNGEON_WIDTH * s, DUNGEON_HEIGHT * s), pygame.SRCALPHA)
        img.fill((0, 0, 0, 0))

        def cell(c, color, inset=0):
            pygame.draw.rect(img, color, (c[0] * s + inset, c[1] * s + inset,
                                          s - 2 * inset, s - 2 * inset))

        walls = set()
        for x, y in ds.seen:
            for nx in (x - 1, x, x + 1):
                for ny in (y - 1, y, y + 1):
                    if not d.is_walkable((nx, ny)):
                        walls.add((nx, ny))
        for c in walls:
            if 0 <= c[0] < DUNGEON_WIDTH and 0 <= c[1] < DUNGEON_HEIGHT:
                cell(c, WALL_COLOR)
        for c in ds.seen:
            cell(c, SEEN_COLOR)
        for room in ds.visited:
            r = room.rect
            pygame.draw.rect(img, ROOM_COLOR, (r.x * s, r.y * s, r.w * s, r.h * s))
        for c in d.visited_corridors:
            cell(c, CORRIDOR_COLOR)

        for c, opened in ds.chests:
            if c in ds.seen and not opened:
                cell(c, CHEST_COLOR, inset=max(1, s // 4))
        if ds.stairs is not None and ds.stairs in ds.seen:
            cell(ds.stairs, STAIRS_COLOR)
        for kind, room in ds.special.items():
            if room in ds.visited:
                cx, cy = room.rect.center
                pygame.draw.circle(img, MARK_COLORS[kind],
                                   (cx * s + s // 2, cy * s + s // 2), max(3, s // 2 + 1))
        return img

    def draw(self, surface):
        draw_background(surface)
        title = font(40).render(f"Floor {self.ds.floor} map", True, GOLD)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 36)))
        seen, total = self.explored
        sub = font(20).render(f"Rooms explored: {seen} / {total}", True, DIM_TEXT)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 72)))

        if self._base is None:
            self._base = self._render_map()
        s = map_scale()
        frame = self._base.get_rect(center=MAP_AREA.center)
        draw_panel(surface, frame.inflate(16, 16))
        surface.blit(self._base, frame)

        if int(self.t * 3) % 2 == 0 or self.t < 0.3:   # blinking hero
            hx, hy = self.ds.cell()
            centre = (frame.x + hx * s + s // 2, frame.y + hy * s + s // 2)
            r = max(3, s // 2 + 1)
            pygame.draw.circle(surface, (0, 0, 0), centre, r + 2)
            pygame.draw.circle(surface, HERO_COLOR, centre, r)

        self._draw_legend(surface)

    def _draw_legend(self, surface):
        items = [("You", HERO_COLOR, "dot"), ("Room", ROOM_COLOR, "box"),
                 ("Corridor", CORRIDOR_COLOR, "box"), ("Seen", SEEN_COLOR, "box"),
                 ("Chest", CHEST_COLOR, "box")]
        for kind, room in self.ds.special.items():
            if room in self.ds.visited:
                items.append((MARK_NAMES[kind], MARK_COLORS[kind], "dot"))
        if self.ds.stairs is not None:
            items.append(("Stairs", STAIRS_COLOR, "box"))
        f = font(17)
        labels = [f.render(name, True, TEXT_COLOR) for name, _, _ in items]
        widths = [16 + lab.get_width() + 22 for lab in labels]
        x = (SCREEN_WIDTH - sum(widths)) // 2
        y = SCREEN_HEIGHT - 44
        for (name, color, shape), lab, w in zip(items, labels, widths):
            if shape == "dot":
                pygame.draw.circle(surface, color, (x + 6, y), 6)
            else:
                pygame.draw.rect(surface, color, (x, y - 6, 12, 12))
            surface.blit(lab, lab.get_rect(midleft=(x + 18, y)))
            x += w
        key = settings.action_label("map")
        hint = font(16).render(f"{key} / Esc: back to the floor", True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(SCREEN_WIDTH - 20, SCREEN_HEIGHT - 8)))
