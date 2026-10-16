# Plan.md — RPG_Ai Development Plan

> Goal: turn the minimal `pygame_rpg/` dungeon crawler + the text-based RPG_V3 mechanics into one
> complete 2‑D sprite‑based pygame game, where **all game functions up to and including the Base
> (lobby)** run inside the GUI.

---

## 1. Current State (what exists today)

| Area | Status |
|------|--------|
| `pygame_rpg/main.py` | ✅ M3: state machine + `build_screen()` factory, screen switching, global clock loop (M1 dungeon loop removed; recoverable from git) |
| `pygame_rpg/dungeon.py` | M1 (dormant): procedural rooms + corridors, tiled rendering, minimap — kept for Phase 4 (M4) |
| `pygame_rpg/assets.py` + `assets/` | M1: asset manager + generated placeholder art with stable names — dormant, kept for M4 |
| `pygame_rpg/config.py` | ✅ M3: screen/FPS constants, starting stats, XP curve, `BASE_MAX_WEIGHT`, save dir |
| `pygame_rpg/player.py` | ✅ M3: `Player` — stats, XP/level-up, equipment, JSON round-trip |
| `pygame_rpg/items.py` | ✅ M3 (M2 partial): `Item` dataclass + level/tier system, 113-item catalog (20 weapon bases + 60 weapon tiers + 8 armor bases + 24 armor tiers + potion) |
| `pygame_rpg/savegame.py` | ✅ M3: JSON saves — flat `saves/<name>.json` per character + `saves/index.json`, name validation |
| `pygame_rpg/gui/` | ✅ M3: shared `screen.py` base + 8 screens (title, tutorial, hero maker/chooser, base, inventory, stats, level-up) |
| `RPG_V3/main_V3.py` | Text UI reference (ported up to the Base in M3): `tutorial()`, `hero_maker()`, `hero_chooser()`, `lobby()` (stub), `inventory()`/`backpack()` (stubs), `xp_check()` |
| `RPG_V3/assets_V3.py` | M2 reference: `WP` weapon base + 7 subclasses with unimplemented `effect()`; skeleton `Consumable`/`Armor`/`Trinket`/`Ability`/`Enemy`/`Boss` classes; level‑1 weapon catalog |
| Environment | `venv/` Python 3.14 + `pygame-ce` 2.5.8 (required — plain pygame has no cp314 wheel) |

---

## 2. Target Architecture

```
pygame_rpg/
├── main.py                 # entry point: state machine, screen switching, global loop
├── config.py               # constants: screen/tile size, paths, colors, balance values
├── dungeon.py              # (existing) generation — refactored: tilemap, fog of war, room loot
├── assets.py               # asset manager: load/cache sprite sheets, tileset, icons, fonts
├── player.py               # Player: stats, movement, animation state, equipment
├── items.py                # full item system (Phase 3)
├── enemies.py              # Enemy + Boss classes, per-room placement, battle data
├── combat.py               # turn-based battle logic, weapon effect() ailments, XP/drops
├── savegame.py             # JSON save/load: character, inventory, dungeon state
├── gui/
│   ├── screen.py           # Screen base class: handle_event → transition / handle_update(dt) / draw
│   ├── title_screen.py     # title + menu (New / Saved / Exit)
│   ├── tutorial_screen.py  # renders tutorial.txt pages, skip/next
│   ├── hero_maker.py           # name input, duplicate check, confirm, stat preview
│   ├── hero_chooser.py        # list saved heroes, preview, select/delete
│   ├── base_screen.py      # THE BASE (lobby): hub menu → inventory / stats / (adventure)
│   ├── inventory_screen.py # backpack grid + equipment slots + weight bar
│   ├── stats_screen.py     # hp/ap/rap/map/dp/rdp/mdp, XP bar, upgrade history
│   ├── level_up_screen.py  # pick stat to upgrade (ported xp_check)
│   ├── battle_screen.py    # Pokémon-style turn battle: menu, sprite HP bars, status icons
│   └── hud.py              # in-dungeon HUD: HP/XP bar, minimap, message log
└── assets/
    ├── tileset.png         # 32×32 tiles: floor, wall, door, corridor, chest, stairs
    ├── player/             # sprite sheets: 4 dirs × (idle, walk, attack, hurt, death)
    ├── enemies/            # one sheet per enemy type + boss
    ├── items/              # one icon per item (all items get a unique icon)
    └── ui/                 # panels, buttons, bars, inventory slots, fonts
```

