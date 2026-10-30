# DEVELOPMENT.md — RPG_Ai Development Guide

> Single source of truth for further development. Replaces the former `Handoff.md` and
> `Plan.md` (both merged here on 23 Oct 2026). Keep this file current at the end of every
> work session: update §0, the status table in §2, and §5 when something changes.

**Goal:** turn the minimal `pygame_rpg/` dungeon crawler plus the text-based `RPG_V3/`
mechanics into one complete 2-D, sprite-based pygame game. Everything up to and including the
Base (lobby), the item system, the dungeon, turn-based combat and saved dungeon runs work in
the GUI; all five milestones are done. What's left is play-testing the balance and real art.

---

## 0. Start Here

**Where we are:** all five milestones (M1 sprites, M3 GUI, M2 items, M4 dungeon + combat,
M5 persistence + polish) are done.
* Dungeon runs are saved (*Continue (Floor N)* / *New Adventure* in the Base).
* The tuning numbers live in `config.py`, and there is a pytest suite (`python -m pytest`).
* Polish: every menu works with the keyboard, each enemy type has its own placeholder shape,
  and the title screen has a drawn logo.
* Effects: damage numbers, hit flash, victory / defeat animations, chest sparks, a level-up
  fanfare and a floor banner.

The full loop: Base → Adventure → walk a fogged floor → bump an enemy → turn-based battle →
XP / loot → level up mid-run → chests → beat the boss → stairs to a harder floor. Esc returns to
the Base with the run kept; defeat ends the run.

**Character customization:** the hero maker has a look stage between the name and the
confirm (skin, hair style incl. helmet / hood, hair colour, tunic colour, with a walking preview
and a Random button). The hero is drawn in code from `Player.look` (`AssetManager.hero_frames`),
so `player/hero_sheet.png` is gone; old saves get the default look.

**Walking animation:** the hero frames are now 10 × 4 (idle 0-1, a six-frame walk 2-7,
attack 8-9). The walk is a real stride (legs scissor or lift, arms swing against them, the body
dips when a foot lands), driven by the distance walked rather than time so the feet never slide;
each footstep plays the splash sound and kicks up a few drops. The hero and enemies cast soft
shadows, and each enemy breathes on its own beat.

**Gear on the hero:** the equipped weapon and armour are drawn on the hero everywhere the
hero shows (dungeon, battle, Base portrait). `assets.gear_of(equipment)` reduces the equipment to
(weapon family, weapon ailment, leather / iron per armour slot), and `hero_frames(look, gear)`
caches one sheet per look + gear: a sword, mace, bow or staff (orb coloured by its element) in the
right hand, an iron helmet or leather cap, chain mail or a leather vest, gloves and boots. The
dungeon looks the frames up each draw, so a change in the inventory or at the anvil shows at once.

**Armour at the anvil:** blueprints now cover the eight armour bases too (Leather Cap … Iron
Boots), so they drop like weapon blueprints and the forge crafts and upgrades armour the same
way. Leather armour costs cloth 2 + bone 1, iron armour iron 2 + stone 1, times the piece's base
weight (torso pieces cost double); upgrades are that × the new level plus 15 gold × the new
level. Equipped armour stays in its slot when upgraded.

**Blueprints and the anvil room:** each floor also has a forge room (second special room,
same rules as the shop) with an anvil; E next to it opens the forge screen
(`gui/forge_screen.py`, rules in `crafting.py`). *Craft* makes the level-1 weapon of any known
blueprint from materials (by family: blade iron 3 + wood 1, blunt iron 2 + wood 2 + stone 1,
ranged wood 3 + cloth 2, magic wood 2 + bone 2 + cloth 1) plus 10 gold. *Upgrade* raises a
carried weapon one tier (`sword` → `sword_2` …, up to 4) for the family's materials × the new
level plus 15 gold × the new level; it needs that weapon's blueprint and the hero's level, and an
equipped weapon stays equipped. Blueprints (`Player.blueprints`, weapon base ids, saved; new and
old heroes know the Sword) drop from the boss always (one the hero doesn't know yet), enemies 10 %,
chests 30 %, smashed props 3 % (`BLUEPRINT_*_CHANCE`). `RUN_VERSION` is 5.

**Shop room:** every floor has one safe room (`special_rooms.py`: own RNG, never the entrance
or the lair; no enemies, chests or props) with a merchant on a rug near the top wall. E next to
them opens the shop screen (`gui/shop_screen.py`, rules in `shop.py`): health potions, rations and
mana potions at the floor's tier never run out, plus four pieces of gear rolled from the seed (up
to floor + 1) that sell out. Prices: gear base × the level's triangle number (weapon 20 / 60 /
120 / 200), consumables 8 × level; the merchant buys junk at its value and anything else at a
quarter of the price. The minimap marks the shop once visited. Run saves keep `shop_sold`;
`RUN_VERSION` went to 4 (the shop changes enemy, chest and prop placement).

**Money and junk:** every won fight pays gold (`ENEMY_GOLD` 3-8 × floor, the boss ×5) and
has a 25 % chance of a piece of junk; smashed props hold coins (30 %, 1-4 × floor) or junk
(12 %). `Player.gold` is saved and shown in the HUD, the inventory and the Base. Junk is a new
item kind (`items.JUNK`, 10 pieces from Rat Tail at 2 gold to Jeweled Buckle at 35, `value` =
what a shop pays, `level` = first floor it drops on); `roll_loot` never returns it
(`LOOT_KINDS`). The catalog has 222 items.

**Smashing props:** Space (or F) in the dungeon swings the weapon at the prop in front (a
white arc, attack frames), or with a bow / crossbow / wand fires an arrow or a coloured bolt that
flies until it hits a wall, an enemy, a prop or 8 tiles. Props take 1-3 hits (`PROP_HP`) and
leave crafting materials (`PROP_MATERIALS`: wood, iron, cloth, bone, stone) in
`Player.materials`, a weightless pouch shown in the inventory. Broken props stay broken in the
run save (`props`). New sounds: `shoot`, `crack`, `shatter`.

