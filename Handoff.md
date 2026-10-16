# Project Handoff

## 1. Current State

* **Milestones M1 + M3 complete** (see `Plan.md` §9): M1 "Sprites everywhere" and M3 "GUI up to the Base".
  The game now runs the full pre-adventure flow in the GUI: title → tutorial → hero maker / hero
  chooser → Base (lobby) → inventory / stats / level-up, with JSON saves.
* `pygame_rpg/main.py` – rewritten for M3 as the state machine: module-level
  `build_screen(name, display, kwargs)` factory, per-event screen switching, global clock loop.
  The M1 dungeon loop (animated player, camera, WASD) no longer lives in `main.py` (recoverable
  from git); `dungeon.py` + `assets.py` are dormant, kept for Phase 4 (M4).
* GUI under `pygame_rpg/gui/`: shared `screen.py` base (`Screen`, `Button`, cached fonts, palette,
  `QUIT` sentinel) plus 8 screens: `title_screen`, `tutorial_screen`, `hero_maker`, `hero_chooser`,
  `base_screen`, `inventory_screen`, `stats_screen`, `level_up_screen`.
* Data modules: `config.py` (800×600, FPS, starting stats, XP curve, `BASE_MAX_WEIGHT=50`, save dir),
  `player.py` (`Player`: stats, XP/level-up, equipment, JSON round-trip), `items.py` (21-item starter
  catalog: 20 weapons + healing potion; `item_by_id()` returns copies), `savegame.py` (one JSON per
  character + `saves/index.json`, names validated against `^[\w .-]{1,20}$`).
* `pygame_rpg/assets/` unchanged from M1: placeholder art generated on first load, stable filenames
  so real art can be dropped in later.
* All logic is written in pure Python and uses the `pygame` library (pygame‑ce).

## 2. Learned Points

1. **Headless pygame** – Setting `SDL_VIDEODRIVER=dummy` (plus `SDL_AUDIODRIVER=dummy`) before
   `pygame.init()` lets the whole game run on a machine with no display. The game draws to real
   `pygame` surfaces and `convert()`s normally, so this also catches real rendering bugs; it just
   never shows a window. This is how M1's "run the game, see the dungeon" acceptance check is
   verified.
2. **`pygame-ce` for Python 3.14** – Plain `pygame` 2.6.1 ships no wheel for CPython 3.14, so the
   venv uses `pygame-ce` (community edition) 2.5.8 instead. It is API‑compatible with `pygame`
   (import name is still `pygame`); nothing in the code needs to change.
3. **V3 is a text‑UI reference, not a codebase to extend** – `RPG_V3/main_V3.py` is one big file of
   `print()`/`input()` functions with all data in module‑level dicts and `None`/stub bodies
   (`lobby()`, `inventory()`, `backpack()`). It is the spec for mechanics and flow; the pygame game
   re‑implements it as real classes (see `Plan.md` "Rule of thumb").
4. **Asset manager pattern** – `pygame_rpg/assets.py` loads from `pygame_rpg/assets/` and, when a
   file is missing, generates a placeholder programmatically **and saves it to disk** under the same
   name. First run populates the folder; later real art dropped in replaces placeholders
   automatically. This keeps "sprites everywhere" achievable without real art on day one.
5. **V3 mechanics to preserve** – Six combat stats: `attack`, `attack_range`, `attack_magic`,
   `defense`, `defense_range`, `defense_magic`; `hp` + `level` + `xp`; `max_xp = level * 100`;
   starting stats are level 1, 0 xp, 100 HP, and 5 in each of the six combat stats. Level‑up gives
   1 point to a chosen stat (V3 `xp_check`). Weapons split into melee/range/magic × sharp/dull/
   poison/fire/electric (the `WP*` subclasses), each with an unimplemented `effect()` — a combat
   hook for M4.
6. **`dungeon.py` already does M1's heavy lifting** – rectangular rooms + corridor linking +
   tilemap rendering + minimap exist and run; M1 only added the sprite/asset layer around them.
7. **Run command** – `.\venv\Scripts\python.exe -m pygame_rpg.main` from the repo root.
8. **Screen transition protocol (M3)** – Screens never reference each other: `handle_event` returns
   `None` (stay), the `QUIT` sentinel, `"screen_name"`, or `("name", {kwargs})`; the state machine in
   `main.py` does the swapping. `QUIT` is a sentinel **object** (a `_Quit` instance with no `__eq__`)
   — compare with `is`, never `==` or a string.
