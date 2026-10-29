# pygame_rpg/gui/dungeon_screen.py
"""Dungeon screen (M4): the hero explores one generated floor.

``dungeon.py`` builds and draws the floor; this screen owns the hero's
position, movement with wall collision, the walk animation, the camera,
fog of war, and what stands on the floor:

* enemies (``enemies.py``): bumping into one opens the battle screen;
  this screen object is kept and resumed afterwards, so the floor
  survives the fight.  After a win, pending level-ups open the level-up
  screen right away (the stat pick happens mid-run).
* chests: walking into one opens it and rolls loot into the backpack.
* stairs: appear in the boss's room once the boss is beaten; stepping
  on them builds the next, harder floor.

Arrows / WASD move.  Esc saves, rests (full HP / MP) and returns to the
Base; the next Adventure starts again on floor 1.  Window close saves,
then quits.
"""

import pygame

from ..assets import (
    AssetManager, HERO_COLS, HERO_ROWS, HERO_IDLE_COLS, HERO_WALK_COLS,
    HERO_DIR_DOWN, HERO_DIR_UP, HERO_DIR_LEFT, HERO_DIR_RIGHT,
    ENEMY_COLS, ENEMY_ROWS, ENEMY_IDLE, TILE_STAIRS_DOWN,
)
from ..combat import WON, FLED
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..dungeon import Dungeon, TILE_SIZE, DUNGEON_WIDTH, DUNGEON_HEIGHT
from ..enemies import place_enemies, boss_room, BOSS_TYPE
from ..items import roll_loot
from ..savegame import save_player
from .base_screen import pending_levels
from .hud import Hud
from .screen import QUIT, Screen, font, DIM_TEXT