**Room props:** rooms hold sewer clutter (barrels, crates, clay pots, sacks, rusty buckets,
bone piles, rubble; `props.py`, art in `objects/props.png`). They stand on a room's edge row,
never on or beside a door, and block the way; interiors, doors and corridors always stay
reachable. Placement has its own RNG seeded from the floor seed (`PROPS_PER_ROOM` in `config.py`),
so floors, enemies and chests are unchanged and old runs still load.

**Play-test round 2 (PR #9):** the dungeon is a sewer. A new `sewer/tiles_v2.png` has mossy
flagstones, slimy brick walls with pipes, stains and moss, puddles, drains, bones, grated
walkways, thin iron gates on doorways and manhole stairs, and there is torch-light darkness. Walls block line of
sight, corridors are shorter, there is a Rat enemy, and the boss is a Rat King. `RUN_VERSION` was 3 (now 4, see Shop room).

**Play-test round 1 (done, PR #8):** single doors with corridors routed around rooms, fights
start on entering an occupied room, inventory from the dungeon (I), damage previews, attack
styles. Run saves carry `RUN_VERSION` (config); older runs are dropped because the same seed now
builds a different floor.

**Next steps (beyond the milestones):**

1. **Play-test the balance on the real machine.** The numbers in `config.py` (Balance section)
   came from a simulation (§4 Combat). Tune them there.
2. **Real art:** drop PNGs over the generated placeholders (same file names, §3.3). If enemy
   sheets were generated on your machine before this version, delete the untracked
   `pygame_rpg/assets/enemies/{bat,goblin,skeleton,boss}.png` so the new shapes are generated.
3. **Answer the open design questions in §9** (defeat penalty, endgame after floor 4-5, how
   abilities are found), which decide the next content milestone.

**Standing rules**

* Work one sub-milestone at a time; verify each with a headless run before starting the next.
* Never rename or remove an existing item id: saves reference items by id.
* `RPG_V3/` is a read-only reference. All new code lives in `pygame_rpg/`.
* Run the game from the repo root: `.\venv\Scripts\python.exe -m pygame_rpg.main` (Windows
  venv; see §7 for other setups).
* Commit only when asked; keep work on a branch and open a PR.

---

## 1. Build Order and Milestones

Build order: **M1 → M3 → M2 → M4 → M5.** M3 works with a tiny starter item set; M2's full
catalog then appears in the already-finished inventory UI; M4 needs M2's weapon effects to be
meaningful.

| # | Milestone | Contents | Status |
|---|-----------|----------|--------|
| M1 | Sprites everywhere | Tileset, player/enemy/item/UI sprites, asset manager | ✅ done |
| M3 | GUI up to the Base | Title → tutorial → hero maker/chooser → Base → inventory / stats / level-up, JSON saves | ✅ done (16 Oct 2026), 32-check end-to-end smoke test |
| M2 | Item system | Full catalog, equipment slots, equipment-driven stats, weight, rarity (six sub-milestones, §6.1) | ✅ done (29 Oct 2026): 212-item catalog, 11 slots, effective stats, HP/MP, level gate, rarity + loot roll |
| M4 | Dungeon + Combat | Collision, fog of war, loot, enemies/bosses, turn-based battles, weapon ailments, HUD | ✅ done (29 Oct 2026): dungeon screen, enemies + boss, battle screen, chests, stairs, fog, HUD, mid-run level-ups |
| M5 | Persistence + Polish | Dungeon state in saves, balance config, polish, pytest suite | ✅ done (29 Oct 2026): run saves, balance in `config.py`, pytest suite, effects, keyboard menus, enemy shapes, title logo |

---

## 2. Current State

### 2.1 What runs today

Starting the game runs the full pre-adventure flow in the GUI: **title → tutorial → hero maker
(name input → look → confirm) or hero chooser (paged saved list) → Base hub → inventory
(equip / unequip / use / drop + weight bar, 11 equipment slots incl. 4 ability slots) → stats (base + equipment bonus)
→ level-up (bank one stat at a time)**, with one JSON save per character. The Base's *Adventure* button opens the dungeon: **walk a fogged floor → bump an enemy → turn-based
battle → XP / loot → level up mid-run → open chests → beat the boss → stairs to the next floor**.
Esc returns to the Base and keeps the run (*Continue (Floor N)*). A defeat ends the run and you
wake up rested in the Base.

### 2.2 File-by-file

| File | Status | Notes |
|------|--------|-------|
| `pygame_rpg/main.py` | ✅ M4 | State machine: `build_screen()` factory, per-event screen switching, global clock loop. `handle_update` may also return a transition; `("resume", {"screen": s})` switches back to an existing screen object (dungeon floor after a battle / level-up). The M1 dungeon demo loop was removed (recoverable from git, commit `d2a0ec2`). |
| `pygame_rpg/config.py` | ✅ M5 | Screen 800×600 @ 60 FPS, starting stats, XP curve (`max_xp_for`), `BASE_MAX_WEIGHT = 50`, `SAVE_DIR`, rarity weights, and the **Balance** section (weapon power, enemy hit multiplier, variance, ailment bonuses, run / loot chances, post-win recovery, enemy growth, enemies per room, chests per floor). |
| `pygame_rpg/player.py` | ✅ M3 | `Player` dataclass: base stats, XP/level-up, upgrade counts, backpack, 11 equipment slots, `bonus()`/`total()`, `max_hp`/`current_hp`/`heal()`, `look` (appearance indices, `LOOK_KEYS`), `gold`, `materials` (pouch, `MATERIALS`), `blueprints`, `max_mp`/`current_mp`/`restore_mp()`/`can_cast()`/`spend_mp()`/`equipped_abilities()`, `slot_for`/`can_equip`/`slot_of`/`equip`/`unequip`/`drop`, `can_use`/`use`, weight, `to_dict`/`from_dict` (with old-save migration). |
| `pygame_rpg/items.py` | 🚧 M2 | `Item` dataclass; builders `_wp`/`_arm`/`_con`/`_trinket`/`_ab` + tier helpers `_tier`/`_arm_tier`/`_con_tier`/`_trinket_tier`/`_ab_tier`; `JUNK` (`_junk`, sell `value`), `CATALOG` (222 items), `LOOT_KINDS`, `roll_junk()`; `STARTER_INVENTORY = ["sword", "potion", "fireball"]`; `item_by_id()` returns a copy. |
| `pygame_rpg/savegame.py` | ✅ M5 | `saves/<name>.json` per character + `saves/index.json`; runs in `saves/runs/<name>.json` (`save_run` / `load_run` / `delete_run`; a broken run file reads as no run); `_safe_name()` validates names (`^[\w .-]{1,20}$`), index self-prunes missing files; `_resolve()` turns saved item refs (id or `{"id", "charges"}`) into items. |
| `pygame_rpg/gui/display.py` | ✅ | The window. Screens still draw on the fixed 800×600 canvas; `Display` opens a resizable window as large as fits the desktop (`fit_scale`, 0.25 steps), smooth-scales the canvas into it with black bars (`letterbox`), maps mouse events back to canvas coordinates (`to_canvas`) and toggles fullscreen on F11. `main.py` passes every event through `display.handle_event` and ends each frame with `display.present()`. |
| `pygame_rpg/settings.py` | ✅ | Player settings in one shared `settings.current`: `brightness` (0.5–2.0), `ambience_volume`, `effects_volume` (defaults from `config.py`), `fullscreen`, and `keys` (action → two key slots; actions up / down / left / right / attack / interact / inventory). `load()` at start-up, `save()` to `saves/settings.json` (bad values fall back to defaults). `bind()` takes a key off any other slot first; Esc, F11 and M are reserved. The dungeon asks `pressed(event, action)` / `held(keys, action)`; hints use `action_label()`. Menus keep their fixed arrows / Enter. |
| `pygame_rpg/gui/settings_screen.py` | ✅ | Sliders, fullscreen toggle and the key table, plus Reset keys / Back; opened from the title screen and the Base with `return_to` (resumed on leaving), saves on leaving. Plays the sewer ambience so its volume can be heard. Brightness is applied by `Display` (colours multiplied, black stays black); volumes by `audio` (`refresh_volume()` for the running loop). |
| `pygame_rpg/gui/screen.py` | ✅ M3 | `Screen` base class, `Button`, cached `font()`, shared palette, `QUIT` sentinel. |
| `pygame_rpg/gui/*.py` (8 screens) | ✅ M3 | `title_screen`, `tutorial_screen`, `hero_maker`, `hero_chooser`, `base_screen`, `inventory_screen`, `stats_screen`, `level_up_screen` (takes `return_to`: resume a dungeon floor instead of the Base). |
| `pygame_rpg/dungeon.py` | ✅ M4 | Seeded generation (private `rng`, same seed = same floor): 60 × 44 tiles, up to 13 rooms with `ROOM_GAP` free tiles between them; rooms are linked by a minimum spanning tree over wall-to-wall gaps (shortest corridors that still reach every room) with A*-routed corridors from a door on the wall facing the target to a door on the target, never entering another room or the ring around it, so walls stay solid and every door is a single tile (one door per wall, reused). `door_outside()` gives the corridor cell outside a door. `visible_from()` (line of sight), `is_walkable()`, `spawn_point()`, sewer-tileset rendering (`sewer/tiles_v2.png`, doorways drawn as a thin gate on the corridor side, per-cell variants cached in `_tile_cache`) with camera offset, fog (`seen` cells + their walls), dimming outside `visible`, `overrides` for the manhole stairs, minimap of visited rooms + walked corridors. |
| `pygame_rpg/special_rooms.py` | ✅ | `SPECIAL_KINDS`, `special_rooms(dungeon, seed)` (kind → room, own RNG), `keeper_cell(room)` (interior, clear of doors and the centre). |
| `pygame_rpg/crafting.py` | ✅ | `BLUEPRINTS` (weapon + armour bases), `RECIPES` by `family()` (incl. `leather` / `iron` armour), `base_id()`, `craft_cost` / `can_craft` / `craft`, `upgrade_cost` / `can_upgrade` / `upgrade` (in place), `upgradeable()`, `roll_blueprint()`; no drawing. |
| `pygame_rpg/gui/forge_screen.py` | ✅ | `ForgeScreen(player, return_to)`: Craft / Upgrade tabs, cost panel (green / red per material), keyboard + mouse. |
| `pygame_rpg/shop.py` | ✅ | `price()`, `sell_price()`, `roll_stock(seed, floor)`, `buy(player, stock, sold, index)`, `sell(player, item)`; no drawing. |
| `pygame_rpg/gui/shop_screen.py` | ✅ | `ShopScreen(player, stock, sold, return_to)`: goods and backpack side by side, keyboard + mouse, saves the hero after each trade. |
| `pygame_rpg/props.py` | ✅ | `Prop` (kind, cell, broken, hp; `solid` while standing, `hit()`), `PROP_HP`, `PROP_MATERIALS`, `salvage()`, `PROP_KINDS` (sheet order), `edge_cells()`, `place_props(dungeon, seed)` with its own `Random(f"props-{seed}")`. |
| `pygame_rpg/enemies.py` | ✅ M4 | `EnemyType` (frozen data) for slime, bat, goblin, skeleton + `BOSS_TYPE`; `make_enemy()` scales per floor; `boss_room()` (farthest from room 0); `place_enemies()` with the dungeon's rng. |
| `pygame_rpg/combat.py` | ✅ M4 | `Battle`: pure rules, no drawing. `attack()`, `cast()`, `use_item()`, `run()`, ailments (`AILMENTS`), cooldowns, Shield guard, wards, XP + loot on win. |
| `pygame_rpg/gui/dungeon_screen.py` | ✅ M4 | `DungeonScreen(player, floor, seed)`: `move()` with axis-separated wall collision (20 px hitbox), trinket speed bonus, walk animation by distance walked (`walk_frame()`, footsteps on `HERO_STEP_FRAMES` with a splash), idle breathing, shadows, clamped camera, fog (`seen`), enemies, chests, stairs, HUD + minimap. Saves the run (`to_run()` / `save_run()`) on floor entry, after each battle, on Esc and on quit; `run=` restores one. `step(dx, dy, dt)` is one frame and returns a transition (battle on bump, level-up after a win, next floor on the stairs); tests drive it directly. `battle_over()` is called by the battle screen. Esc saves → Base (no rest). Floor banner on arrival. |
| `pygame_rpg/gui/battle_screen.py` | ✅ M4 | `BattleScreen`: enemy + hero sprites, HP / MP bars, ailments, log, menu (Attack / Abilities / Items / Run, sub-lists), keyboard + mouse; Floating damage / heal numbers, hero hit flash + shake. Continue resumes the floor, or on defeat rests, saves, deletes the run → Base. |
| `pygame_rpg/gui/hud.py` | ✅ M4 | `Hud`: floor, level, weapon icon, HP / MP / XP bars, fading message log (`say()`). |
| `pygame_rpg/assets.py` + `assets/` | M1, in use | `AssetManager`: loads PNGs, slices sheets, and generates + saves placeholder art for missing files (tileset, slime, sword/potion icons, panel). `hero_frames(look, gear)` draws the hero in code per look and visible gear (`gear_of()`) (`LOOK_OPTIONS`, `look_choice()`), cached in memory, never saved. Used by GUI screens for icons/portrait. |
| `pygame_rpg/README.md` | ✅ M5 | Short player-facing readme: install, run, test, controls; points here. |
| `pygame_rpg/audio.py` | ✅ M5 | All sound, synthesised in plain Python at start-up on a background thread (no audio files, nothing to license): `_RECIPES` maps names to small synth functions (tones, filtered noise, echo). `play(name, delay, volume)` (a name with numbered variants such as `step0..2` picks one at random), `set_ambience("sewer" / None)` (looping bubbly water built from grains + scattered drips, distant metal clanks, pipe groans, rat squeaks via `_SCATTER`), `update(dt)` from the main loop, `toggle_mute()` (M; not on the hero-name screen). Every call is a no-op if the mixer can't start. Screens set an `ambience` class attribute; inventory and level-up inherit it from `return_to`. Volumes: `SFX_VOLUME` / `AMBIENT_VOLUME` in `config.py`. |
| `pygame_rpg/gui/effects.py` | ✅ M5 | `Particles` (burst / update / draw sparks) and `menu_key()` (Up / Down / Enter for button lists). |
| `RPG_V3/main_V3.py` | reference | Text UI: `tutorial()`, `hero_maker()`, `hero_chooser()`, `lobby()` (stub), `inventory()`/`backpack()` (stubs), `xp_check()`. Ported up to the Base. |
| `RPG_V3/assets_V3.py` | reference | `WP` weapon base + 7 subclasses with unimplemented `effect()`; empty `Consumable`/`Armor`/`Trinket`/`Ability`/`Enemy`/`Boss` classes; level-1 weapon catalog. |
| `RPG_V3/tutorial.txt` | in use | Rendered page by page by the tutorial screen. |

### 2.3 Git

* `d2a0ec2` "Baseline: M1 sprites + M3 GUI up to the Base" (16 Oct 2026).
* `be470d0` "M2 sub-milestones 1-2: weapons + armor catalog; sync docs".
* PR #1: `Handoff.md` + `Plan.md` merged into this file.
* PR #2: equipment/HP bug fixes + consumables. Then `7e47d37` trinkets (from the desktop
  stash) and abilities on the same branch.
* PRs #3 / #4: abilities, rarity (M2 done). PR #5: M4 (dungeon screen, enemies, combat, HUD).
* PR #6: M5 run saves, pytest suite, balance in `config.py`, battle feedback.
* PR #7: M5 polish (effects, keyboard menus, enemy shapes, title logo); M5 done.
* PR #9: play-test round 2 (line of sight, shorter corridors, sewer look, Rat + Rat King).
* PR #8: play-test round 1 (door generation, room-entry battles, inventory in the dungeon,
  damage previews, attack styles).