**Rule of thumb:** one `Screen` class per game state; `main.py` only switches screens and runs
the clock. All RPG_V3 logic is re-implemented against real classes (no global dicts).

---

## 3. Phase 1 — 2D Sprites for ALL Assets

Everything that is currently a colored rectangle becomes a sprite.

1. **Tileset (32×32)**
   - Floor variants (2–3 textures for visual variety), wall, door, corridor, chest, stairs,
     torch/decor.
   - `Dungeon.render()` switches from `pygame.draw.rect` to blitting from a tileset with a
     camera offset; add a per-tile variation pass (deterministic via tile coords) so floors
     don't look flat.
2. **Player sprite sheet**
   - 4 directions × walk animation + idle, attack swing, hurt, death.
   - `Player` gets an animation state machine driven by movement/attack, replaces the blue
     surface in `main.py`.
3. **Enemy sprites** — one sheet per enemy type + boss (see Phase 5), with idle/attack/hurt/death.
4. **Item icons** — every item in the catalog gets a unique icon (weapons, armor, potions,
   trinkets). Used in inventory, HUD hotbar, pickup on the floor, and loot chests.
5. **UI sprites** — framed panels, buttons, HP/XP bars, inventory grid slots, rarity-color
   borders, font (pixel font for the retro look).
6. **Asset manager** (`assets.py`)
   - Loads and caches sheets; slices frames by grid size; helper `get_icon(item)`.
   - **Fallback policy:** if an image file is missing, draw a labeled colored placeholder so
     development never crashes on missing art.
   - **Art sourcing:** start with programmatically generated placeholders (or free CC0 packs,
     e.g. Kenney-style dungeon tileset), keep filenames stable so real art can be swapped in
     later without code changes.

**Definition of done (M1):** running the game shows a tiled dungeon with an animated player —
no raw `pygame.draw.rect` colors anywhere in the scene.

---

## 4. Phase 2 — Sophisticated Item System (`items.py`)

Port `RPG_V3/assets_V3.py` into a working, data-driven item system.

### 4.1 Core design
- `Item` base dataclass: `name`, `item_id`, `level` (level gate), `rarity`, `weight_kg`,
  `stat_mods` (dict over hp/ap/rap/map/dp/rdp/mdp), `icon` key, `description`.
- `Rarity`: common / rare / epic / legendary → drives border color in UI + spawn weights.
- All stat effects are **data**, not code; combat reads `stat_mods`.

### 4.2 Weapons (existing hierarchy, now functional)
| Subclass | Category | `effect()` (implemented in Phase 5 combat) |
|----------|----------|--------------------------------------------|
| `WP_melee_sharp`   | melee | **Bleeding** – damage over time |
| `WP_melee_dull`    | melee | **Stun** – chance enemy skips turn |
| `WP_range_sharp`   | ranged | **Bleeding** |
| `WP_range_dull`    | ranged | **Stun** (lower chance, longer duration) |
| `WP_magic_poison`  | magic | **Poison** – damage over time |
| `WP_magic_fire`    | magic | **Burning** – damage over time |
| `WP_magic_electric`| magic | **Electrocuted** – chance to interrupt/chain |

- Weapon category (melee/ranged/magic) determines attack type in combat and attack animation.
- Expand the level‑1 catalog (Saber, Spear, Dagger, Sword, Greatsword, Warhammer, Mace, Club,
  Crossbow, Bow, Blowpipe, Boomerang, Slingshot, Whip, Staves/Wands) with **level‑2+ tiers**:
  per-tier stat growth, better ailment chance/duration, more weight.
- Ailment definitions live in `combat.py` as data: `{type: (dps_or_chance, duration_ticks)}`.