# Hero movement in pixels per second (trinket speed_bonus adds %).
WALK_SPEED = 160
# Collision box: smaller than a tile so the hero fits through
# one-tile corridors without snagging on corners.
HITBOX = 20
# Seconds per walk/idle animation frame.
FRAME_TIME = 0.12
# Centre distance at which the hero touches an enemy or a chest.
TOUCH = 24
# How far (in tiles) the hero sees into corridors; rooms light up whole.
SIGHT = 2
CHESTS_PER_FLOOR = 2

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
        self.seen = set()
        self.enemies = place_enemies(self.dungeon, floor)
        self.chests = self._place_chests()   # [cell, opened]
        self.stairs = None                   # cell, once the boss is beaten
        self.ignore = None      # enemy just fled from: no re-bump until apart
        self.check_levels = False
        self.hud = Hud()
        self.hud.say(f"Floor {floor}: beat the {BOSS_TYPE.name} to open the stairs.")
        self._mark_visited()
        assets = AssetManager()
        self.frames = assets.load_sheet("player/hero_sheet.png",
                                        HERO_COLS, HERO_ROWS)
        self.enemy_frames = {}
        for e in self.enemies:
            if e.type.sprite not in self.enemy_frames:
                self.enemy_frames[e.type.sprite] = assets.load_sheet(
                    f"enemies/{e.type.sprite}.png", ENEMY_COLS, ENEMY_ROWS)
        self.chest_frames = assets.load_sheet("objects/chest.png", 2, 1)

    # -- floor contents --------------------------------------------------
    def _place_chests(self):
        """CHESTS_PER_FLOOR chests in random rooms (not the entrance, not
        the boss room), on interior cells no enemy stands on."""
        rng = self.dungeon.rng
        lair = boss_room(self.dungeon)
        taken = {(int(e.x // TILE_SIZE), int(e.y // TILE_SIZE))
                 for e in self.enemies}
        rooms = [r for r in self.dungeon.rooms[1:] if r is not lair]
        chests = []
        for room in rng.sample(rooms, min(CHESTS_PER_FLOOR, len(rooms))):
            r = room.rect
            cells = [(x, y) for x in range(r.left + 1, r.right - 1)
                     for y in range(r.top + 1, r.bottom - 1)
                     if (x, y) not in taken]
            if cells:
                cell = rng.choice(cells)
                taken.add(cell)
                chests.append([cell, False])
        return chests

    @staticmethod
    def _centre(cell):
        return (cell[0] * TILE_SIZE + TILE_SIZE / 2,
                cell[1] * TILE_SIZE + TILE_SIZE / 2)

    def _near(self, x, y) -> bool:
        return abs(self.x - x) < TOUCH and abs(self.y - y) < TOUCH

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
                r = room.rect
                self.seen.update((x, y) for x in range(r.left, r.right)
                                 for y in range(r.top, r.bottom))
        else:
            self.dungeon.visited_corridors.add(cell)
        cx, cy = cell
        for x in range(cx - SIGHT, cx + SIGHT + 1):
            for y in range(cy - SIGHT, cy + SIGHT + 1):
                if self.dungeon.is_walkable((x, y)):
                    self.seen.add((x, y))

    def camera(self):
        """Top-left world pixel of the view, centred on the hero and
        clamped to the map."""
        max_x = DUNGEON_WIDTH * TILE_SIZE - SCREEN_WIDTH
        max_y = DUNGEON_HEIGHT * TILE_SIZE - SCREEN_HEIGHT
        cx = int(self.x) - SCREEN_WIDTH // 2
        cy = int(self.y) - SCREEN_HEIGHT // 2
        return (max(0, min(max_x, cx)), max(0, min(max_y, cy)))

    # -- encounters ------------------------------------------------------
    def touching_enemy(self):
        """The enemy the hero bumps into, if any (ignoring the one just
        fled from until the hero has stepped away)."""
        if self.ignore is not None and not self._near(self.ignore.x, self.ignore.y):
            self.ignore = None
        for e in self.enemies:
            if e.alive and e is not self.ignore and self._near(e.x, e.y):
                return e
        return None

    def battle_over(self, battle) -> None:
        """Called by the battle screen before it resumes this floor."""
        self.enemies = [e for e in self.enemies if e.alive]
        if battle.state == WON:
            self.hud.say(f"Defeated the {battle.enemy.name}! +{battle.xp_gained} XP")
            for item in battle.loot:
                self.hud.say(f"Found: {item.name}")
            if battle.enemy.boss:
                self.stairs = boss_room(self.dungeon).rect.center
                self.hud.say("Stairs down have appeared!")
            self.check_levels = True
        elif battle.state == FLED:
            self.ignore = battle.enemy

    def _open_chests(self):
        for chest in self.chests:
            cell, opened = chest
            if not opened and self._near(*self._centre(cell)):
                chest[1] = True
                item = roll_loot(self.dungeon.rng,
                                 max_level=min(4, self.floor + 1))
                if self.player.can_carry(item):
                    self.player.inventory.append(item)
                    self.hud.say(f"Chest: {item.name} ({item.rarity})")
                else:
                    self.hud.say(f"Chest: {item.name}, too heavy to carry")

    # -- Screen hooks ----------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            save_player(self.player)
            return QUIT
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.player.rest()
            save_player(self.player)
            return ("base", {"player": self.player})
        return None

    def step(self, dx, dy, dt):
        """One frame of play with the given input; returns a transition
        request or None.  ``handle_update`` feeds it the keyboard; tests
        call it directly."""
        self.anim_t += dt
        self.hud.update(dt)
        if self.check_levels:
            self.check_levels = False
            if pending_levels(self.player) > 0:
                return ("level_up", {"player": self.player, "return_to": self})
        self.move(dx, dy, dt)
        self._open_chests()
        enemy = self.touching_enemy()
        if enemy is not None:
            self.moving = False
            return ("battle", {"player": self.player, "enemy": enemy,
                               "dungeon": self})
        if self.stairs is not None and self.cell() == self.stairs:
            save_player(self.player)
            return ("dungeon", {"player": self.player, "floor": self.floor + 1})
        return None

    def handle_update(self, dt):
        keys = pygame.key.get_pressed()
        dx = ((keys[pygame.K_RIGHT] or keys[pygame.K_d])
              - (keys[pygame.K_LEFT] or keys[pygame.K_a]))
        dy = ((keys[pygame.K_DOWN] or keys[pygame.K_s])
              - (keys[pygame.K_UP] or keys[pygame.K_w]))
        return self.step(dx, dy, dt)

    # -- drawing ---------------------------------------------------------
    def draw(self, surface):
        surface.fill((0, 0, 0))
        ox, oy = self.camera()
        overrides = {self.stairs: TILE_STAIRS_DOWN} if self.stairs else None
        self.dungeon.render(surface, (ox, oy), seen=self.seen,
                            overrides=overrides)
        blink = int(self.anim_t / 0.4) % 2

        for cell, opened in self.chests:
            if cell in self.seen:
                x, y = self._centre(cell)
                img = self.chest_frames[1 if opened else 0]
                surface.blit(img, img.get_rect(center=(x - ox, y - oy)))

        for e in self.enemies:
            cell = (int(e.x // TILE_SIZE), int(e.y // TILE_SIZE))
            if cell not in self.seen:
                continue
            img = self.enemy_frames[e.type.sprite][ENEMY_IDLE[blink]]
            if e.boss:
                img = pygame.transform.scale(img, (48, 48))
            surface.blit(img, img.get_rect(center=(e.x - ox, e.y - oy)))

        cols = HERO_WALK_COLS if self.moving else HERO_IDLE_COLS
        col = cols[int(self.anim_t / FRAME_TIME) % len(cols)]
        frame = self.frames[self.facing * HERO_COLS + col]
        surface.blit(frame, frame.get_rect(
            center=(int(self.x) - ox, int(self.y) - oy)))

        self.hud.draw(surface, self.player, self.floor)
        mm_w = DUNGEON_WIDTH * MINIMAP_SCALE
        self.dungeon.draw_minimap(
            surface, self.visited, (SCREEN_WIDTH - mm_w - 10, 10),
            self.cell(), scale=MINIMAP_SCALE)
        hint = font(18).render(
            "Arrows / WASD: move    Esc: back to base", True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 12, SCREEN_HEIGHT - 10)))