* `.gitignore` covers `venv/`, `saves/`, `__pycache__/`, `*.py[cod]`.

---

## 3. Architecture

### 3.1 Current layout

```
pygame_rpg/
├── main.py            # state machine + build_screen() factory + clock loop
├── config.py          # constants: display, stats, XP curve, weight, saves, rarity, balance
├── player.py          # Player: stats, XP/level-up, equipment, backpack, (de)serialization
├── items.py           # Item dataclass + data-driven catalog
├── savegame.py        # JSON save/load + hero index
├── assets.py          # AssetManager + placeholder generators
├── dungeon.py         # seeded floor generation, walkability, rendering, fog, minimap
├── enemies.py         # enemy types, per-floor scaling, boss room, placement
├── props.py           # room clutter (barrels, crates, pots...) and its placement
├── special_rooms.py   # the floor's shop room and where its keeper stands
├── shop.py            # prices, stock, buy / sell rules
├── crafting.py        # blueprints, crafting and upgrading weapons at the anvil
├── combat.py          # turn-based battle rules: damage, ailments, cooldowns, XP, loot
├── audio.py           # synthesised sound effects + sewer ambience, play()/set_ambience()
├── gui/
│   ├── screen.py      # Screen base, Button, fonts, palette, QUIT
│   ├── title_screen.py, tutorial_screen.py, hero_maker.py, hero_chooser.py
│   ├── base_screen.py, inventory_screen.py, stats_screen.py, level_up_screen.py
│   ├── dungeon_screen.py  # walk the floor: fog, enemies, chests, stairs
│   ├── effects.py         # Particles (sparks) + menu_key() keyboard navigation
│   ├── battle_screen.py   # turn-based battle menu
│   └── hud.py             # in-dungeon HUD (bars, weapon icon, message log)
└── assets/            # tileset, hero sheet, enemy sheets, item icons, objects/chest.png,
                       # ui/panel.png (generated placeholders)
```

