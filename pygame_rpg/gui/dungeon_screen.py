# pygame_rpg/gui/dungeon_screen.py
"""Dungeon screen (M4): the hero explores one generated floor.

``dungeon.py`` builds and draws the floor; this screen owns the hero's
position, movement with wall collision, the walk animation, the camera,
fog of war, and what stands on the floor:

* enemies (``enemies.py``): stepping into a room where enemies stand
  starts one battle against all of them (the nearest is the first
  target), so no fight can be walked around.  Fleeing puts the hero
  back outside the room's nearest door.  This screen object is kept and
  resumed after each battle, so the floor survives the fight.  After a win, pending level-ups open the level-up
  screen right away (the stat pick happens mid-run).
* chests: walking into one opens it and rolls loot into the backpack.
* props (``props.py``): barrels, crates, pots and other clutter along
  the room walls; standing props block the way.  Space (or F) swings
  the weapon at the prop in front, or shoots an arrow / bolt with a
  ranged or magic weapon; a prop breaks after a few hits and leaves
  crafting materials in the hero's pouch.
* the shop (``special_rooms.py``, ``shop.py``): one safe room per floor
  with a merchant; E next to them opens the shop screen.  Gear bought
  there stays sold out for the floor.
* the forge: another safe room with an anvil; E next to it opens the
  forge screen (craft weapons from blueprints, upgrade them;
  ``crafting.py``).  Blueprints drop from the boss, sometimes from
  enemies, chests and smashed props.
* lost writings (``lore.py``): books, notes, scrolls, letters and
  slates on floors 1-5 that tell the story; walking onto one opens the
  story reader and files it in the hero's journal.  Beating the floor-5
  boss tells the epilogue.
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

import math
import random

import pygame

from .. import audio, device, settings
from ..assets import (
    AssetManager, gear_of, HERO_COLS, HERO_IDLE_COLS, HERO_WALK_COLS, HERO_STEP_FRAMES,
    HERO_ATTACK_COLS,
    HERO_DIR_DOWN, HERO_DIR_UP, HERO_DIR_LEFT, HERO_DIR_RIGHT,
    ENEMY_COLS, ENEMY_ROWS, ENEMY_IDLE, SEWER_MANHOLE,
)
from ..combat import WON, FLED, weapon_type
from ..config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, CHESTS_PER_FLOOR, RUN_VERSION,
    PROP_GOLD, PROP_GOLD_CHANCE, PROP_JUNK_CHANCE,
    BLUEPRINT_CHEST_CHANCE, BLUEPRINT_PROP_CHANCE,
)
from ..crafting import roll_blueprint
from ..dungeon import (
    Dungeon, TILE_SIZE, DUNGEON_WIDTH, DUNGEON_HEIGHT, MEMORY_SHADE,
)
from ..enemies import place_enemies, boss_room, cell_of, BOSS_TYPE
from ..items import roll_loot, roll_junk, item_by_id
from ..lore import (lore_cells, CHAPTERS, LORE_FLOORS, EPILOGUE,
                    EPILOGUE_TITLE)
from ..props import place_props, salvage, PROP_KINDS
from ..shop import roll_stock
from ..special_rooms import special_rooms, keeper_cell
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
# Seconds per idle animation frame.  Walk frames follow the distance
# walked instead (one stride = two footsteps = all HERO_WALK_COLS), so
# the feet never slide, whatever the speed.
FRAME_TIME = 0.4
# Centre distance at which the hero touches a chest.
TOUCH = 24
# Pixels walked per footstep (half a stride).
STRIDE = 34
# Little splash at the feet on every footstep.
SPLASH_COLOR = (120, 150, 120)
# How far (in tiles) the hero sees.  Walls block the view (line of
# sight); what was seen stays on the map but is drawn dimmed.
SIGHT = 8
# Torch light: the screen darkens from LIGHT_INNER px around the hero to
# LIGHT_DARK alpha at LIGHT_OUTER px.
LIGHT_INNER, LIGHT_OUTER, LIGHT_DARK = 120, 420, 190

# Talking to a room's keeper (the merchant): centre distance in px.
TALK = 52

# Attacking props: seconds between attacks, how long the swing shows,
# how far ahead a melee swing reaches (px from the hero's centre), and
# shots (px per second, range in px).
ATTACK_COOLDOWN = 0.35
SWING_TIME = 0.2
REACH = 26
SHOT_SPEED = 420
SHOT_RANGE = 8 * TILE_SIZE
FACING_STEP = {HERO_DIR_DOWN: (0, 1), HERO_DIR_UP: (0, -1),
               HERO_DIR_LEFT: (-1, 0), HERO_DIR_RIGHT: (1, 0)}
# Swing arc (start, stop angle in radians, counter-clockwise) per facing.
SWING_ARC = {HERO_DIR_RIGHT: (-1.05, 1.05), HERO_DIR_UP: (0.52, 2.62),
             HERO_DIR_LEFT: (2.09, 4.19), HERO_DIR_DOWN: (3.67, 5.76)}
# Splinters per prop kind, and the sound it breaks with.
PROP_COLORS = {"barrel": (150, 100, 56), "crate": (150, 100, 56),
               "pot": (180, 104, 70), "sack": (190, 168, 124),
               "bucket": (140, 82, 44), "bones": (214, 206, 186),
               "rubble": (130, 132, 126)}
BREAK_SOUND = {"barrel": "crack", "crate": "crack", "sack": "crack",
               "bucket": "bash", "pot": "shatter", "bones": "shatter",
               "rubble": "shatter"}
# Shot colours: arrows, and magic bolts by the wand's ailment.
SHOT_COLORS = {"ranged": (200, 170, 110), "burning": (255, 140, 60),
               "poison": (120, 220, 90), "electrocuted": (140, 200, 255),
               "magic": (170, 130, 255)}

MINIMAP_SCALE = 2
MINIMAP_MARK = {"shop": (230, 190, 90), "anvil": (240, 120, 50)}
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


_SHADOWS = {}


def _shadow(size):
    """Soft dark ellipse that grounds a sprite ``size`` px wide (cached)."""
    if size not in _SHADOWS:
        surf = pygame.Surface((size * 3 // 4, size // 5 + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (0, 0, 0, 90), surf.get_rect())
        _SHADOWS[size] = surf
    return _SHADOWS[size]



_LORE_SPRITES = {}


def _lore_sprite(kind):
    """A lost writing lying on the floor, drawn in code (20 x 20)."""
    if kind in _LORE_SPRITES:
        return _LORE_SPRITES[kind]
    img = pygame.Surface((20, 20), pygame.SRCALPHA)
    paper, ink, edge = (226, 210, 172), (90, 70, 50), (120, 90, 56)
    if kind == "book":
        pygame.draw.rect(img, (110, 44, 36), (2, 3, 16, 14), border_radius=2)
        pygame.draw.rect(img, paper, (4, 4, 13, 12))
        pygame.draw.rect(img, (140, 58, 46), (2, 3, 14, 12), border_radius=2)
        pygame.draw.line(img, (200, 160, 80), (5, 6), (12, 6), 1)
        pygame.draw.line(img, (200, 160, 80), (5, 12), (12, 12), 1)
    elif kind == "scroll":
        pygame.draw.rect(img, paper, (4, 5, 12, 10))
        pygame.draw.rect(img, edge, (2, 4, 16, 3), border_radius=1)
        pygame.draw.rect(img, edge, (2, 13, 16, 3), border_radius=1)
        for y in (9, 11):
            pygame.draw.line(img, ink, (6, y), (14, y), 1)
    elif kind == "tablet":
        pygame.draw.rect(img, (70, 70, 78), (3, 2, 14, 16), border_radius=3)
        pygame.draw.rect(img, (40, 40, 46), (3, 2, 14, 16), 1, border_radius=3)
        for y in (6, 9, 12, 15):
            pygame.draw.line(img, (150, 150, 160), (6, y), (14, y), 1)
    else:                                   # note / letter
        pygame.draw.polygon(img, paper, [(3, 4), (16, 2), (17, 16), (4, 18)])
        pygame.draw.polygon(img, edge, [(3, 4), (16, 2), (17, 16), (4, 18)], 1)
        if kind == "letter":
            pygame.draw.circle(img, (160, 30, 30), (10, 11), 3)   # wax seal
        else:
            for y in (7, 10, 13):
                pygame.draw.line(img, ink, (6, y), (14, y - 1), 1)
    _LORE_SPRITES[kind] = img
    return img


def _lore_halo(alpha):
    """A soft warm glow under a writing, so it can be spotted."""
    key = ("halo", alpha // 10)
    if key not in _LORE_SPRITES:
        img = pygame.Surface((36, 36), pygame.SRCALPHA)
        for r, a in ((18, 0.35), (13, 0.6), (8, 1.0)):
            pygame.draw.circle(img, (255, 220, 140, int(alpha * a)), (18, 18), r)
        _LORE_SPRITES[key] = img
    return _LORE_SPRITES[key]


def controls_hint():
    """The bottom-line key hint, following the player's key bindings
    (or naming the on-screen controls on a touch screen)."""
    if device.TOUCH:
        return "D-pad: move    A: attack    B: talk    Bag: inventory    Menu: Base"
    moves = ("up", "left", "down", "right")
    if all(settings.current.keys[a] == settings.DEFAULT_KEYS[a] for a in moves):
        move = "Arrows / WASD"
    else:
        move = " ".join(settings.action_label(a) for a in moves)
    a = settings.action_label
    return (f"{move}: move    {a('attack')}: attack    {a('interact')}: talk"
            f"    {a('inventory')}: inventory    Esc: Base")

class DungeonScreen(Screen):
    name = "dungeon"
    ambience = "sewer"

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
        self.walked = 0.0   # pixels walked in this stride (walk frames, footsteps)
        self.attack_cd = 0.0    # seconds until the next attack
        self.swing_t = 0.0      # seconds the current swing still shows
        self.swing_melee = False
        self.shots = []         # [x, y, dx, dy, distance, colour]
        self.visited = []
        self.seen = set()
        self.visible = set()                 # in line of sight right now
        # Special rooms (the shop) are safe: no enemies, chests or props.
        self.special = special_rooms(self.dungeon, seed)
        safe = list(self.special.values())
        self.enemies = [e for e in place_enemies(self.dungeon, floor)
                        if not any(r.contains(cell_of(e)) for r in safe)]
        self.all_enemies = list(self.enemies)   # placement order, for saves
        self.chests = self._place_chests()   # [cell, opened]
        self.props = [p for p in place_props(self.dungeon, seed)
                      if not any(r.contains(p.cell) for r in safe)]
        self.keepers = {kind: keeper_cell(room) for kind, room in self.special.items()}
        self.shop_stock = roll_stock(seed, floor)
        self.shop_sold = set()               # stock indices bought out
        self.prop_at = {p.cell: p for p in self.props}
        # Lost writings not found yet: [(entry, cell)].
        blocked = ({cell_of(e) for e in self.enemies}
                   | {c for c, _ in self.chests} | set(self.keepers.values()))
        self.lore = [(e, c) for e, c in lore_cells(self.dungeon, seed, floor, blocked)
                     if e.id not in player.lore]
        self.story = None                    # story transition to show next
        self.stairs = None                   # cell, once the boss is beaten
        self.check_levels = False
        self.banner_t = BANNER_TIME
        self.fx = Particles()
        self.hud = Hud()
        self.hud.say(f"Floor {floor}: beat the {BOSS_TYPE.name} to open the stairs.")
        if self.lore:
            n = len(self.lore)
            self.hud.say(f"{n} lost writing{'s' if n > 1 else ''} lie{'' if n > 1 else 's'}"
                         " somewhere on this floor.")
        self._mark_visited()
        assets = AssetManager()
        self.assets = assets
        self.enemy_frames = {}
        for e in self.enemies:
            if e.type.sprite not in self.enemy_frames:
                self.enemy_frames[e.type.sprite] = assets.load_sheet(
                    f"enemies/{e.type.sprite}.png", ENEMY_COLS, ENEMY_ROWS)
        self.chest_frames = assets.load_sheet("objects/chest.png", 2, 1)
        self.keeper_frames = {"shop": assets.load_sheet("objects/merchant.png", 2, 1),
                              "anvil": assets.load_sheet("objects/anvil.png", 2, 1)}
        self.prop_frames = assets.load_sheet("objects/props.png",
                                             len(PROP_KINDS), 2)
        self._prop_shade = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self._prop_shade.fill((0, 0, 0, MEMORY_SHADE))
        if run is not None:
            self._restore(run)
        self.save_run()

    def hero_frames(self):
        """The hero's frames in their look and current gear (cached per
        combination, so a new weapon or armour shows at once)."""
        return self.assets.hero_frames(self.player.look, gear_of(self.player.equipment))

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
            "props": [i for i, p in enumerate(self.props) if p.broken],
            "shop_sold": sorted(self.shop_sold),
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
        self.shop_sold = {i for i in run.get("shop_sold", [])
                          if 0 <= i < len(self.shop_stock)}
        for i in run.get("props", []):
            if 0 <= i < len(self.props):
                self.props[i].broken, self.props[i].hp = True, 0
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
        rooms = [r for r in self.dungeon.rooms[1:]
                 if r is not lair and r not in self.special.values()]
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
        """Whether the hitbox centred on (x, y) touches only floor (and no
        standing prop)."""
        half = HITBOX / 2
        for cx in (x - half, x + half - 1):
            for cy in (y - half, y + half - 1):
                cell = (int(cx // TILE_SIZE), int(cy // TILE_SIZE))
                if not self.dungeon.is_walkable(cell):
                    return False
                prop = self.prop_at.get(cell)
                if prop is not None and prop.solid:
                    return False
                if cell in self.keepers.values():
                    return False
        return True

    def move(self, dx, dy, dt) -> None:
        """Move by direction (dx, dy) in -1..1 for ``dt`` seconds.

        Axes are resolved separately, so the hero slides along walls
        instead of sticking to them.
        """
        self.moving = bool(dx or dy)
        if not self.moving:
            # Standing still: the next walk starts with a footstep.
            self.walked = 2 * STRIDE - 1
            return
        if dx and dy:  # same speed diagonally
            dx, dy = dx * 0.7071, dy * 0.7071
        step = self.speed * dt
        old = (self.x, self.y)
        nx = self.x + dx * step
        if self._fits(nx, self.y):
            self.x = nx
        ny = self.y + dy * step
        if self._fits(self.x, ny):
            self.y = ny
        self._footsteps(old)
        if abs(dx) >= abs(dy):
            self.facing = HERO_DIR_RIGHT if dx > 0 else HERO_DIR_LEFT
        else:
            self.facing = HERO_DIR_DOWN if dy > 0 else HERO_DIR_UP
        self._mark_visited()

    def walk_frame(self) -> int:
        """Index into HERO_WALK_COLS for the distance walked so far."""
        n = len(HERO_WALK_COLS)
        return int(self.walked / (2 * STRIDE) * n) % n

    def _footsteps(self, old):
        """A splash whenever a foot lands (the walk frame reaches one of
        HERO_STEP_FRAMES); a door creaks when the hero steps onto its
        tile."""
        before = self.walk_frame()
        self.walked = (self.walked + abs(self.x - old[0]) + abs(self.y - old[1])) % (2 * STRIDE)
        now = self.walk_frame()
        if now != before and now in HERO_STEP_FRAMES:
            audio.play("step", volume=0.6)
            self.fx.burst(self.x, self.y + 12, SPLASH_COLOR, count=5,
                          speed=45, life=0.3, size=2)
        doors = self.dungeon.door_tiles
        before = (int(old[0] // TILE_SIZE), int(old[1] // TILE_SIZE))
        if self.cell() in doors and before != self.cell():
            audio.play("door", volume=0.7)

    def _mark_visited(self):
        cell = self.cell()
        room = self.dungeon.get_room_at(cell)
        if room is not None:
            if room not in self.visited:
                self.visited.append(room)
                if room is self.special.get("shop"):
                    self.hud.say("A merchant has set up shop here. Press E to trade.")
                elif room is self.special.get("anvil"):
                    self.hud.say("An anvil glows here. Press E to craft and upgrade.")
        else:
            self.dungeon.visited_corridors.add(cell)
        # A gate stays shut until you step through it: on a door cell the
        # hero still sees from the side they came from.
        if cell in self.dungeon.door_tiles:
            eye = getattr(self, "_last_open_cell", cell)
        else:
            eye = self._last_open_cell = cell
        if eye != getattr(self, "_sight_from", None):
            self._sight_from = eye
            self.visible = {c for c in self.dungeon.visible_from(eye, SIGHT)
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
    def room_enemies(self):
        """Everyone to fight now: the living enemies in the room the hero
        stands in, nearest first (empty in corridors and cleared rooms)."""
        room = self.dungeon.get_room_at(self.cell())
        if room is None:
            return []
        here = [e for e in self.enemies if e.alive and room.contains(cell_of(e))]
        return sorted(here, key=lambda e: (e.x - self.x) ** 2 + (e.y - self.y) ** 2)

    def room_enemy(self):
        """The nearest enemy in the hero's room, or None."""
        return next(iter(self.room_enemies()), None)

    def battle_over(self, battle) -> None:
        """Called by the battle screen before it resumes this floor."""
        self.enemies = [e for e in self.enemies if e.alive]
        foes = battle.enemies
        names = foes[0].name if len(foes) == 1 else f"{len(foes)} enemies"
        if battle.state == WON:
            self.hud.say(f"Defeated {'the ' if len(foes) == 1 else ''}{names}!"
                         f" +{battle.xp_gained} XP, +{battle.gold_gained} gold")
            for item in battle.loot:
                self.hud.say(f"Found: {item.name}")
            if battle.blueprint:
                self.hud.say(f"Blueprint: {item_by_id(battle.blueprint).name}"
                             " (craft it at an anvil)")
            if any(e.boss for e in foes):
                self.stairs = boss_room(self.dungeon).rect.center
                self.hud.say("Stairs down have appeared!")
                if self.floor == LORE_FLOORS and "epilogue" not in self.player.lore:
                    self.player.lore.append("epilogue")
                    save_player(self.player)
                    self.story = ("story", {"title": EPILOGUE_TITLE,
                                            "heading": "Brackmoor",
                                            "pages": list(EPILOGUE),
                                            "return_to": self})
            self.check_levels = True
        elif battle.state == FLED:
            # Back out through the nearest door; the room stays hostile.
            room = self.dungeon.get_room_at(self.cell())
            if room is not None:
                out = self.dungeon.door_outside(room, self.cell())
                self.x, self.y = self._centre(out)
                self._mark_visited()
                self.hud.say(f"You escaped from {'the ' if len(foes) == 1 else ''}{names}.")
        self.save_run()

    def _open_chests(self):
        for chest in self.chests:
            cell, opened = chest
            if not opened and self._near(*self._centre(cell)):
                chest[1] = True
                audio.play("chest")
                self.fx.burst(*self._centre(cell), (240, 200, 90), count=22)
                item = roll_loot(self.dungeon.rng,
                                 max_level=min(4, self.floor + 1))
                if self.player.can_carry(item):
                    self.player.inventory.append(item)
                    self.hud.say(f"Chest: {item.name} ({item.rarity})")
                else:
                    self.hud.say(f"Chest: {item.name}, too heavy to carry")
                found = self._find_blueprint(BLUEPRINT_CHEST_CHANCE)
                if found:
                    self.hud.say(f"Chest: a blueprint for the {found}!")

    def _read_lore(self):
        """Pick up the writing the hero walks onto: it goes into the
        journal (saved at once) and opens in the story reader."""
        for i, (entry, cell) in enumerate(self.lore):
            if self._near(*self._centre(cell)):
                del self.lore[i]
                self.player.lore.append(entry.id)
                save_player(self.player)
                self.moving = False
                audio.play("chest", volume=0.6)
                self.fx.burst(*self._centre(cell), (226, 210, 172), count=16)
                self.hud.say(f"Found: {entry.title} (reread it in the Base's Journal)")
                return ("story", {"title": entry.title, "pages": list(entry.pages),
                                  "heading": f"Floor {entry.floor}: {CHAPTERS[entry.floor]}",
                                  "return_to": self})
        return None

    # -- special rooms -------------------------------------------------------
    def keeper_near(self):
        """The kind of special room whose keeper the hero stands next to
        (None if nobody is in reach)."""
        for kind, cell in self.keepers.items():
            x, y = self._centre(cell)
            if abs(self.x - x) <= TALK and abs(self.y - y) <= TALK:
                return kind
        return None

    def interact(self):
        """E: talk to the keeper in reach; returns a transition or None."""
        kind = self.keeper_near()
        if kind is not None:
            self.moving = False
            audio.play("click")
        if kind == "shop":
            return ("shop", {"player": self.player, "stock": self.shop_stock,
                             "sold": self.shop_sold, "return_to": self})
        if kind == "anvil":
            return ("forge", {"player": self.player, "return_to": self})
        return None

    def _find_blueprint(self, chance):
        """Maybe learn a new weapon or armour blueprint (``chance`` %); returns its
        weapon name or None."""
        if self.dungeon.rng.uniform(0, 100) >= chance:
            return None
        base = roll_blueprint(self.dungeon.rng, self.player.blueprints)
        if base is None:
            return None
        self.player.blueprints.append(base)
        return item_by_id(base).name

    # -- attacking props -----------------------------------------------------
    def attack(self) -> None:
        """Swing the weapon (melee, or bare fists) at the prop in front,
        or shoot an arrow / magic bolt (ranged / magic weapons) the way
        the hero faces.  Does nothing while the last attack cools down."""
        if self.attack_cd > 0:
            return
        self.attack_cd = ATTACK_COOLDOWN
        self.swing_t = SWING_TIME
        weapon = self.player.equipment.get("weapon")
        kind = weapon_type(weapon)
        self.swing_melee = kind == "melee"
        dx, dy = FACING_STEP[self.facing]
        if kind == "melee":
            prop = self._prop_near(self.x + dx * REACH, self.y + dy * REACH)
            if prop is None:
                audio.play("miss", volume=0.6)
            else:
                self._hit_prop(prop)
            return
        audio.play("shoot" if kind == "ranged" else "magic", volume=0.7)
        color = SHOT_COLORS["ranged"] if kind == "ranged" else SHOT_COLORS.get(
            weapon.effect, SHOT_COLORS["magic"])
        self.shots.append([self.x + dx * 12, self.y + dy * 12, dx, dy, 0.0, color])

    def _prop_near(self, x, y):
        """The standing prop under a HITBOX-sized box centred on (x, y),
        the one under the centre first."""
        half = HITBOX / 2
        for px, py in ((x, y), (x - half, y - half), (x + half - 1, y - half),
                       (x - half, y + half - 1), (x + half - 1, y + half - 1)):
            prop = self.prop_at.get((int(px // TILE_SIZE), int(py // TILE_SIZE)))
            if prop is not None and prop.solid:
                return prop
        return None

    def _update_shots(self, dt) -> None:
        """Fly the shots in small steps (so none skips a tile); a shot
        stops at a wall, an enemy, a prop (which takes the hit) or the
        end of its range."""
        keep = []
        enemy_cells = {cell_of(e) for e in self.enemies}
        for x, y, dx, dy, dist, color in self.shots:
            travel = SHOT_SPEED * dt
            n = int(travel // 8) + 1
            alive = True
            for _ in range(n):
                x, y, dist = x + dx * travel / n, y + dy * travel / n, dist + travel / n
                cell = (int(x // TILE_SIZE), int(y // TILE_SIZE))
                prop = self.prop_at.get(cell)
                if prop is not None and prop.solid:
                    self._hit_prop(prop)
                    alive = False
                    break
                if (not self.dungeon.is_walkable(cell) or cell in enemy_cells
                        or dist >= SHOT_RANGE):
                    self.fx.burst(x, y, color, count=6, speed=60, life=0.25, size=2)
                    alive = False
                    break
            if alive:
                keep.append([x, y, dx, dy, dist, color])
        self.shots = keep

    def _hit_prop(self, prop) -> None:
        """One hit on ``prop``; when it breaks, its materials go into the
        hero's pouch."""
        x, y = self._centre(prop.cell)
        color = PROP_COLORS[prop.kind]
        if not prop.hit():
            audio.play("strike", volume=0.6)
            self.fx.burst(x, y, color, count=6, speed=70, life=0.3, size=2)
            return
        audio.play(BREAK_SOUND[prop.kind], volume=0.8)
        self.fx.burst(x, y, color, count=16, speed=110, life=0.5, size=3)
        got = salvage(prop, self.dungeon.rng)
        for mat, n in got.items():
            self.player.materials[mat] += n
        found = [f"+{n} {mat}" for mat, n in got.items()]
        rng = self.dungeon.rng
        if rng.uniform(0, 100) < PROP_GOLD_CHANCE:
            coins = rng.randint(*PROP_GOLD) * self.floor
            self.player.gold += coins
            found.append(f"+{coins} gold")
            self.fx.burst(x, y, (240, 200, 90), count=8, speed=80, life=0.4, size=2)
        if rng.uniform(0, 100) < PROP_JUNK_CHANCE:
            junk = roll_junk(rng, self.floor)
            if self.player.can_carry(junk):
                self.player.inventory.append(junk)
                found.append(junk.name)
            else:
                found.append(f"{junk.name} (too heavy)")
        bp = self._find_blueprint(BLUEPRINT_PROP_CHANCE)
        if bp:
            found.append(f"{bp} blueprint")
        what = ", ".join(found) or "nothing useful"
        self.hud.say(f"{prop.kind.capitalize()} smashed: {what}")

    # -- Screen hooks ----------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            save_player(self.player)
            self.save_run()
            return QUIT
        if settings.pressed(event, "interact"):
            return self.interact()
        if settings.pressed(event, "attack"):
            self.attack()
            return None
        if settings.pressed(event, "inventory"):
            return ("inventory", {"player": self.player, "return_to": self})
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            save_player(self.player)
            self.save_run()
            return ("base", {"player": self.player})
        return None

    def suspend(self):
        """The app is going to the background (a phone may close it
        there): keep the hero and the run."""
        save_player(self.player)
        self.save_run()

    def step(self, dx, dy, dt):
        """One frame of play with the given input; returns a transition
        request or None.  ``handle_update`` feeds it the keyboard; tests
        call it directly."""
        self.anim_t += dt
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.swing_t = max(0.0, self.swing_t - dt)
        self.banner_t = max(0.0, self.banner_t - dt)
        self.fx.update(dt)
        self.hud.update(dt)
        if self.check_levels:
            self.check_levels = False
            if pending_levels(self.player) > 0:
                return ("level_up", {"player": self.player, "return_to": self})
        if self.story is not None:
            story, self.story = self.story, None
            return story
        self.move(dx, dy, dt)
        self._update_shots(dt)
        self._open_chests()
        story = self._read_lore()
        if story is not None:
            return story
        foes = self.room_enemies()
        if foes:
            self.moving = False
            self.shots.clear()
            audio.play("encounter")
            return ("battle", {"player": self.player, "enemy": foes[0],
                               "enemies": foes, "dungeon": self})
        if self.stairs is not None and self.cell() == self.stairs:
            save_player(self.player)
            audio.play("stairs")
            return ("dungeon", {"player": self.player, "floor": self.floor + 1})
        return None

    def handle_update(self, dt):
        keys = pygame.key.get_pressed()
        dx = settings.held(keys, "right") - settings.held(keys, "left")
        dy = settings.held(keys, "down") - settings.held(keys, "up")
        return self.step(dx, dy, dt)

    # -- drawing ---------------------------------------------------------
    def draw(self, surface):
        surface.fill((0, 0, 0))
        ox, oy = self.camera()
        overrides = {self.stairs: SEWER_MANHOLE} if self.stairs else None
        self.dungeon.render(surface, (ox, oy), seen=self.seen,
                            overrides=overrides, visible=self.visible)

        for cell, opened in self.chests:
            if cell in self.seen:
                x, y = self._centre(cell)
                img = self.chest_frames[1 if opened else 0]
                surface.blit(img, img.get_rect(center=(x - ox, y - oy)))

        glow = 0.5 + 0.5 * math.sin(self.anim_t * 3)
        for entry, cell in self.lore:
            if cell not in self.visible:            # only while in sight
                continue
            x, y = self._centre(cell)
            halo = _lore_halo(int(60 + 70 * glow))
            surface.blit(halo, halo.get_rect(center=(x - ox, y - oy)))
            img = _lore_sprite(entry.kind)
            surface.blit(img, img.get_rect(center=(x - ox, y - oy - 2 * glow)))

        for prop in self.props:
            if prop.cell not in self.seen:
                continue
            col = PROP_KINDS.index(prop.kind)
            img = self.prop_frames[col + (len(PROP_KINDS) if prop.broken else 0)]
            pos = (prop.cell[0] * TILE_SIZE - ox, prop.cell[1] * TILE_SIZE - oy)
            surface.blit(img, pos)
            if prop.cell not in self.visible:       # remembered, not in sight
                surface.blit(self._prop_shade, pos)

        for kind, cell in self.keepers.items():
            if cell not in self.seen:
                continue
            x, y = self._centre(cell)
            rug = pygame.Rect(0, 0, 2 * TILE_SIZE + 8, TILE_SIZE)
            rug.center = (x - ox, y - oy + 8)
            if kind == "shop":                      # the merchant's rug
                pygame.draw.rect(surface, (78, 34, 34), rug, border_radius=4)
                pygame.draw.rect(surface, (150, 116, 56), rug, 2, border_radius=4)
            else:                                   # soot around the forge
                pygame.draw.ellipse(surface, (26, 24, 22), rug)
            img = self.keeper_frames[kind][int(self.anim_t / (0.5 if kind == "shop" else 0.15)) % 2]
            surface.blit(img, img.get_rect(center=(x - ox, y - oy)))
            if cell not in self.visible:
                surface.blit(self._prop_shade, (cell[0] * TILE_SIZE - ox, cell[1] * TILE_SIZE - oy))

        for i, e in enumerate(self.enemies):
            if cell_of(e) not in self.visible:      # walls hide enemies
                continue
            # Each enemy breathes on its own beat (offset by its index).
            t = self.anim_t + i * 0.37
            img = self.enemy_frames[e.type.sprite][ENEMY_IDLE[int(t / 0.4) % 2]]
            size = 48 if e.boss else 32
            if e.boss:
                img = pygame.transform.scale(img, (48, 48))
            sx, sy = e.x - ox, e.y - oy
            surface.blit(_shadow(size), _shadow(size).get_rect(
                center=(sx, sy + size * 0.38)))
            surface.blit(img, img.get_rect(center=(sx, sy)))

        for x, y, dx, dy, _, color in self.shots:
            sx, sy = x - ox, y - oy
            if color == SHOT_COLORS["ranged"]:          # an arrow
                pygame.draw.line(surface, color, (sx - dx * 9, sy - dy * 9), (sx, sy), 2)
                pygame.draw.circle(surface, (200, 200, 210), (int(sx), int(sy)), 2)
            else:                                       # a magic bolt
                pygame.draw.circle(surface, color, (int(sx), int(sy)), 5)
                pygame.draw.circle(surface, (255, 255, 255), (int(sx), int(sy)), 2)

        self.fx.draw(surface, (ox, oy))

        if self.swing_t > 0:
            col = HERO_ATTACK_COLS[0 if self.swing_t > SWING_TIME / 2 else 1]
        elif self.moving:
            col = HERO_WALK_COLS[self.walk_frame()]
        else:
            col = HERO_IDLE_COLS[int(self.anim_t / FRAME_TIME) % len(HERO_IDLE_COLS)]
        frame = self.hero_frames()[self.facing * HERO_COLS + col]
        surface.blit(frame, frame.get_rect(
            center=(int(self.x) - ox, int(self.y) - oy)))
        if self.swing_t > SWING_TIME / 3 and self.swing_melee:
            a0, a1 = SWING_ARC[self.facing]
            box = pygame.Rect(0, 0, 2 * REACH, 2 * REACH)
            box.center = (int(self.x) - ox, int(self.y) - oy)
            pygame.draw.arc(surface, (235, 235, 240), box, a0, a1, 3)

        light = _light_mask()
        surface.blit(light, light.get_rect(center=(int(self.x) - ox, int(self.y) - oy)))
        near = self.keeper_near()
        if near:
            x, y = self._centre(self.keepers[near])
            use = settings.action_label("interact")
            tip = font(20).render(f"{use}: trade" if near == "shop"
                                  else f"{use}: forge", True, (235, 200, 90))
            surface.blit(tip, tip.get_rect(midbottom=(x - ox, y - oy - 18)))

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
        mm_pos = (SCREEN_WIDTH - mm_w - 10, 10)
        self.dungeon.draw_minimap(surface, self.visited, mm_pos,
                                  self.cell(), scale=MINIMAP_SCALE)
        for kind, room in self.special.items():   # mark the shop and forge
            if room in self.visited:
                cx, cy = room.rect.center
                pygame.draw.rect(surface, MINIMAP_MARK[kind],
                                 (mm_pos[0] + cx * MINIMAP_SCALE - 2,
                                  mm_pos[1] + cy * MINIMAP_SCALE - 2, 5, 5))
        hint = font(18).render(controls_hint(), True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 12, SCREEN_HEIGHT - 10)))
