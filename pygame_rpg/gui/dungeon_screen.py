# pygame_rpg/gui/dungeon_screen.py
"""Dungeon screen (M4): the hero explores one generated floor.

``dungeon.py`` builds and draws the floor; this screen owns the hero's
position, movement with wall collision, the walk animation, the camera,
fog of war, and what stands on the floor:

* enemies (``enemies.py``): stepping into a room where enemies stand
  starts a battle with the nearest one, then the next, until the room
  is clear, so no fight can be walked around.  Fleeing puts the hero
  back outside the room's nearest door.  This screen object is kept and
  resumed after each battle, so the floor survives the fight.  After a win, pending level-ups open the level-up
  screen right away (the stat pick happens mid-run).
* chests: walking into one opens it and rolls loot into the backpack.
* stairs: appear in the boss's room once the boss is beaten; stepping
  on them builds the next, harder floor.

The run is saved (``savegame.save_run``) on entering a floor, after
every battle, on Esc and on window close: floor, seed, beaten enemies,
opened chests, stairs, fog and the hero's spot.  Enemy and chest
placement follow the seed, so the save only records what changed.
I opens the inventory (equip, use potions) and comes back to the floor.
Esc returns to the Base *without* resting; the Base's Continue picks
the run up again, New Adventure (or a defeat) ends it.
"""

import random

import pygame

from ..assets import (
    AssetManager, HERO_COLS, HERO_ROWS, HERO_IDLE_COLS, HERO_WALK_COLS,
    HERO_DIR_DOWN, HERO_DIR_UP, HERO_DIR_LEFT, HERO_DIR_RIGHT,
    ENEMY_COLS, ENEMY_ROWS, ENEMY_IDLE, SEWER_MANHOLE,
)
from ..combat import WON, FLED
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT, CHESTS_PER_FLOOR, RUN_VERSION
from ..dungeon import Dungeon, TILE_SIZE, DUNGEON_WIDTH, DUNGEON_HEIGHT
from ..enemies import place_enemies, boss_room, cell_of, BOSS_TYPE
from ..items import roll_loot
from ..savegame import save_player, save_run
from .base_screen import pending_levels
from .effects import Particles
from .hud import Hud
from .screen import QUIT, Screen, font, DIM_TEXT

# Hero movement in pixels per second (trinket speed_bonus adds %).
WALK_SPEED = 160
# Collision box: smaller than a tile so the hero fits through
# one-tile corridors without snagging on corners.
HITBOX = 20
# Seconds per walk/idle animation frame.
FRAME_TIME = 0.12
# Centre distance at which the hero touches a chest.
TOUCH = 24
# How far (in tiles) the hero sees.  Walls block the view (line of
# sight); what was seen stays on the map but is drawn dimmed.
SIGHT = 8
# Torch light: the screen darkens from LIGHT_INNER px around the hero to
# LIGHT_DARK alpha at LIGHT_OUTER px.
LIGHT_INNER, LIGHT_OUTER, LIGHT_DARK = 120, 420, 190

MINIMAP_SCALE = 2
BANNER_TIME = 2.0   # seconds the "Floor N" banner shows on arrival


_LIGHT = None


def _light_mask():
    """Dark overlay with a soft clear circle in the middle (cached)."""
    global _LIGHT
    if _LIGHT is None:
        size = 2 * LIGHT_OUTER + max(SCREEN_WIDTH, SCREEN_HEIGHT)
        _LIGHT = pygame.Surface((size, size), pygame.SRCALPHA)
        _LIGHT.fill((0, 0, 0, LIGHT_DARK))
        c = size // 2
        for r in range(LIGHT_OUTER, LIGHT_INNER - 1, -4):
            t = (r - LIGHT_INNER) / (LIGHT_OUTER - LIGHT_INNER)
            pygame.draw.circle(_LIGHT, (0, 0, 0, int(LIGHT_DARK * t)), (c, c), r)
    return _LIGHT