### 3.2 Tests and saves on disk

```
tests/
├── conftest.py            # headless pygame, repo on sys.path, `saves` temp-folder fixture
├── test_combat.py         # damage formulas, styles, previews, ailments, wards, cooldowns, win / lose
├── test_dungeon.py        # no overlap, connectivity, seeding, boss + entrance rules
├── test_saves.py          # player + run round trips, migration, broken run file
├── test_gui.py            # keyboard menus, particles, battle end animations, enemy sheets
├── test_crafting.py       # families, blueprints in saves / drops, craft, upgrade, anvil room, forge screen
├── test_shop.py           # safe shop room, merchant, prices, stock, buying / selling, saves
├── test_money.py          # gold per win / floor, junk drops, saves, coins and junk in props
├── test_props.py          # props on edges away from doors, nothing cut off, seeded, blocking
├── test_looks.py          # character customization: look stage, look in saves, frames per look
├── test_smoke_scripts.py  # runs the two scripts below as pytest cases
├── m2_smoke_test.py       # end-to-end item / inventory checks (plain script)
└── m4_smoke_test.py       # end-to-end dungeon / battle / run-save checks (plain script)
saves/                     # git-ignored: <name>.json, index.json, runs/<name>.json
```

### 3.3 Conventions

* **One `Screen` class per game state.** `main.py` only switches screens and runs the clock.
* **Transition protocol:** screens never reference each other. `handle_event` returns `None`
  (stay), the `QUIT` sentinel, `"screen_name"`, or `("name", {kwargs})`; `main.py` builds the
  next screen via `build_screen()`. `handle_update` may return a transition too.
  `("resume", {"screen": s})` switches back to a screen that is still alive (screens that must
  survive a round trip, like a dungeon floor, pass themselves along as `dungeon` / `return_to`). `QUIT` is a sentinel object: compare with `is`, never `==`.
  New screens must be registered in `build_screen()`.