### 4.3 New item types (skeleton classes in V3 → implemented)
- **`Armor`** — slots: head / torso / hands / feet. Stats: `dp`/`rdp`/`mdp` scaling, small hp
  bonus. Tiers per level; weight matters.
- **`Consumable`** — healing potion, mana potion, food (restores weight capacity?), bomb.
  `use(target)` method; has `charges` for stackable items.
- **`Trinket`** — passive bonuses: +XP gain, +loot chance, +speed, +max_weight, ailment
  resistance. 2 equip slots.
- **`Ability`** — active skills unlocked by level (e.g. Fireball, Shield, Heal); cost in
  AP/MP, cooldown ticks; assigned to the 4 ability slots (chosen from the battle menu,
  not hotkeys).

### 4.4 Equipment & capacity
- Equipment slots: **weapon, armor ×4, trinket ×2, ability slots (4)**.
- Equipping applies `stat_mods` to the player's derived stats; unequipping removes them
  (player base stats + Σ equipment — recomputed, never mutated).
- **Backpack weight**: `weight / max_weight` (the variables V3's `backpack()` already
  referenced). Overload → movement speed penalty. Weight bar drawn in the inventory UI.
- Inventory actions: equip / unequip / use / drop (drop spawns item sprite on the floor tile).

### 4.5 Build order: six sub-milestones

M2 is implemented one sub-milestone at a time, in this order:

1. **Weapons, all tiers** — grow the level-1 catalog into a full multi-level weapon line
   (stronger versions, better status effects, heavier).
2. **Armor** — head / torso / hands / feet in tiers; defensive stats + HP.
3. **Consumables** — more potion types, food, bombs; stackable uses.
4. **Trinkets** — passive bonus items (extra weight capacity, more XP, etc.).
5. **Abilities** — active skills unlocked by level (fireball, shield, heal, etc.) for battle slots.
6. **Wiring** — new equipment slots (4 armor + 2 trinkets), equipment-reflected stats,
   level/rarity rules, updated inventory UI, old-save compatibility.

Each sub-milestone is verified with a quick headless run before the next starts.

**Definition of done (M2):** full item catalog in `items.py` (weapons + armor + consumables +
trinkets + abilities, multi-tier), equipment math unit-testable without pygame, weight system
working.

---

## 5. Phase 3 — ALL Functions Up to the Base, in the GUI

Every function of `RPG_V3/main_V3.py` up to (and including) the Base/lobby gets a GUI screen.
Flow: `Title → Tutorial → New/Saved → Base → Inventory / Stats / Level-up`.

1. **Title screen** — game logo (sprite), buttons: *New Hero*, *Saved Heroes*, *Exit*.
2. **Tutorial screen** (port of `tutorial()`) — paginated render of `tutorial.txt`,
   Next / Back / Skip, skippable each run.
3. **Hero maker screen** (port of `hero_maker()` + `character_double_check()`)
   - Name text input field (mouse + keyboard), live duplicate check against the save index.
   - Confirmation step ("Is X correct? yes/no") as buttons.
   - Live preview: player sprite, base stats (100 hp, 5 ap/rap/map/dp/rdp/mdp, lvl 1).
   - On confirm → writes save, adds to index, jumps to Base.
4. **Hero chooser screen** (port of `hero_chooser()` — currently broken in V3)
   - Lists saved heroes from `saves/` index with level + sprite.
   - Hover/selection shows full stat preview; buttons: *Load*, *Delete* (with confirm).
5. **Base / Lobby screen** (port of `lobby()`) — the hub:
   - "Welcome in your Base, {name}." with sprite portrait + stat summary.
   - Menu buttons: **Inventory**, **View Stats**, **Adventure** (Phase 5, disabled until done),
     **Save & Exit** (auto-save on leave anyway).
6. **Inventory screen** (port of `inventory()` + `backpack()`)
   - Left: backpack grid of item **icons** with counts; weight bar `weight / max_weight`.
   - Right: equipment slots with icons.
   - Actions per selected item: **Equip / Unequip / Use / Drop**, and a detail panel showing
     description + stat diffs (green/red deltas vs currently equipped).
   - Rarity-colored slot borders.