class DungeonScreen(Screen):
    name = "dungeon"

    def __init__(self, screen, player, floor=1, seed=None, run=None):
        """``run``: a dict from ``to_run()`` (a saved run) to restore;
        it overrides ``floor`` and ``seed``."""
        super().__init__(screen)
        self.player = player
        if run is not None:
            floor, seed = run["floor"], run["seed"]
        if seed is None:
            seed = random.randrange(1 << 30)
        self.floor = floor
        self.seed = seed
        self.dungeon = Dungeon()
        self.dungeon.generate(seed)
        self.x, self.y = map(float, self.dungeon.spawn_point())
        self.facing = HERO_DIR_DOWN
        self.moving = False
        self.anim_t = 0.0
        self.visited = []
        self.seen = set()
        self.visible = set()                 # in line of sight right now
        self.enemies = place_enemies(self.dungeon, floor)
        self.all_enemies = list(self.enemies)   # placement order, for saves
        self.chests = self._place_chests()   # [cell, opened]
        self.stairs = None                   # cell, once the boss is beaten
        self.check_levels = False
        self.banner_t = BANNER_TIME
        self.fx = Particles()
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
        if run is not None:
            self._restore(run)
        self.save_run()

    # -- run saves -------------------------------------------------------
    def to_run(self) -> dict:
        """What a run save needs on top of the seed (JSON-ready)."""
        rooms = self.dungeon.rooms
        return {
            "version": RUN_VERSION,
            "floor": self.floor, "seed": self.seed,
            "x": self.x, "y": self.y, "facing": self.facing,
            "beaten": [i for i, e in enumerate(self.all_enemies)
                       if not e.alive],
            "chests": [opened for _, opened in self.chests],
            "stairs": self.stairs is not None,
            "seen": sorted(self.seen),
            "visited": [rooms.index(r) for r in self.visited],
            "corridors": sorted(self.dungeon.visited_corridors),
        }

    def _restore(self, run: dict) -> None:
        for i in run.get("beaten", []):
            if 0 <= i < len(self.all_enemies):
                self.all_enemies[i].hp = 0
        self.enemies = [e for e in self.all_enemies if e.alive]
        for chest, opened in zip(self.chests, run.get("chests", [])):
            chest[1] = bool(opened)
        if run.get("stairs"):
            self.stairs = boss_room(self.dungeon).rect.center
        self.seen = {tuple(c) for c in run.get("seen", [])}
        rooms = self.dungeon.rooms
        self.visited = [rooms[i] for i in run.get("visited", [])
                        if 0 <= i < len(rooms)]
        self.dungeon.visited_corridors = {tuple(c) for c in
                                          run.get("corridors", [])}
        x, y = run.get("x", self.x), run.get("y", self.y)
        if self._fits(x, y):
            self.x, self.y = float(x), float(y)
        self.facing = run.get("facing", self.facing)
        self.hud.messages.clear()
        self.hud.say(f"Floor {self.floor}: run continued.")
        self._mark_visited()

    def save_run(self) -> None:
        save_run(self.player.name, self.to_run())

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
        else:
            self.dungeon.visited_corridors.add(cell)
        if cell != getattr(self, "_sight_from", None):
            self._sight_from = cell
            self.visible = {c for c in self.dungeon.visible_from(cell, SIGHT)
                            if self.dungeon.is_walkable(c)}
            self.seen |= self.visible

    def camera(self):
        """Top-left world pixel of the view, centred on the hero and
        clamped to the map."""
        max_x = DUNGEON_WIDTH * TILE_SIZE - SCREEN_WIDTH
        max_y = DUNGEON_HEIGHT * TILE_SIZE - SCREEN_HEIGHT
        cx = int(self.x) - SCREEN_WIDTH // 2
        cy = int(self.y) - SCREEN_HEIGHT // 2
        return (max(0, min(max_x, cx)), max(0, min(max_y, cy)))

    # -- encounters ------------------------------------------------------
    def room_enemy(self):
        """The enemy to fight now: the nearest living one in the room the
        hero stands in (None in corridors and cleared rooms)."""
        room = self.dungeon.get_room_at(self.cell())
        if room is None:
            return None
        here = [e for e in self.enemies if e.alive and room.contains(cell_of(e))]
        return min(here, default=None,
                   key=lambda e: (e.x - self.x) ** 2 + (e.y - self.y) ** 2)

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
            # Back out through the nearest door; the room stays hostile.
            room = self.dungeon.get_room_at(self.cell())
            if room is not None:
                out = self.dungeon.door_outside(room, self.cell())
                self.x, self.y = self._centre(out)
                self._mark_visited()
                self.hud.say(f"You escaped from the {battle.enemy.name}.")
        self.save_run()

    def _open_chests(self):
        for chest in self.chests:
            cell, opened = chest
            if not opened and self._near(*self._centre(cell)):
                chest[1] = True
                self.fx.burst(*self._centre(cell), (240, 200, 90), count=22)
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
            self.save_run()
            return QUIT
        if event.type == pygame.KEYDOWN and event.key == pygame.K_i:
            return ("inventory", {"player": self.player, "return_to": self})
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            save_player(self.player)
            self.save_run()
            return ("base", {"player": self.player})
        return None

    def step(self, dx, dy, dt):
        """One frame of play with the given input; returns a transition
        request or None.  ``handle_update`` feeds it the keyboard; tests
        call it directly."""
        self.anim_t += dt
        self.banner_t = max(0.0, self.banner_t - dt)
        self.fx.update(dt)
        self.hud.update(dt)
        if self.check_levels:
            self.check_levels = False
            if pending_levels(self.player) > 0:
                return ("level_up", {"player": self.player, "return_to": self})
        self.move(dx, dy, dt)
        self._open_chests()
        enemy = self.room_enemy()
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
        overrides = {self.stairs: SEWER_MANHOLE} if self.stairs else None
        self.dungeon.render(surface, (ox, oy), seen=self.seen,
                            overrides=overrides, visible=self.visible)
        blink = int(self.anim_t / 0.4) % 2

        for cell, opened in self.chests:
            if cell in self.seen:
                x, y = self._centre(cell)
                img = self.chest_frames[1 if opened else 0]
                surface.blit(img, img.get_rect(center=(x - ox, y - oy)))

        for e in self.enemies:
            if cell_of(e) not in self.visible:      # walls hide enemies
                continue
            img = self.enemy_frames[e.type.sprite][ENEMY_IDLE[blink]]
            if e.boss:
                img = pygame.transform.scale(img, (48, 48))
            surface.blit(img, img.get_rect(center=(e.x - ox, e.y - oy)))

        self.fx.draw(surface, (ox, oy))

        cols = HERO_WALK_COLS if self.moving else HERO_IDLE_COLS
        col = cols[int(self.anim_t / FRAME_TIME) % len(cols)]
        frame = self.frames[self.facing * HERO_COLS + col]
        surface.blit(frame, frame.get_rect(
            center=(int(self.x) - ox, int(self.y) - oy)))

        light = _light_mask()
        surface.blit(light, light.get_rect(center=(int(self.x) - ox, int(self.y) - oy)))

        self.hud.draw(surface, self.player, self.floor)
        if self.banner_t > 0:
            alpha = int(255 * min(1.0, self.banner_t / 0.5))
            img = font(48).render(f"Floor {self.floor}", True, (235, 200, 90))
            shadow = font(48).render(f"Floor {self.floor}", True, (0, 0, 0))
            for im in (img, shadow):
                im.set_alpha(alpha)
            r = img.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3))
            surface.blit(shadow, r.move(2, 2))
            surface.blit(img, r)
        mm_w = DUNGEON_WIDTH * MINIMAP_SCALE
        self.dungeon.draw_minimap(
            surface, self.visited, (SCREEN_WIDTH - mm_w - 10, 10),
            self.cell(), scale=MINIMAP_SCALE)
        hint = font(18).render(
            "Arrows / WASD: move    I: inventory    Esc: Base (run is kept)", True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 12, SCREEN_HEIGHT - 10)))