* **All player state lives in one `Player` object** (stats, equipment, backpack), passed to
  screens through the transition kwargs (`{"player": player}`).
* **Data, not code:** items are plain `Item` records; combat will read their stat fields.
  All V3 logic is re-implemented against real classes (no global dicts).
* **Input:** every screen supports keyboard (arrows / Enter / Escape) and mouse; Escape always
  goes back.
* **Assets:** stable filenames; a missing file gets a generated placeholder saved under the same
  name, so real art can be dropped in later without code changes.

### 3.4 Data model

**`Item`** (`items.py`) is one flat dataclass for every kind:
`id, name, kind ("weapon" | "armor" | "consumable" | "trinket" | "ability"), rarity, level (min player level),
weight (kg), ap, rap, map, dp, rdp, mdp, hp, slot, effect, heal, mana, damage, charges,
combat_only, bonus_weight, xp_bonus, loot_bonus, speed_bonus, resist (trinkets),
attack_type, mp_cost, cooldown, guard, duration (abilities), description`.
New kinds add fields with defaults (e.g. `charges`, `rarity`) so existing entries and
saves stay valid. Item ids for tiers follow `<base_id>_<level>` (e.g. `sword_3`), names get a
Roman numeral (`Sword III`).

**Equipment slots** (`player.EQUIP_SLOTS`): `weapon, head, torso, hands, feet, trinket1,
trinket2, ability1-4`. An item's `slot` names the slot it fits; `"trinket"` and `"ability"`
name a group (`player.SLOT_GROUPS`) and take the first free slot of it. Equipping needs
`item.level <= player.lvl` (`Player.can_equip`); items already equipped in an older save stay
equipped even above the gate.

**Saves** (`saves/<name>.json`): `name, lvl, xp, hp, current_hp, ap, rap, map, dp, rdp, mdp,
current_mp, lvl_up_counts, look {skin, hair, hair_color, tunic: option index}, gold, materials {wood, iron, cloth, bone, stone: count}, blueprints [weapon base id, ...], equipment {slot: ref | null}, inventory [ref, ...]`. A `ref` is an item id, or
`{"id": ..., "charges": n}` for a consumable with used charges.
**Old saves keep loading:** a missing `current_hp` / `current_mp` means full HP / MP, a missing `look` the default look; legacy slot `accessory` maps
to `trinket1`; an item in an unknown slot (e.g. the old `armor` slot) or a slot it doesn't fit
goes back to the backpack. The catalog is code
and saves are data, so items are always stored by id. `saves/index.json` is the hero list (the
V3 `saved_chars.txt` equivalent).

**Run saves** (`saves/runs/<name>.json`, M5): `version` (`RUN_VERSION`; a mismatch drops the run), `floor, seed, x, y, facing, beaten` (indices into
the seeded enemy placement), `chests` (opened flags), `props` (indices of broken props), `shop_sold` (bought-out stock indices), `stairs`, `seen` (fog cells), `visited`
(room indices), `corridors` (minimap). The seed rebuilds the floor, enemies and chests; the save
only records what changed. Chest loot after a reload is rolled fresh.

**Save triggers today:** on character creation; from the Base on Esc / *Save & Exit* / window
close / Adventure; in the dungeon on floor entry, after each battle, on Esc and on window close
(player + run); after a defeat (player; the run is deleted). Other screens save only on window close.

---

## 4. Game Mechanics Reference

* **Base vs effective stats:** the `Player` fields are base stats (start + level-ups) and are
  never changed by equipment. `Player.total(stat)` = base + `Player.bonus(stat)` (sum over
  equipped items), recomputed on every call. Combat must read `total()`.
* **HP:** the `hp` field is base max HP. `max_hp = total("hp")` (armor adds hp). The HP the
  hero has now is `current_hp`, capped at `max_hp` (clamped when armor comes off). Raising
  `hp` on level-up raises `current_hp` by the same amount. Battles damage it; `Player.rest()`
  refills HP and MP (leaving the dungeon, defeat).
* **Stats** (from V3): `hp`, plus six combat stats `ap` (melee attack), `rap` (ranged attack;
  `config.py` comments call it "raw"), `map` (magic attack), `dp`, `rdp`, `mdp` (matching
  defences). Start: level 1, 0 XP, 100 HP, 5 in each combat stat.
* **XP:** `max_xp = level × 100`. Level-up triggers at `xp >= max_xp` (V3 used strict `>`);
  leftover XP carries over, multiple level-ups can be pending. Each level-up gives +1 to one
  chosen stat (any of the seven) and increments `lvl_up_counts[stat]`.
* **Level-up flow:** `BaseScreen.pending_levels(player)` counts pending levels without banking.
  While pending > 0 the Base enables only *Choose Stat*. The level-up screen banks one stat
  per click and returns to the Base when pending hits 0; Esc returns without banking.
