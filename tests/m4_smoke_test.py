"""M4 headless smoke test: dungeon generation + dungeon screen.
Run from the repo root:  python tests/m4_smoke_test.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import os, random, tempfile
from collections import deque
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame
from pygame_rpg import savegame as S, items as I
from pygame_rpg.player import Player
from pygame_rpg.dungeon import Dungeon, TILE_SIZE

checks = 0
def ok(cond, msg):
    global checks
    assert cond, msg
    checks += 1

tmp = pathlib.Path(tempfile.mkdtemp()); S.SAVE_ROOT = tmp; S.INDEX_FILE = tmp / "index.json"
pygame.init(); screen = pygame.display.set_mode((800, 600))


def reachable(d, start):
    """Walkable cells reachable from ``start`` (4-neighbour flood fill)."""
    seen, todo = {start}, deque([start])
    while todo:
        x, y = todo.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and d.is_walkable(n):
                seen.add(n); todo.append(n)
    return seen


def path(d, start, goal):
    """Shortest 4-neighbour cell path start -> goal (BFS)."""
    prev, todo = {start: None}, deque([start])
    while todo:
        c = todo.popleft()
        if c == goal:
            break
        x, y = c
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in prev and d.is_walkable(n):
                prev[n] = c; todo.append(n)
    out, c = [], goal
    while c is not None:
        out.append(c); c = prev[c]
    return out[::-1]


# --- Generation ---
state = random.getstate()
for seed in range(40):
    d = Dungeon(); d.generate(seed)
    ok(len(d.rooms) >= 5, f"seed {seed}: rooms")
    ok(all(not a.rect.colliderect(b.rect) for i, a in enumerate(d.rooms) for b in d.rooms[i + 1:]),
       f"seed {seed}: no overlap")
    ok(all(d.get_room_at(c) is r for r in d.rooms
           for c in [(x, y) for x in range(r.rect.left, r.rect.right) for y in range(r.rect.top, r.rect.bottom)]),
       f"seed {seed}: corridors keep room cells")
    ok(d.door_tiles and all(d.get_room_at(c) is not None and any(
           n in d.room_map and d.room_map[n] is None
           for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)))
           for c in d.door_tiles), f"seed {seed}: doors open onto corridors")
    start = d.rooms[0].rect.center
    seen = reachable(d, start)
    ok(all(r.rect.center in seen for r in d.rooms), f"seed {seed}: every room reachable")
ok(random.getstate() == state, "generation leaves global random alone")
a, b = Dungeon(), Dungeon(); a.generate(7); b.generate(7)
ok([r.rect for r in a.rooms] == [r.rect for r in b.rooms] and a.room_map.keys() == b.room_map.keys(),
   "same seed, same floor")

# --- Dungeon screen ---
from pygame_rpg.main import build_screen
from pygame_rpg.gui.dungeon_screen import DungeonScreen, WALK_SPEED
from pygame_rpg.gui.base_screen import BaseScreen

hero = Player(name="Walker")
ds = build_screen("dungeon", screen, {"player": hero, "seed": 3})
ok(isinstance(ds, DungeonScreen) and ds._fits(ds.x, ds.y), "spawn inside the first room")
ok(ds.visited == [ds.dungeon.rooms[0]], "first room visited")
ds.draw(screen); ds.handle_update(0.016)

# Walls stop the hero: walking left for 10 s ends against a wall, still on floor.
x0 = ds.x
for _ in range(600):
    ds.move(-1, 0, 1 / 60)
ok(ds._fits(ds.x, ds.y) and ds.x < x0, "walked left until a wall")
x1 = ds.x
ds.move(-1, 0, 1 / 60)
ok(ds.x == x1, "wall blocks further movement")

# Random walking never leaves the floor.
rng = random.Random(5)
for _ in range(3000):
    ds.move(rng.choice((-1, 0, 1)), rng.choice((-1, 0, 1)), 1 / 60)
    assert ds._fits(ds.x, ds.y)
ok(True, "random walk stays on floor")

# Follow a BFS path to every room: corridors are passable with the hitbox.
for seed in (3, 11, 23):
    ds = DungeonScreen(screen, Player(name="P"), seed=seed)
    for room in ds.dungeon.rooms[1:]:
        cells = path(ds.dungeon, ds.cell(), room.rect.center)
        for cx, cy in cells[1:]:
            tx, ty = cx * TILE_SIZE + TILE_SIZE / 2, cy * TILE_SIZE + TILE_SIZE / 2
            for _ in range(120):
                ddx, ddy = tx - ds.x, ty - ds.y
                if abs(ddx) < 2 and abs(ddy) < 2:
                    break
                ds.move((ddx > 1) - (ddx < -1), (ddy > 1) - (ddy < -1), 1 / 120)
        ok(ds.dungeon.get_room_at(ds.cell()) is room, f"seed {seed}: walked to room {room.id}")
    ok(len(ds.visited) == len(ds.dungeon.rooms), f"seed {seed}: all rooms visited")
    ok(len(ds.dungeon.visited_corridors) > 0, f"seed {seed}: corridors on minimap")
    ds.draw(screen)

# Speed trinket makes the hero faster.
fast = Player(name="Fast", lvl=4)
scarf = I.item_by_id("haste_scarf_4"); fast.inventory.append(scarf); fast.equip(scarf)
fs = DungeonScreen(screen, fast, seed=3)
ok(abs(fs.speed - WALK_SPEED * 1.25) < 1e-9, "speed bonus applies")

# Camera stays on the map.
cx, cy = ds.camera()
ok(0 <= cx and 0 <= cy, "camera clamped")

# Transitions: Base Adventure -> dungeon; Esc -> Base (saved).
base = BaseScreen(screen, hero)
r = base.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                         pos=base.btn_adventure.rect.center))
ok(r == ("dungeon", {"player": hero}), "Adventure opens the dungeon")
ok((tmp / "Walker.json").exists(), "saved on entering")
ds = DungeonScreen(screen, hero, seed=1)
r = ds.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
ok(r == ("base", {"player": hero}), "Esc returns to the Base")
base.draw(screen)
print(f"m4 OK ({checks} checks)")
