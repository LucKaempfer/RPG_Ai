# DEVELOPMENT.md — RPG_Ai Development Guide

> Single source of truth for further development. Replaces the former `Handoff.md` and
> `Plan.md` (both merged here on 23 Oct 2026). Keep this file current at the end of every
> work session: update §0, the status table in §2, and §5 when something changes.

**Goal:** turn the minimal `pygame_rpg/` dungeon crawler plus the text-based `RPG_V3/`
mechanics into one complete 2-D, sprite-based pygame game. Everything up to and including the
Base (lobby) already runs in the GUI; the item system, dungeon and combat are next.

---

## 0. Start Here

**Where we are:** M1 (sprites), M3 (GUI up to the Base) and M2 (item system) are done. **M4
(dungeon + combat) is in progress: step 1, the dungeon screen, is done.** The Base's *Adventure*
button opens `gui/dungeon_screen.py`: a generated floor where the hero walks with wall collision,
a walk animation, a following camera and a minimap of explored rooms and corridors. Esc saves and
returns to the Base. `pygame_rpg/items.py` holds a 212-item catalog with rarity and a
`roll_loot()` helper ready for drops.

**Next task: M4 step 2 — enemies** (details in §6.2):

1. New `pygame_rpg/enemies.py`: data-driven enemy types (`ENEMY_NAMES` in `assets.py` already
   lists slime, goblin, bat, skeleton, boss and their sprite sheets generate as placeholders).
   Stats scale with floor; one boss per floor in the room farthest from room 0.
2. Place enemies as sprites in rooms (never in room 0) with the idle animation
   (`ENEMY_IDLE` frames). Use the dungeon's own `rng` so placement follows the seed.
3. Bumping into one (hitbox overlap in `DungeonScreen.move`) requests a transition to a
   `"battle"` screen. Until step 3 exists, a stub battle screen that wins instantly is fine;
   the beaten enemy is removed from the floor, so the dungeon screen must survive the round
   trip (keep it in the transition kwargs, or keep floor state outside the screen).
4. Extend `tests/m4_smoke_test.py`.

Later M4 steps: **3. Combat** (`combat.py` + `gui/battle_screen.py`: turn-based menu Attack /
Abilities / Items / Run; damage from `Player.total()`; abilities via `can_cast()` /
`spend_mp()` with cooldowns in battle state; bombs and mana potions usable; ailments as data;
trinket wards and XP bonus apply; win → XP + `roll_loot()`, death → back to the Base).
**4. Loot, stairs, HUD, fog of war,** then dungeon state in saves (M5).

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
| M4 | Dungeon + Combat | Collision, fog of war, loot, enemies/bosses, turn-based battles, weapon ailments, HUD | 🚧 step 1 of 4 done (dungeon screen + collision); next: enemies |
| M5 | Persistence + Polish | Dungeon state in saves, balance config, polish, pytest suite | pending (character JSON saves already done) |

---

## 2. Current State

### 2.1 What runs today

Starting the game runs the full pre-adventure flow in the GUI: **title → tutorial → hero maker
(two-stage name input + confirm) or hero chooser (paged saved list) → Base hub → inventory
(equip / unequip / use / drop + weight bar, 11 equipment slots incl. 4 ability slots) → stats (base + equipment bonus)
→ level-up (bank one stat at a time)**, with one JSON save per character. The Base's *Adventure* button opens the dungeon (walk a generated floor; no enemies yet).

### 2.2 File-by-file