* **Weight:** `Player.weight` sums backpack + equipped items; `max_weight = BASE_MAX_WEIGHT = 50`
  (V3 referenced `weight`/`max_weight` but never defined them). `can_carry()` exists but only
  gates floor pickups once M4 adds them.
* **Weapons:** 20 level-1 bases ported from V3, 1 kg each, in five families with an `effect`:
  melee sharp → bleeding, melee dull → stun, ranged sharp → bleeding, ranged dull → stun,
  magic → poison / burning / electrocuted. Tiers 2-4: each attack stat the weapon has, and
  `dp`, grow +1 per level; weight = level. Better ailment chance/duration is keyed off `level`
  in `combat.py` (M4).
* **Armor** (designed from scratch, V3 has none): slots head / torso / hands / feet, two bases
  per slot (leather + iron). Profiles: head → `dp`, torso → `dp + rdp + mdp`, hands → `rdp`,
  feet → `mdp`; every piece adds small `hp`. Level 1: one stat = 1, hp 2, 1 kg (torso: all
  three = 1, hp 3, 2 kg). Tiers 2-4: each stat present +1, hp +1, weight +1 per level.
* **Consumables** (designed from scratch): four lines, level-1 base + tiers 2-4, all 1 kg.
  Health potion (`potion`): heal 25 × level, 1 charge. Ration (`ration`, food): heal 10 × level,
  3 charges. Mana potion (`mana_potion`): mana 20 × level, battle only (mana arrives with
  abilities). Bombs (`fire_bomb` → burning, `poison_bomb` → poison, `flash_bomb` → stun):
  damage 15 + 10 per level above 1, battle only (used from the M4 battle menu).
  *Use* in the inventory spends one charge of a healing item outside battle, is disabled at
  full HP, and removes the item at 0 charges. Backpack rows show `x<charges>` for stacks.
* **Trinkets** (13 bases × 4 levels, 0 kg, either trinket slot): weight belts (+kg to
  `max_weight`), XP amulets/coins (+% XP), loot rings/charms (+% loot), speed scarves/feathers
  (+% speed) and five wards (resist one ailment). Tiers: +1 kg or +5 % per level. All bonuses
  work: weight (`max_weight`), XP (battle XP), loot (drop chance), speed (walk speed), wards
  (−25 % ailment chance per ward level, so level 4 is immune).
* **MP:** `max_mp = START_MP (20) + MP_PER_LEVEL (5) × (level − 1)`; `current_mp` is what is
  left. A level-up raises both. Mana potions restore it (battle only).
* **Abilities** (6 bases × 4 levels, 0 kg, 4 ability slots, cast from the M4 battle menu):
  Fireball (magic 20 + burning), Chain Lightning (magic 15 + electrocuted), Power Strike
  (melee 15 + stun), Piercing Shot (ranged 15 + bleeding), Heal (25 HP), Shield (+3 dp/rdp/mdp
  for 3 turns). Each has an MP cost and a cooldown in turns. Tiers: damage +10, heal +15,
  guard +2, MP cost +2 per level; the level gate unlocks them. Cooldown tracking belongs to
  `combat.py` (battle state, not saved).
* **Starter kit:** `sword` + `potion` + `fireball` (V3 started empty).

**Combat (M4, `combat.py` / `enemies.py`).** Design calls made without V3 guidance; tune after
play-testing.

* **Flow:** stepping into a room where enemies stand starts one battle against all of them at
  once (play-test round 1: bumping let you walk around enemies). The hero aims at one target
  (nearest first; tap an enemy, Left / Right, or the menu's *Target* row to switch; it moves on
  when the target falls); attacks, abilities and bombs hit the target only. Same-named enemies
  get letters (Slime A / Slime B). Each hero action (Attack / ability / item / Run) is
  followed by every living enemy's turn; the hero panel shows their hits summed. XP is the sum,
  gold / loot / junk are rolled per enemy (at most one blueprint per fight). Ailments tick at the start of the afflicted side's turn; ability
  cooldowns and the Shield count down at the end of each round (cooldown 2 = usable again two
  turns after the cast).
* **Damage:** hero hit = (stat + power) × 0.85-1.15 − enemy defense, minimum 1. The stat follows
  the weapon type (`rap` → ranged, `map` without `ap` → magic, else melee: `ap`, `rap`, `map` via
  `total()`). Weapon power = 4 + 2 × level (unarmed 2); ability power = `damage` ÷ 2; bombs deal
  `damage` flat. Enemy hit = 2 × attack × 0.85-1.15 − hero `dp` / `rdp` / `mdp` (by enemy attack type)
  − Shield guard, minimum 1.
* **Attack styles** (`combat.STYLES`, chosen under *Attack*): Strike ×1.0 with the weapon's own
  ailment; Slash ×0.75, causes bleeding at +30 %; Bash ×0.8, causes stun at +15 %; Heavy ×1.35,
  no ailment, 25 % miss. The style's ailment replaces the weapon's.
* **Previews:** every attack style and damaging ability shows its min-max damage against this
  enemy, and the hero panel shows the enemy's next hit (`attack_preview`, `cast_preview`,
  `incoming_preview`).
* **Ailments** (`AILMENTS`, chance % / turns / damage per turn): bleeding 25/3/3, poison 30/3/3,
  burning 25/2/5, stun 20/1 (skip turn), electrocuted 20/1/2 (skip). +5 % per weapon or ability
  level above 1, abilities +20 %, bombs a flat 60 %.
* **Enemies** (floor-1 HP / attack / defense, type, ailment, XP): Slime 28/5/2 melee poison 20,
  Bat 20/6/1 melee bleeding 18, Rat 18/5/1 melee poison 15, Goblin 32/6/3 ranged bleeding 30 (floor 2+), Skeleton 40/7/4
  melee stun 40 (floor 3+), Rat King boss 60/6/4 melee bleeding 150. Per floor: HP +20 %,
  attack +1, defense +1, XP +30 %. 0-2 enemies per room (never the entrance), the boss in the
  room farthest from the entrance.
* **After a win:** XP (+ trinket bonus) goes into `player.xp`; the floor then opens the level-up
  screen if levels are pending and returns to the same floor. The hero recovers 10 % max HP and
  5 MP. Loot: 50 % (+ loot bonus) for normal enemies, always for the boss, rolled with
  `roll_loot(max_level = floor + 1, boss + 2)`, skipped if too heavy.