7. **Stats screen** — name, level, XP bar (`xp / max_xp`), the 7 stats (hp, ap, rap, map, dp,
   rdp, mdp) split into *base* vs *equipment bonus*, plus upgrade history (per-stat count from
   the ported `lvl_up_stats`).
8. **Level-up screen** (port of `xp_check()`)
   - Triggered when `xp >= max_xp` (on entering Base or after combat).
   - "LEVEL UP!" panel: pick one of the 7 stats to raise; shows current value and how many
     times each stat was already upgraded (the V3 table, rendered as rows with + buttons).
   - Remaining XP carries over (multi-level support).

### UI/UX conventions
- All screens: keyboard (arrows/Enter/Escape) **and** mouse navigation; Escape always goes back.
- One shared `Screen` base class; screens never talk to each other directly — they request
  transitions via the state machine in `main.py`.
- All player state lives in one `Player` object (stats, equipment, inventory), passed to screens.

**Definition of done (M3):** start the game → title → tutorial → create or load a hero → Base →
full inventory (equip/unequip/use/drop + weight) → stats → level-up screen, entirely in the
GUI with sprites. No terminal `input()` anywhere.

> **✅ M3 complete (16 Oct 2026).** All screens implemented: `gui/screen.py` base (shared
> `Button`, fonts, palette, `QUIT` sentinel) + `title_screen`, `tutorial_screen`, `hero_maker`,
> `hero_chooser`, `base_screen`, `inventory_screen`, `stats_screen`, `level_up_screen`.
> State machine + `build_screen()` factory in `main.py`; JSON saves as flat
> `saves/<name>.json` per character + `saves/index.json`. Verified headless (`SDL_VIDEODRIVER=dummy`):
> 32-check end-to-end smoke test passing (new-hero and saved-hero paths, level-up banking,
> save round-trip). Deliberate deviations: level-up triggers at `xp >= max_xp` (V3 used strict
> `>`); kind-based slot border colors (no rarity tiers yet); `can_carry` weight gate deferred
> to Phase 4 floor pickups.

---

## 6. Phase 4 — Dungeon + Combat (building on the existing crawler)

The existing crawler stays; it gains collision, loot, enemies, and combat.

1. **Dungeon upgrades (`dungeon.py`)**
   - Real tilemap with wall collision (current code only clamps to bounds — player walks
     through walls).
   - Fog of war: tiles become visible when entered (minimap already tracks visited rooms —
     extend to tiles).
   - Room content: loot chests (icon sprite + open animation → items), item pickups on floor,
     stairs tile to the next generated floor, torches/decor for depth.