9. **V3 gaps filled by design (M3)** – V3's `lobby()`/`inventory()`/`backpack()` are stubs and it
   references `weight`/`max_weight` without defining them → Base/inventory built to the `Plan.md`
   Phase 3 spec with `BASE_MAX_WEIGHT = 50`. V3 has **no rarity data** (grep‑confirmed) → inventory
   slot borders are colored by item kind, not rarity. Level‑up triggers at `xp >= max_xp` (V3 used
   strict `>`).
10. **Saves (M3)** – One JSON per character: `saves/<name>/character.json` + `saves/index.json`;
    `savegame._safe_name()` raises `ValueError` on bad names; `item_by_id()` returns a **copy** so
    per‑character state can't mutate the catalog; `save_player()` runs on Esc, Save & Exit, and
    QUIT from every screen.
11. **Level‑up flow (M3)** – `BaseScreen.pending_levels(player)` counts pending levels read‑only
    without banking; while pending > 0 the Base activates **only** "Choose Stat". The level‑up
    screen banks one stat per click and returns to Base only when pending hits 0; Esc returns with
    no banking.
12. **Headless testing extended (M3)** – Chunk harnesses live in
    `C:\Users\lucka\AppData\Local\Temp\opencode\` (`m3_chunk1_test.py` … `m3_chunk7_test.py`). They
    set `SDL_VIDEODRIVER=dummy` + `SDL_AUDIODRIVER=dummy` **before** `pygame.init()` and need
    `$env:PYTHONPATH=<repo root>` (Python puts the script's dir on `sys.path`, not the CWD).
    Latest baseline: `m3_chunk7_test.py` → "chunk7 OK" (32 checks, end‑to‑end: new‑hero route,
    saved‑hero route, level‑up banking, save round‑trip).

## 3. Next Steps

Milestones follow `Plan.md`; build order is **M1 → M3 → M2 → M4 → M5**. M1 and M3 are done;
**M2 is next**.

1. **Local setup** – ✅ Done. `venv/` (Python 3.14.7) has `pygame-ce` 2.5.8 installed; run the game
   with `.\venv\Scripts\python.exe -m pygame_rpg.main`. `pygame-ce` is required on Python 3.14
   because `pygame` 2.6.1 has no matching wheel.
2. **M1 – Sprites everywhere** – ✅ Done. Tileset‑based dungeon rendering, animated hero sheet,
   enemy/item/UI placeholder sprites, and the asset manager are in place; verified headless
   (Learned Points 1, 4, 6).
3. **M3 – GUI up to the Base** – ✅ Done (16 Oct 2026). Full flow in the GUI: title → tutorial →
   hero maker (two‑stage name input + confirm) → hero chooser (paged saved list) → Base hub →
   inventory (equip/unequip/use/drop + weight bar) → stats → level‑up (bank one stat at a time).
   JSON saves per character + index. Verified headless with a 32‑check end‑to‑end smoke test; see
   the completion note in `Plan.md` §5.
4. **M2 – Item system** (next up) – Grow the 21‑item starter catalog in `items.py` into the full
   multi‑tier catalog per `Plan.md` §4: armor (head/torso/hands/feet), consumables with charges,
   trinkets (2 slots), abilities, level‑2+ weapon tiers, and rarity data (common/rare/epic/
   legendary → UI border colors + spawn weights). Equipment math and the weight system already
   exist from M3.
5. **M4 – Dungeon + Combat** – Revive the M1 crawler (`dungeon.py`/`assets.py` are untouched): wall
   collision, fog of war, loot, enemies/bosses, weapon ailments (V3 `WP` hierarchy), HUD; wire the
   Base's "Adventure" button to it.
6. **M5 – Persistence + Polish** – JSON character saves ✅ already in place; remaining: dungeon
   state in saves, balance config, pytest suite (add `pytest` to the venv).

## 4. Deliverables

* `pygame_rpg/` – current code: `main.py` (M3 state machine), `config.py`, `player.py`, `items.py`,
  `savegame.py`, `gui/` (9 files), plus M1's `dungeon.py`, `assets.py`, `README.md`.
* `pygame_rpg/assets/` – generated placeholder sprites; lazy, overridable with real art.
* `saves/` – created at runtime: one JSON per character + `index.json`.
* `RPG_V3/` – the text‑mechanics reference (ported up to the Base in M3; remaining reference for
  M2–M4).
* `Plan.md` – master plan (phases, milestones M1–M5 with status, build order M1 → M3 → M2 → M4 → M5).
* `venv/` – virtual environment (Python 3.14.7) with `pygame-ce` 2.5.8 installed.
* `Handoff.md` – this document.
* `README.md` – usage instructions.

Feel free to pick up any of the next steps above. Happy coding!