| File | Status | Notes |
|------|--------|-------|
| `pygame_rpg/main.py` | ✅ M3 | State machine: `build_screen()` factory, per-event screen switching, global clock loop. The M1 dungeon demo loop was removed (recoverable from git, commit `d2a0ec2`). |
| `pygame_rpg/config.py` | ✅ M3 | Screen 800×600 @ 60 FPS, starting stats, XP curve (`max_xp_for`), `BASE_MAX_WEIGHT = 50`, `SAVE_DIR`. |
| `pygame_rpg/player.py` | ✅ M3 | `Player` dataclass: base stats, XP/level-up, upgrade counts, backpack, 11 equipment slots, `bonus()`/`total()`, `max_hp`/`current_hp`/`heal()`, `max_mp`/`current_mp`/`restore_mp()`/`can_cast()`/`spend_mp()`/`equipped_abilities()`, `slot_for`/`can_equip`/`slot_of`/`equip`/`unequip`/`drop`, `can_use`/`use`, weight, `to_dict`/`from_dict` (with old-save migration). |
| `pygame_rpg/items.py` | 🚧 M2 | `Item` dataclass; builders `_wp`/`_arm`/`_con`/`_trinket`/`_ab` + tier helpers `_tier`/`_arm_tier`/`_con_tier`/`_trinket_tier`/`_ab_tier`; `CATALOG` (212 items); `STARTER_INVENTORY = ["sword", "potion", "fireball"]`; `item_by_id()` returns a copy. |
| `pygame_rpg/savegame.py` | ✅ M3 | `saves/<name>.json` per character + `saves/index.json`; `_safe_name()` validates names (`^[\w .-]{1,20}$`), index self-prunes missing files; `_resolve()` turns saved item refs (id or `{"id", "charges"}`) into items. |
| `pygame_rpg/gui/screen.py` | ✅ M3 | `Screen` base class, `Button`, cached `font()`, shared palette, `QUIT` sentinel. |
| `pygame_rpg/gui/*.py` (8 screens) | ✅ M3 | `title_screen`, `tutorial_screen`, `hero_maker`, `hero_chooser`, `base_screen`, `inventory_screen`, `stats_screen`, `level_up_screen`. |
| `pygame_rpg/dungeon.py` | 🚧 M4 | Seeded generation (private `rng`, same seed = same floor): non-overlapping rooms, corridors linked as a tree so every room is reachable, doors where corridors leave rooms. `is_walkable()`, `spawn_point()`, tileset rendering with camera offset, minimap of visited rooms + walked corridors. |
| `pygame_rpg/gui/dungeon_screen.py` | 🚧 M4 | `DungeonScreen`: hero position, `move()` with axis-separated wall collision (20 px hitbox), trinket speed bonus, walk/idle animation, clamped camera, overlay (floor, HP/MP, minimap). Esc saves → Base. |
| `pygame_rpg/assets.py` + `assets/` | M1, in use | `AssetManager`: loads PNGs, slices sheets, and generates + saves placeholder art for missing files (tileset, hero sheet, slime, sword/potion icons, panel). Used by GUI screens for icons/portrait. |
| `pygame_rpg/README.md` | outdated | Still describes the M1 skeleton (walk around a dungeon). Update or fold into this file when M4 lands. |
| `RPG_V3/main_V3.py` | reference | Text UI: `tutorial()`, `hero_maker()`, `hero_chooser()`, `lobby()` (stub), `inventory()`/`backpack()` (stubs), `xp_check()`. Ported up to the Base. |
| `RPG_V3/assets_V3.py` | reference | `WP` weapon base + 7 subclasses with unimplemented `effect()`; empty `Consumable`/`Armor`/`Trinket`/`Ability`/`Enemy`/`Boss` classes; level-1 weapon catalog. |
| `RPG_V3/tutorial.txt` | in use | Rendered page by page by the tutorial screen. |

### 2.3 Git

* `d2a0ec2` "Baseline: M1 sprites + M3 GUI up to the Base" (16 Oct 2026).
* `be470d0` "M2 sub-milestones 1-2: weapons + armor catalog; sync docs".
* PR #1: `Handoff.md` + `Plan.md` merged into this file.
* PR #2: equipment/HP bug fixes + consumables. Then `7e47d37` trinkets (from the desktop
  stash) and abilities on the same branch.
* `.gitignore` covers `venv/`, `saves/`, `__pycache__/`, `*.py[cod]`.

---

## 3. Architecture

### 3.1 Current layout

```
pygame_rpg/
├── main.py            # state machine + build_screen() factory + clock loop
├── config.py          # constants: display, starting stats, XP curve, weight, save dir
├── player.py          # Player: stats, XP/level-up, equipment, backpack, (de)serialization
├── items.py           # Item dataclass + data-driven catalog
├── savegame.py        # JSON save/load + hero index
├── assets.py          # AssetManager + placeholder generators
├── dungeon.py         # seeded floor generation, walkability, rendering, minimap
├── gui/
│   ├── screen.py      # Screen base, Button, fonts, palette, QUIT
│   ├── title_screen.py, tutorial_screen.py, hero_maker.py, hero_chooser.py
│   ├── base_screen.py, inventory_screen.py, stats_screen.py, level_up_screen.py
│   └── dungeon_screen.py  # M4: walk the floor (Adventure)
└── assets/            # tileset.png, player/hero_sheet.png, enemies/slime.png,
                       # items/{sword,potion}.png, ui/panel.png (generated placeholders)
```

### 3.2 Target additions (M4/M5)