* **Run:** 60 %, never from the boss. Fleeing puts the hero in the corridor outside the room's
  nearest door; the room stays hostile.
* **Defeat:** "You collapse" → back to the Base with full HP / MP, nothing lost but the run.
* **Inventory mid-run:** I in the dungeon opens the inventory (equip, use potions); Esc / Back
  returns to the floor.
* **Leaving and resting:** Esc keeps the run and does *not* heal, so Esc-and-Continue is no free
  heal; use potions from the inventory. Starting a new adventure (first one or *New Adventure*)
  rests the hero.
* **Floors:** 2 chests per floor (not in the entrance room, loot up to floor + 1). The boss's
  room shows stairs once the boss is beaten; the stairs make a new floor (+1) with a new seed.
  Sight: line of sight up to `SIGHT` = 8 tiles; walls and doors block it (standing on a gate the hero still sees only the side they came from; the room opens up once they step through; no diagonal peeking past a gate). Cells seen
  before stay on the map, heavily dimmed (`MEMORY_SHADE`); enemies show only while in sight. A torch-light vignette
  darkens the screen edges.
* **Balance check** (simulated, not play-tested): a fresh hero clears floor 1 comfortably; the
  floor-4 boss wins about a quarter of fights for a hero without potions, so potions and level-ups
  matter from floor 3 on.

---

## 5. Known Issues and Gaps

