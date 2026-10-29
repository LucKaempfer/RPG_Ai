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
from pygame_rpg.gui.screen import QUIT

hero = Player(name="Walker")
ds = build_screen("dungeon", screen, {"player": hero, "seed": 3})
ok(isinstance(ds, DungeonScreen) and ds._fits(ds.x, ds.y), "spawn inside the first room")
ok(ds.banner_t > 0, "floor banner on arrival")
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
S.delete_run(hero.name)
base = BaseScreen(screen, hero)
r = base.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                         pos=base.btn_adventure.rect.center))
ok(r == ("dungeon", {"player": hero}), "Adventure opens the dungeon")
ok((tmp / "Walker.json").exists(), "saved on entering")
ds = DungeonScreen(screen, hero, seed=1)
r = ds.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
ok(r == ("base", {"player": hero}), "Esc returns to the Base")
base.draw(screen)

# --- Enemies ---
from pygame_rpg import enemies as E, combat as C
from pygame_rpg.gui.battle_screen import BattleScreen
from pygame_rpg.gui.level_up_screen import LevelUpScreen
for seed in range(20):
    d = Dungeon(); d.generate(seed)
    es = E.place_enemies(d, 1)
    bosses = [e for e in es if e.boss]
    lair = E.boss_room(d)
    ok(len(bosses) == 1 and lair.contains((int(bosses[0].x // TILE_SIZE), int(bosses[0].y // TILE_SIZE))),
       f"seed {seed}: one boss in the lair")
    cells = [(int(e.x // TILE_SIZE), int(e.y // TILE_SIZE)) for e in es]
    ok(len(set(cells)) == len(cells) and all(d.is_walkable(c) for c in cells), f"seed {seed}: enemies on free floor")
    ok(not any(d.rooms[0].contains(c) for c in cells), f"seed {seed}: entrance empty")
d1, d2 = Dungeon(), Dungeon(); d1.generate(9); d2.generate(9)
ok([(e.name, e.x, e.y) for e in E.place_enemies(d1, 2)] == [(e.name, e.x, e.y) for e in E.place_enemies(d2, 2)],
   "placement follows the seed")
s1, s3 = E.make_enemy(E.ENEMY_TYPES["slime"], 1), E.make_enemy(E.ENEMY_TYPES["slime"], 3)
ok(s3.max_hp > s1.max_hp and s3.attack == s1.attack + 2 and s3.xp > s1.xp, "floor scaling")
ok(all(t.min_floor <= 1 for t in E.ENEMY_TYPES.values() if t.name in ("Slime", "Bat", "Rat")), "floor-1 pool")

# --- Combat rules ---
def kit(*ids, lvl=1):
    p = Player(name="K", lvl=lvl)
    for i in ids:
        it = I.item_by_id(i); p.inventory.append(it)
        if it.slot:
            p.equip(it)
    return p
ok(C.weapon_type(None) == "melee" and C.weapon_type(I.item_by_id("bow")) == "ranged"
   and C.weapon_type(I.item_by_id("fiery_wand")) == "magic" and C.weapon_type(I.item_by_id("dagger")) == "melee",
   "weapon types")
p = kit("sword", "fireball", "heal", "shield")
e = E.make_enemy(E.ENEMY_TYPES["skeleton"], 1)
b = C.Battle(p, e, random.Random(1))
hp0 = e.hp; b.attack(); ok(e.hp < hp0 and p.current_hp < p.max_hp, "attack + enemy reply")
fb = p.equipment["ability1"]
mp0 = p.current_mp; b.cast(fb)
ok(p.current_mp == mp0 - fb.mp_cost and not b.can_cast(fb), "cast spends MP, cooldown blocks")
e.hp = e.max_hp = 999; p.current_hp = p.max_hp
b.attack(); ok(b.can_cast(fb), "ready again 2 turns after the cast (cooldown 2)")
p2 = kit("sword", "heal", "shield")
b2 = C.Battle(p2, E.make_enemy(E.ENEMY_TYPES["slime"], 1), random.Random(2))
ok(not b2.can_cast(p2.equipment["ability1"]), "heal blocked at full HP")
b2.cast(p2.equipment["ability2"]); ok(b2.guard == 3, "shield guards")
p3 = kit("sword"); bomb = I.item_by_id("fire_bomb"); mana = I.item_by_id("mana_potion"); p3.inventory += [bomb, mana]
e3 = E.make_enemy(E.ENEMY_TYPES["skeleton"], 1); b3 = C.Battle(p3, e3, random.Random(3))
ok(bomb in b3.battle_items() and not b3.can_use(mana), "bombs usable, mana blocked at full MP")
hp0 = e3.hp; b3.use_item(bomb)
ok(e3.hp <= hp0 - bomb.damage and bomb not in p3.inventory, "bomb: flat damage, charge used")
boss = E.make_enemy(E.BOSS_TYPE, 1, boss=True)
b4 = C.Battle(kit("sword"), boss, random.Random(4)); b4.run()
ok(b4.state == C.ONGOING and "can't run" in b4.log[-1], "no running from the boss")
fled = 0
for sd in range(30):
    bb = C.Battle(kit("sword"), E.make_enemy(E.ENEMY_TYPES["slime"], 1), random.Random(sd)); bb.run()
    fled += bb.state == C.FLED
ok(10 < fled < 30, "running works sometimes")
# Stun skips the enemy's turn.
p5 = kit("sword"); e5 = E.make_enemy(E.ENEMY_TYPES["skeleton"], 1); e5.hp = 999; e5.max_hp = 999
b5 = C.Battle(p5, e5, random.Random(5)); e5.statuses["stun"] = 1; b5.attack()
ok(p5.current_hp == p5.max_hp and "can't move" in " ".join(b5.log), "stun skips a turn")
# Wards: poison ward IV makes the hero immune to the slime's poison.
hits = {}
for ward in (None, "poison_ward_4"):
    n = 0
    for sd in range(60):
        pw = kit("sword", lvl=4) if ward is None else kit("sword", ward, lvl=4)
        pw.ap = 1
        sl = E.make_enemy(E.ENEMY_TYPES["slime"], 1); sl.hp = sl.max_hp = 999
        bw = C.Battle(pw, sl, random.Random(sd))
        for _ in range(3):
            bw.attack()
        n += "poison" in bw.statuses or any("You take" in l and "poison" in l for l in bw.log)
    hits[ward] = n
ok(hits[None] > 10 and hits["poison_ward_4"] == 0, "ward blocks its ailment")
# Winning: XP (+ trinket bonus), recovery, loot respects weight.
p6 = kit("sword", "wisdom_amulet", lvl=2); p6.current_hp = 50
e6 = E.make_enemy(E.ENEMY_TYPES["bat"], 1); e6.hp = 1
b6 = C.Battle(p6, e6, random.Random(6)); b6.attack()
ok(b6.state == C.WON and b6.xp_gained == round(18 * 1.1) and p6.xp == b6.xp_gained, "XP with bonus")
ok(p6.current_hp == 50 + p6.max_hp // 10, "post-fight recovery")
p7 = kit("sword"); p7.inventory += [I.item_by_id("chainmail_4")] * 10   # 50 kg: full
e7 = E.make_enemy(E.BOSS_TYPE, 1, boss=True); e7.hp = 1
b7 = C.Battle(p7, e7, random.Random(7)); n_inv = len(p7.inventory); b7.attack()
ok(b7.state == C.WON and len(p7.inventory) == n_inv and "too heavy" in b7.log[-1], "loot respects weight")
p8 = kit("sword"); e8 = E.make_enemy(E.BOSS_TYPE, 1, boss=True); e8.hp = e8.max_hp = 999
b8 = C.Battle(p8, e8, random.Random(8))
for _ in range(100):
    b8.attack()
ok(b8.state == C.LOST and p8.current_hp == 0, "hero can lose")

# --- Encounter loop through the screens ---
def press(scr, key):
    return scr.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
def walk_to(ds, tx, ty, limit=4000):
    for _ in range(limit):
        ddx, ddy = tx - ds.x, ty - ds.y
        r = ds.step((ddx > 2) - (ddx < -2), (ddy > 2) - (ddy < -2), 1 / 120)
        if r is not None:
            return r
    return None

hero = kit("sword_2", "fireball", lvl=2); hero.name = "Runner"
ds = DungeonScreen(screen, hero, seed=3)
target = next(e for e in ds.enemies if not e.boss)
# Teleport next to it on its row so the last steps bump into it.
ds.x, ds.y = target.x - 2 * TILE_SIZE, target.y
if not ds._fits(ds.x, ds.y):
    ds.x, ds.y = target.x, target.y - 2 * TILE_SIZE
r = walk_to(ds, target.x, target.y)
ok(r is not None and r[0] == "battle"
   and E.boss_room(ds.dungeon) is not ds.dungeon.get_room_at(E.cell_of(r[1]["enemy"]))
   and ds.dungeon.get_room_at(E.cell_of(r[1]["enemy"])) is ds.dungeon.get_room_at(E.cell_of(target)),
   "being in an enemy's room starts a battle")
target = r[1]["enemy"]
bs = build_screen("battle", screen, r[1]); ok(isinstance(bs, BattleScreen), "battle screen built")
bs.draw(screen)
hero.xp = hero.max_xp - 1                     # next win levels up
for _ in range(60):
    if bs.battle.state != C.ONGOING:
        break
    target.hp = min(target.hp, 1)
    res = press(bs, pygame.K_RETURN)          # focus 0 = Attack
ok(bs.battle.state == C.WON, "won through the menu")
ok(any(t.startswith("-") for t, *_ in bs.pops), "damage numbers pop up")
bs.handle_update(5.0); ok(not bs.pops and bs.hurt_t == 0, "pops and flashes fade")
bs.draw(screen)
res = press(bs, pygame.K_RETURN)              # Continue
ok(res[0] == "resume" and res[1]["screen"] is ds,
   "Continue resumes the same floor")
ok(target not in ds.enemies, "beaten enemy removed")
r = ds.step(0, 0, 1 / 60)
ok(r is not None and r[0] == "level_up" and r[1]["return_to"] is ds, "mid-run level-up")
lu = build_screen(r[0], screen, r[1]); lu.draw(screen)
click_res = lu.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                               pos=lu.stat_buttons["ap"].rect.center))
ok(click_res == ("resume", {"screen": ds}) and hero.lvl == 3, "level banked, back to the floor")
r = ds.step(0, 0, 1 / 60); ok(r is None or r[0] != "level_up", "no second level-up prompt")

# Room entry: stepping through a door into a room with enemies starts the
# fight at once (no walking around them); fleeing puts the hero outside.
other = next((e for e in ds.enemies if not e.boss), None)
if other is not None:
    room = ds.dungeon.get_room_at(E.cell_of(other))
    door = room.doors[0]
    out = ds.dungeon.door_outside(room, door)
    ds.x, ds.y = ds._centre(out)
    ok(ds.step(0, 0, 1 / 60) is None, "outside the room: no fight")
    r = walk_to(ds, *ds._centre(door))
    ok(r is not None and r[0] == "battle" and ds.dungeon.get_room_at(ds.cell()) is room
       and r[1]["enemy"] in ds.enemies and room.contains(E.cell_of(r[1]["enemy"])),
       "entering the room starts the fight")
    foe = r[1]["enemy"]
    fb_ = BattleScreen(screen, hero, foe, ds, rng=random.Random(0))
    while fb_.battle.state == C.ONGOING:
        fb_.battle.run(); foe.hp = foe.max_hp; hero.current_hp = hero.max_hp
    ok(fb_.battle.state == C.FLED, "fled")
    fb_._leave()
    ok(ds.dungeon.get_room_at(ds.cell()) is None and ds.step(0, 0, 1 / 60) is None,
       "fleeing puts the hero back outside")
    r = walk_to(ds, *ds._centre(door))
    ok(r is not None and r[0] == "battle", "the room stays hostile")

# Chest.
cell, _ = ds.chests[0]
n_inv = len(hero.inventory)
ds.x, ds.y = ds._centre(cell)
ds.step(0, 0, 1 / 60)
ok(ds.chests[0][1] and len(hero.inventory) == n_inv + 1, "chest opened, loot in backpack")

# Boss -> stairs -> floor 2.
bossy = next(e for e in ds.enemies if e.boss)
ds.x, ds.y = bossy.x - TILE_SIZE, bossy.y
r = walk_to(ds, bossy.x, bossy.y)
ok(r is not None and r[1]["enemy"] is bossy, "boss fight")
bb = BattleScreen(screen, hero, bossy, ds, rng=random.Random(1))
bossy.hp = 1; hero.current_hp = hero.max_hp
bb.battle.attack()
ok(bb.battle.state == C.WON, "boss beaten")
bb._leave()
ok(ds.stairs == E.boss_room(ds.dungeon).rect.center, "stairs appear")
ds.draw(screen)
ds.x, ds.y = ds._centre(ds.stairs)
ds.check_levels = False
r = ds.step(0, 0, 1 / 60)
ok(r == ("dungeon", {"player": hero, "floor": 2}), "stairs lead down")
f2 = build_screen(r[0], screen, r[1])
ok(f2.floor == 2 and all(e.floor == 2 for e in f2.enemies), "floor 2 enemies scale")
f2.draw(screen)

# Fog of war: an unseen far corner stays black.
f2.draw(screen)
far = max(f2.dungeon.rooms, key=lambda rm: abs(rm.rect.centerx - f2.x / TILE_SIZE) + abs(rm.rect.centery - f2.y / TILE_SIZE))
ok(far.rect.center not in f2.seen, "far room unseen at start")

# Defeat -> Base, rested.
loser = kit("sword"); loser.name = "Loser"
dl = DungeonScreen(screen, loser, seed=5)
bl = BattleScreen(screen, loser, next(e for e in dl.enemies if e.boss), dl, rng=random.Random(2))
bl.enemy.hp = bl.enemy.max_hp = 999
for _ in range(200):
    if bl.battle.state != C.ONGOING:
        break
    bl.battle.attack()
ok(bl.battle.state == C.LOST, "defeat")
bl._build_buttons(); bl.draw(screen)
r = press(bl, pygame.K_RETURN)
ok(r == ("base", {"player": loser}) and loser.current_hp == loser.max_hp, "back to the Base, rested")
ok(S.load_run("Loser") is None, "defeat ends the run")

# --- Run saves (M5) ---
runner = kit("sword_2", lvl=2); runner.name = "Saver"
d1 = DungeonScreen(screen, runner, seed=11)
ok(S.load_run("Saver")["seed"] == 11 and S.load_run("Saver")["floor"] == 1, "run saved on entering a floor")
victim = next(e for e in d1.enemies if not e.boss)
bt = BattleScreen(screen, runner, victim, d1, rng=random.Random(3))
victim.hp = 1; bt.battle.attack(); bt._leave()
d1.chests[0][1] = True
d1.stairs = E.boss_room(d1.dungeon).rect.center
d1.x, d1.y = victim.x, victim.y           # where the beaten enemy stood
d1._mark_visited()
runner.current_hp = 33
r = press(d1, pygame.K_ESCAPE)
ok(r == ("base", {"player": runner}) and runner.current_hp == 33, "Esc keeps the run and the HP")
saved = S.load_run("Saver")
import json; json.dumps(saved)
ok(saved["beaten"] and saved["stairs"] and saved["chests"][0], "beaten enemy, stairs, chest recorded")

hb = BaseScreen(screen, S.load_player("Saver"))
ok(hb.btn_adventure.label == "Continue (Floor 1)" and hb.btn_new_run in hb._active_buttons(),
   "Base offers Continue + New Adventure")
hb.draw(screen)
r = hb.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=hb.btn_adventure.rect.center))
ok(r[0] == "dungeon" and r[1]["run"] == saved, "Continue passes the run")
d2 = build_screen(r[0], screen, r[1])
ok(d2.seed == 11 and d2.floor == 1 and (d2.x, d2.y) == (d1.x, d1.y), "same floor, same spot")
vi = d1.all_enemies.index(victim)
ok(len(d2.enemies) == len(d1.enemies) and not d2.all_enemies[vi].alive
   and all(e.alive for e in d2.enemies), "beaten enemy stays beaten")
ok([o for _, o in d2.chests] == [o for _, o in d1.chests] and d2.stairs == d1.stairs, "chests + stairs restored")
ok(d2.seen >= d1.seen and len(d2.visited) == len(d1.visited)
   and d2.dungeon.visited_corridors == d1.dungeon.visited_corridors, "fog + minimap restored")
ok(d2.player.current_hp == 33, "HP carried over")
d2.draw(screen)
r = d2.step(0, 0, 1 / 60)
ok((r is None) == (d1.room_enemy() is None), "on load a fight starts only if the room still has enemies")

hb = BaseScreen(screen, d2.player)
r = hb.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=hb.btn_new_run.rect.center))
ok(r == ("dungeon", {"player": d2.player}) and S.load_run("Saver") is None
   and d2.player.current_hp == d2.player.max_hp, "New Adventure drops the run and rests")
d3 = build_screen(r[0], screen, r[1])
ok(d3.floor == 1 and S.load_run("Saver")["seed"] == d3.seed, "new run saved")
# Stairs save the next floor.
d3.enemies = [e for e in d3.enemies if not e.boss]
d3.stairs = E.boss_room(d3.dungeon).rect.center
d3.x, d3.y = d3._centre(d3.stairs)
r = d3.step(0, 0, 1 / 60)
d4 = build_screen(r[0], screen, r[1])
ok(S.load_run("Saver")["floor"] == 2 and S.load_run("Saver")["seed"] == d4.seed, "next floor saved")
# Window close saves too; a broken file means no run.
ok(d4.handle_event(pygame.event.Event(pygame.QUIT)) is QUIT and S.load_run("Saver")["floor"] == 2, "quit saves the run")
(tmp / "runs" / "Saver.json").write_text("{broken")
ok(S.load_run("Saver") is None and BaseScreen(screen, d4.player).btn_adventure.label == "Adventure",
   "broken run file is ignored")
ok(S.list_players().count("Saver") == 1 and "runs" not in S.list_players(), "runs don't show as heroes")
S.delete_player("Saver"); ok(not (tmp / "runs" / "Saver.json").exists(), "deleting a hero deletes its run")

print(f"m4 OK ({checks} checks)")