```
pygame_rpg/
├── enemies.py         # Enemy + Boss classes, per-floor scaling, room placement
├── combat.py          # turn-based battle logic, ailment data + ticks, XP/drops
├── gui/
│   ├── battle_screen.py  # turn-based battle: menu, sprite HP bars, status icons
│   └── hud.py            # in-dungeon HUD: HP/XP bars, minimap, message log, weapon icon
└── assets/
    ├── player/        # 4 dirs × (idle, walk, attack, hurt, death)
    ├── enemies/       # one sheet per enemy type + boss
    ├── items/         # one unique icon per catalog item
    └── ui/            # panels, buttons, bars, slots, pixel font
tests/                 # pytest suite (M5)
```

### 3.3 Conventions

* **One `Screen` class per game state.** `main.py` only switches screens and runs the clock.
* **Transition protocol:** screens never reference each other. `handle_event` returns `None`
  (stay), the `QUIT` sentinel, `"screen_name"`, or `("name", {kwargs})`; `main.py` builds the
  next screen via `build_screen()`. `QUIT` is a sentinel object: compare with `is`, never `==`.
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
current_mp, lvl_up_counts, equipment {slot: ref | null}, inventory [ref, ...]`. A `ref` is an item id, or
`{"id": ..., "charges": n}` for a consumable with used charges.
**Old saves keep loading:** a missing `current_hp` / `current_mp` means full HP / MP; legacy slot `accessory` maps
to `trinket1`; an item in an unknown slot (e.g. the old `armor` slot) or a slot it doesn't fit
goes back to the backpack. The catalog is code
and saves are data, so items are always stored by id. `saves/index.json` is the hero list (the
V3 `saved_chars.txt` equivalent).

**Save triggers today:** on character creation; from the Base on Esc / *Save & Exit* / window
close; other screens save only on window close.

---

## 4. Game Mechanics Reference

* **Base vs effective stats:** the `Player` fields are base stats (start + level-ups) and are
  never changed by equipment. `Player.total(stat)` = base + `Player.bonus(stat)` (sum over
  equipped items), recomputed on every call. Combat must read `total()`.
* **HP:** the `hp` field is base max HP. `max_hp = total("hp")` (armor adds hp). The HP the
  hero has now is `current_hp`, capped at `max_hp` (clamped when armor comes off). Raising
  `hp` on level-up raises `current_hp` by the same amount. Nothing damages the hero yet (M4).
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
  (+% speed) and five wards (resist one ailment). Tiers: +1 kg or +5 % per level. Only the
  weight bonus has an effect today; XP/loot/speed/resist are read by M4.
* **MP:** `max_mp = START_MP (20) + MP_PER_LEVEL (5) × (level − 1)`; `current_mp` is what is
  left. A level-up raises both. Mana potions restore it (battle only).
* **Abilities** (6 bases × 4 levels, 0 kg, 4 ability slots, cast from the M4 battle menu):
  Fireball (magic 20 + burning), Chain Lightning (magic 15 + electrocuted), Power Strike
  (melee 15 + stun), Piercing Shot (ranged 15 + bleeding), Heal (25 HP), Shield (+3 dp/rdp/mdp
  for 3 turns). Each has an MP cost and a cooldown in turns. Tiers: damage +10, heal +15,
  guard +2, MP cost +2 per level; the level gate unlocks them. Cooldown tracking belongs to
  `combat.py` (battle state, not saved).
* **Starter kit:** `sword` + `potion` + `fireball` (V3 started empty).

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

* `pygame_rpg/README.md` still describes the M1 skeleton.
* Placeholder icons for items are generated into `pygame_rpg/assets/items/` the first time an
  item is shown, so they appear as untracked files in `git status`. Either commit them, ignore
  them, or generate them in memory only.
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

The M1 crawler (`dungeon.py`, `assets.py`) is revived and wired to the Base's *Adventure* button.

1. **Dungeon** — ✅ dungeon screen, wall collision, connected floors, real doors, minimap.
   Still to come in step 4: tile fog of war, loot chests, floor pickups (respect
   `can_carry`), stairs to the next generated floor, torches/decor.
2. **Enemies (`enemies.py`)** — slimes/rats on floor 1, stronger level-scaled types deeper, one
   boss per floor (larger sprite, more HP, uses an ailment). Enemies stand as visible sprites
   with idle animation; bumping into one starts a battle. No chasing AI.
3. **Combat (`combat.py` + `gui/battle_screen.py`)** — turn-based, Pokémon-style menu: attack
   with the equipped weapon (category decides ap/rap/map vs dp/rdp/mdp), abilities, items.
   Weapon ailments as data `{type: (dps_or_chance, duration_turns)}`: bleeding, stun, poison,
   burning, electrocuted, with status icons. On win: XP + chance-based drop. On death: "You
   died" screen, respawn at the Base, lose only current-floor progress.
4. **HUD (`gui/hud.py`)** — HP + XP bars, minimap with fog, message log ("+12 XP",
   "Picked up Dagger", "Bleeding!"), equipped weapon icon.

**Definition of done (M4):** enter Adventure from the Base → fight enemies with equipment-driven
damage and ailments → collect loot → level up mid-run → descend floors → boss, all sprite-based
with the HUD active.

### 6.3 M5 — Persistence + Polish

* **Persistence:** `dungeon.json` (floor seed, room state, defeated enemies, opened chests);
  in-run save triggers (leaving mid-run, floor cleared, explicit *Save & Exit*).
* **Balance:** move tuning numbers (tier growth, ailment values, drop rates) into `config.py`.
* **Polish:** hit flash, screen shake, death animation, chest pop, level-up fanfare (no audio
  dependency required), consistent pixel font/panels, logo on the title screen.
* **Tests (pytest, headless):** dungeon generation (room count, connectivity, no overlap);
  item system (stat math, weight/overload, rarity roll, equip/unequip round-trip); level-up
  (XP curve, carry-over, stat pick persistence); save/load (round-trip, corrupt save, old-save
  migration); combat (damage formula, ailment ticks, stun skip).

---

## 7. Environment and Testing

* **Windows venv (main dev machine):** `venv/` with Python 3.14.7 and `pygame-ce` 2.5.8. Plain
  `pygame` 2.6.1 has no CPython 3.14 wheel; `pygame-ce` is API-compatible (still `import pygame`).
  Run: `.\venv\Scripts\python.exe -m pygame_rpg.main` from the repo root.
* **Other setups:** `pip install pygame-ce`, then `python -m pygame_rpg.main`. The item/player
  modules import fine on Python 3.13 too.
* **Headless runs:** set `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy` before
  `pygame.init()`. Surfaces and `convert()` work normally, so this catches real rendering bugs.
  Put the repo root on `PYTHONPATH` when running a harness script from another folder.
* **Existing harnesses** live outside the repo (`%LOCALAPPDATA%\Temp\opencode\m3_chunk1_test.py`
  … `m3_chunk7_test.py`); the latest, chunk 7, runs 32 end-to-end checks (new-hero route,
  saved-hero route, level-up banking, save round-trip). Porting these into a `tests/` pytest suite
  is part of M5, and doing it early would make every M2 sub-milestone cheaper to verify.
* **Quick catalog check** (no display needed):
  `python -c "from pygame_rpg import items; print(len(items.CATALOG))"` → `212` today.
* **M2 harness** `tests/m2_smoke_test.py` (run `python tests/m2_smoke_test.py` from the repo
  root → "m2 OK (177 checks)"): headless checks covering catalog counts and
  every pre-existing id, armor/trinket/ability equipping, the level gate, MP, rarity + loot rolls, base vs effective stats, capped healing and
  charges, save round-trip, old-save migration, and a GUI smoke test (every screen renders,
  equip armor and use a potion through the inventory buttons). Saves go to a temp folder; it is
  the natural seed for the M5 pytest suite. Extend it with each sub-milestone.
* **M4 harness** `tests/m4_smoke_test.py` → "m4 OK (260 checks)": 40 seeds of generation
  (no overlap, room cells intact, every room reachable, doors open onto corridors, determinism,
  global `random` untouched), and the dungeon screen (spawn, walls stop the hero, a 3000-step
  random walk stays on floor, the hero walks a BFS path to every room on three seeds, speed
  trinket, camera clamp, Adventure → dungeon → Esc → Base with save).

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

---

## 9. Open Questions

* **Art source:** hand-drawn vs free CC0 packs (e.g. Kenney) vs generated placeholders. Current
  assumption: placeholders now, real art later via stable filenames.
* **MP growth:** MP grows a fixed 5 per level and is not a level-up choice. Make it one of the
  stats you can raise instead?
* **How abilities are found:** the hero starts with Fireball; the rest have no source yet.
  Loot drops (M4), a trainer/shop in the Base, or auto-learn on level-up?
* **Food:** rations are currently a weaker, multi-use heal. Make them heal over time or give a
  temporary buff instead?
* **Overload:** should exceeding `max_weight` block pickups only, or also slow movement?
* **Base content:** shop or crafting later? The hub screen can host extra buttons.