**Fixed in the bug-fix pass (after PR #1):**

1. ~~Armor cannot be equipped~~ — the player now has `weapon, head, torso, hands, feet,
   trinket1, trinket2`; the inventory's Equip check asks `Player.slot_for()`.
2. ~~Equipment does not affect stats~~ — `bonus()` / `total()`; Base and stats screens show
   effective values, the stats screen also shows base + bonus; inventory diffs include HP.
3. ~~No max HP~~ — `max_hp` + `current_hp`; healing is capped.
4. ~~`accessory` vs `trinket` naming~~ — trinket slots everywhere, `accessory` migrated on load.
5. ~~`load_player` does not filter unknown slots~~ — migration in `Player.from_dict()`.
6. ~~Stats screen weight label hidden behind the Back button~~ — moved left of the button.

**Still open:**

* Enemies stand still; there is no attack / hurt animation on the dungeon map yet.
* The battle Items list shows at most four consumables.
* Generated placeholders are git-ignored (`pygame_rpg/assets/`); the files committed before
  that stay tracked. A placeholder generated once is kept on disk, so a newer generator (e.g. the
  enemy shapes) only shows after deleting the old file. Real art needs `git add -f`.
* The hero chooser, hero maker and inventory still lean on the mouse (text input works by
  keyboard); `effects.menu_key()` is the helper to extend them with.
* The stats screen grid uses 2 of its 3 columns (cosmetic).

---

## 6. Roadmap / Next Steps

### 6.1 M2 — Item system (done)

1. **Weapons**, 2. **Armor**, 3. **Consumables** — done (§4).

4. **Trinkets** — done (52 items, see §4).
5. **Abilities** — done (24 items, MP pool, 4 ability slots, see §4).
6. **Wiring** — done: 11 equipment slots, effective stats, max/current HP and MP, level gate on
   equip, charges in saves, old-save migration, and rarity: by tier (levels 1-2 common,
   3 rare, 4 epic; legendary reserved for hand-placed boss drops), rarity-coloured borders and
   labels in the inventory, `RARITY_WEIGHTS` (70/22/7/1) in `config.py`, `roll_rarity()` and
   `roll_loot(rng, max_level, kinds)` in `items.py`.

**Definition of done (M2):** full multi-tier catalog (weapons, armor, consumables, trinkets,
abilities), equipment math testable without pygame, weight system working, every old save loads.

### 6.2 M4 — Dungeon + Combat

Done (PR #5); the rules are in §4 (Combat). Props (room clutter) are in. Left for later: torches, floor pickups
besides chests, a "You died" animation.

1. **Dungeon** — ✅ dungeon screen, wall collision, connected floors, real doors, minimap, fog,
   chests, stairs.
2. **Enemies (`enemies.py`)** — ✅ slimes/bats on floor 1, stronger level-scaled types deeper, one
   boss per floor (larger sprite, more HP, uses an ailment). Enemies stand as visible sprites
   with idle animation; bumping into one starts a battle. No chasing AI.
3. **Combat (`combat.py` + `gui/battle_screen.py`)** — ✅ turn-based, Pokémon-style menu: attack
   with the equipped weapon (category decides ap/rap/map vs dp/rdp/mdp), abilities, items.
   Weapon ailments as data `{type: (dps_or_chance, duration_turns)}`: bleeding, stun, poison,
   burning, electrocuted, with status icons. On win: XP + chance-based drop. On death: "You
   died" screen, respawn at the Base, lose only current-floor progress.
4. **HUD (`gui/hud.py`)** — ✅ HP + XP bars, minimap with fog, message log ("+12 XP",
   "Picked up Dagger", "Bleeding!"), equipped weapon icon.

**Definition of done (M4):** enter Adventure from the Base → fight enemies with equipment-driven
damage and ailments → collect loot → level up mid-run → descend floors → boss, all sprite-based
with the HUD active.

### 6.3 M5 — Persistence + Polish

* **Persistence** — ✅ run saves (`saves/runs/<name>.json`, §3.4), Continue / New Adventure.
* **Balance** — ✅ combat / enemy / floor numbers in `config.py`. Item tier growth and
  `AILMENTS` stay next to their data (`items.py`, `combat.py`). Play-testing is still open.
* **Polish** — ✅ damage numbers, hero hit flash + shake, floor banner, victory burst + enemy
  death frames, defeat collapse, chest sparks, level-up fanfare, title logo with embers,
  distinct enemy placeholder shapes, keyboard navigation (title, Base, level-up), sound
  (`audio.py`: footsteps, doors, chests, encounter, the four attack styles, misses, hits,
  spells, potions, bombs, ailments, run, victory, defeat, level-up, stairs, menu clicks, and
  the looping sewer ambience). Open: real art.
* **Tests** — ✅ `python -m pytest` (117 tests, incl. `test_gui.py` and `test_audio.py`; `pytest.ini` limits collection to `test_*.py`). Open: split the two smoke scripts into real
  pytest functions over time; level-up banking has coverage only in the smoke script.

---

## 7. Environment and Testing

* **Windows venv (main dev machine):** `venv/` with Python 3.14.7 and `pygame-ce` 2.5.8. Plain
  `pygame` 2.6.1 has no CPython 3.14 wheel; `pygame-ce` is API-compatible (still `import pygame`).
  Run: `.\venv\Scripts\python.exe -m pygame_rpg.main` from the repo root.
* **Other setups:** `pip install -r requirements.txt` (pygame-ce + pytest), then
  `python -m pygame_rpg.main`.
* **Tests:** `python -m pytest` from the repo root (headless; saves go to temp folders). The item/player
  modules import fine on Python 3.13 too.
* **Headless runs:** set `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy` before
  `pygame.init()`. Surfaces and `convert()` work normally, so this catches real rendering bugs.
  Put the repo root on `PYTHONPATH` when running a harness script from another folder.
* **Existing harnesses** live outside the repo (`%LOCALAPPDATA%\Temp\opencode\m3_chunk1_test.py`
  … `m3_chunk7_test.py`); the latest, chunk 7, runs 32 end-to-end checks (new-hero route,
  saved-hero route, level-up banking, save round-trip). Porting these into a `tests/` pytest suite
  is part of M5, and doing it early would make every M2 sub-milestone cheaper to verify.
* **Quick catalog check** (no display needed):
  `python -c "from pygame_rpg import items; print(len(items.CATALOG))"` → `222` today.
* **M2 harness** `tests/m2_smoke_test.py` (run `python tests/m2_smoke_test.py` from the repo
  root → "m2 OK (177 checks)"): headless checks covering catalog counts and
  every pre-existing id, armor/trinket/ability equipping, the level gate, MP, rarity + loot rolls, base vs effective stats, capped healing and
  charges, save round-trip, old-save migration, and a GUI smoke test (every screen renders,
  equip armor and use a potion through the inventory buttons). Saves go to a temp folder; it is
  the natural seed for the M5 pytest suite. Extend it with each sub-milestone.
* **M4 harness** `tests/m4_smoke_test.py` → "m4 OK (380 checks)": 40 seeds of generation
  (no overlap, room cells intact, every room reachable, doors open onto corridors, determinism,
  global `random` untouched), and the dungeon screen (spawn, walls stop the hero, a 3000-step
  random walk stays on floor, the hero walks a BFS path to every room on three seeds, speed
  trinket, camera clamp, Adventure → dungeon → Esc → Base with save); enemy placement (one boss
  in the lair, free cells, empty entrance, seeded, floor scaling); combat rules (attack, cast +
  cooldown, heal / shield, bombs, no running from the boss, stun, wards, XP bonus, recovery, loot
  vs weight, defeat); and the full loop through the screens (bump → battle → Continue → mid-run
  level-up → resume, flee without re-bump, chest, boss → stairs → floor 2, fog, defeat → Base);
  run saves (save on entry / battle / Esc / quit / stairs, Continue restores enemies, chests,
  stairs, fog, position and HP, New Adventure drops the run, broken files, delete with the hero);
  battle feedback (damage numbers fade) and the floor banner.

---

## 8. Decisions and Learned Points

1. **V3 is a spec, not a codebase.** `RPG_V3/main_V3.py` is one file of `print()`/`input()`
   functions with module-level dicts and stub bodies. The pygame game re-implements it as classes.
2. **V3 gaps filled by design:** Base/inventory built from the plan because V3's `lobby()`,
   `inventory()` and `backpack()` are stubs; `BASE_MAX_WEIGHT = 50`; V3 has no rarity data, so
   rarity follows the tier (§6.1); V3 has no level-2+ weapons or any armor,
   so tiers and armor are design decisions documented in `items.py` comments.
3. **`item_by_id()` returns a copy**, so per-character state can never mutate the catalog.
4. **Asset manager pattern:** missing files are generated and saved to disk under the same name;
   first run populates `assets/`, real art replaces placeholders automatically.
5. **Combat is turn-based** (bump into an enemy → battle screen), matching the V3 text game. An
   earlier draft assumed real-time combat with cooldowns; that is superseded. Dungeon movement
   stays real-time.
6. **Phases vs milestones:** the former plan numbered phases 1-6 separately from milestones;
   this document uses milestones only (M1 sprites, M2 items, M3 GUI, M4 dungeon + combat,
   M5 persistence + polish).
7. **Floors live in screen objects.** A `DungeonScreen` holds its floor (enemies, chests, fog);
   battles and the level-up screen get it passed and `resume` it, so nothing is rebuilt. Run
   saves (M5) store the seed plus what changed, never the screen.
8. **XP stays banked by choice.** Battles add raw XP; levels are banked on the level-up screen
   (opened automatically after a win) so the player still picks each stat, as in V3.
9. **Defeat costs only the run,** no items or XP, to keep the early game forgiving until balance
   is play-tested.

---

## 9. Open Questions

* **Art source:** hand-drawn vs free CC0 packs (e.g. Kenney) vs generated placeholders. Current
  assumption: placeholders now, real art later via stable filenames.
* **MP growth:** MP grows a fixed 5 per level and is not a level-up choice. Make it one of the
  stats you can raise instead?
* **How abilities are found:** the hero starts with Fireball; the rest have no source yet.
  They now drop as loot (any catalog item can); add a trainer/shop in the Base too?
* **Defeat penalty:** today only the run is lost. Lose some XP or gold, or drop the backpack?
* **Floor scaling / endgame:** the catalog tops out at level 4 items; what happens after
  floor 4-5 (higher tiers, legendary boss drops, a final boss)?
* **Food:** rations are currently a weaker, multi-use heal. Make them heal over time or give a
  temporary buff instead?
* **Overload:** should exceeding `max_weight` block pickups only, or also slow movement?
* **Base content:** the shop and the anvil live in the dungeon (one room each per floor). Add
  them to the Base too, or keep them as a reason to explore?