2. **Enemies (`enemies.py`)**
   - Enemy classes per the V3 skeleton: slimes/rats (floor 1) → stronger types per floor depth
     (level-scaled stats), one **Boss** per floor (larger sprite, more HP, uses an ailment).
   - Enemies stand as visible sprites in rooms (idle animation). Bumping into one starts a turn-based battle (Pokémon style) — no chasing AI, no real-time hits. Old simple AI (idle → detect in radius → chase → attack in weapon-range; sprites animate.
3. **Combat (`combat.py`)**
   - Player attack with equipped weapon: melee = short-range swing (facing dir), ranged =
     projectile sprite, magic = projectile with element color.
   - **Weapon `effect()` implemented**: on hit, roll ailment chance → apply
     bleeding / stun / poison / burning / electrocuted to the enemy (status icons above its
     head, tick damage each frame).
   - Enemy damage reduced by dp/rdp/mdp vs attack type; player HP bar in HUD.
   - On kill: XP + chance-based item drop (floor sprite → walk over to collect).
   - Player death: "You died" screen → respawn at Base, lose nothing but current-floor
     progress (keep it friendly).
4. **In-dungeon HUD (`gui/hud.py`)**
   - HP bar + XP bar top-left (sprite bars), minimap (existing, now with tile fog),
     message log (bottom-left: "+12 XP", "Picked up Dagger", "Bleeding!"),
     hotbar (4 ability keys) + equipped weapon icon.

**Definition of done (M5):** enter Adventure from the Base → fight enemies with equipment-
driven damage and weapon ailments → collect loot → level up mid-run → descend floors →
boss. All sprite-based, HUD active.

---

## 7. Phase 5 — Persistence (`savegame.py`)

Replace V3's text+pickle files with clean JSON. **Done in M3:** one flat
`saves/<name>.json` per character (stats, level, xp, upgrades, equipment and
backpack, items referenced by `item_id`) plus `saves/index.json` for the hero
list (the `saved_chars.txt` equivalent). Item references are stored by
`item_id` — catalog is code, saves are data, so no pickle problems.

**Still pending (with M4/M5):**
- `dungeon.json` — current floor seed, room state, defeated enemies, opened chests.
- In-run save triggers: leaving the Base mid-run, floor cleared, explicit *Save & Exit*.
  (Current triggers: on character creation; from the Base on Esc / Save & Exit / QUIT;
  from the other screens only on QUIT.)

---

## 8. Phase 6 — Polish & Testing

- **Polish:** hit flash + screen shake, death animation, chest sound + pop, level-up fanfare
  (optional, no audio dependency), consistent font/panel styling, game logo on title.
- **Tests (pytest, no display needed — headless `SDL_VIDEODRIVER=dummy`):**
  - Dungeon generation: room count, full connectivity, no overlap, corridor presence.
  - Item system: stat math (base + equipment), weight/overload, rarity roll, equip/unequip
    round-trip.
  - Level-up: XP curve, multi-level carry-over, stat pick persistence.
  - Save/load: character + inventory round-trip; corrupt-save handling.
  - Combat: damage formula, ailment tick damage, stun skip.

---

## 9. Milestones

| # | Milestone | Contents | Status |
|---|-----------|----------|--------|
| M1 | **Sprites everywhere** | Phase 1 (tileset, player/enemy/item/UI sprites, asset manager) | ✅ done |
| M2 | **Item system** | Phase 2 (full catalog, equipment, weight, rarity) — six sub-milestones in build order, see §4.5 | 🚧 partial — sub-milestones 1-2 (weapons + armor, all tiers) done: 113-item catalog; next: sub-milestone 3 (consumables) |
| M3 | **GUI up to the Base** | Phase 3 (title → tutorial → maker/chooser → Base → inventory/stats/level-up) | ✅ done (16 Oct 2026) — full GUI flow + JSON saves, 32-check end-to-end smoke test passing |
| M4 | **Dungeon + Combat** | Phase 4 (collision, fog, loot, enemies, weapon ailments, HUD) | pending |
| M5 | **Persistence + Polish** | Phases 5 + 6 (JSON saves, balance config, tests) | pending (JSON saves already in place) |

> **Known issue from M2 sub-milestone 2:** armor items can be selected in the inventory UI
> but cannot be equipped (slot mismatch — details and fix plan in `Handoff.md` §0).
> Unreachable in normal play until armor drops (M4); fix folded into sub-milestone 6 (wiring).

**Suggested build order:** M1 → M3 → M2 → M4 → M5.
(Why: M3 works with a tiny starter item set; M2's full catalog then just appears in the already-
finished inventory UI. M4 needs M2's weapon effects to be meaningful.)

---

## 10. Open Questions / Notes

- **Art source:** hand-drawn vs. free CC0 packs vs. generated placeholders first? (Plan assumes
  generated/free placeholders now, real art swappable later via stable filenames.)
- **Combat feel:** real-time (current movement model) vs. turn-based (V3 text game was
  turn-based). Plan assumes real-time with cooldowns — decide before M4.
- **Base content:** does the Base get a shop or crafting later? (Out of scope for "up to the
  Base" but the hub screen is structured to host it.)
- Keep `RPG_V3/` as read-only reference; all new code lives in `pygame_rpg/`.
- Environment: always use `.\venv\Scripts\python.exe -m pygame_rpg.main` (Python 3.14 +
  `pygame-ce`); add `pytest` to the venv for M5 tests.
