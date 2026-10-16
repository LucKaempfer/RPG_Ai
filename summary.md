# RPG_AI – Summary of RPG_V2 and RPG_V3 Design

## 1. Overview
The repository contains two major iterations of a text‑based roguelike dungeon‑battler: **RPG_V2** and the newer **RPG_V3**. Both versions are written in Python and run in a terminal, but RPG_V3 introduces a more structured object‑oriented design and expanded game mechanics.

## 2. RPG_V2 Design (as previously summarised)

| Component | File | Responsibility |
|-----------|------|----------------|
| **Main Loop** | `RPG_V2_Main.py` | Handles user input, state transitions, and high‑level flow (character creation, adventure selection, inventory management). |
| **Data Models** | `assets_V2.py` | Defines `item`, `enemy`, and `room` classes and populates lists for items, enemies, and rooms for each map. |
| **State** | `RPG_V2_Main.py` (global dicts) | `char_stats`, `lvl_up_stats`, `adv_stats` store character stats, level‑up gains, and adventure configuration. |
| **Persistence** | Text/Pickle files | Character data (`*.txt`, `*_hidden.txt`), inventory (`*_inventory.pkl`), and equipped items (`*_equipped.pkl`). |
| **Utilities** | `tutorial.txt`, `saved_characters.txt` | Provide guidance and a record of saved characters. |

### 2.1 Game Flow
1. **Start** – Optional tutorial → choose new or saved character.
2. **Main Menu** – `inventory`, `adventure`, `view stats`, `exit`.
3. **Inventory** – view, equip, unequip, pick up loot, view stats. Items modify character stats when equipped.
4. **Adventure** – pick map (Dungeon/Castle/Laboratory) and difficulty (easy/normal). Unlocks depend on character level.
5. **Turn‑Based Combat** – Placeholder; `adventure()` would iterate through rooms and enemies.
6. **Leveling** – On XP gain, player selects a stat to increase; upgrades tracked in `lvl_up_stats`.
7. **Exit** – Saves character, inventory, and equipment.

### 2.2 Planned Features
- Full combat system.
- Room types (`gear`, `food`, `boss`, `loot`, `enemy`).
- Map progression at level thresholds.
- Difficulty scaling.
- Expanded items/enemies.
- No graphical UI.

### 2.3 Suggested Next Steps
1. Implement `adventure()` logic.
2. Expand `assets_V2.py`.
3. Persist adventure state.
4. Refactor into classes (`Game`, `Character`, `Adventure`).
5. Add unit tests.

---

## 3. RPG_V3 Design
RPG_V3 represents a refactored iteration with a clearer separation of concerns, more comprehensive data classes, and a foundation for future features such as abilities, consumables, and more nuanced combat.

### 3.1 Core Architecture
| Component | File | Responsibility |
|-----------|------|----------------|
| **Main Loop** | `main_V3.py` | Orchestrates game start, tutorial, character creation/selection, and the overall game loop. Uses global dictionaries for character stats and equipment inventory. |
| **Weapon & Item Classes** | `assets_V3.py` | Introduces a `WP` base class and specialized subclasses for melee, ranged, and magic weapons (e.g., `WP_melee_sharp`, `WP_range_dull`). Each weapon defines an `effect()` method placeholder for future combat logic. Also defines skeletal classes for `Consumable`, `Armor`, `Trinket`, `Ability`, `Enemy`, and `Boss`. |
| **Data Persistence** | Text & Pickle files | Similar to V2: character files (`*.txt`, `*_hidden.txt`), inventory (`*_inventory.pkl`), equipment (`*_equipment.pkl`). |
| **Utilities** | `tutorial.txt` | Brief introductory text explaining the game mechanics. |

### 3.2 Game Flow (as implemented)
1. **Tutorial** – Optional, displays text from `tutorial.txt`.
2. **Character Creation** – `hero_maker()` creates character files and initializes basic gear in inventory. It also prevents duplicate names.
3. **Character Selection** – `hero_chooser()` (incomplete) would load an existing character.
4. **Main Game Loop** – `start()` decides between new or saved hero and would then lead into gameplay (not fully implemented).
5. **Inventory Management** – Functions `inventory()`, `backpack()`, `xp_check()` provide placeholders for inventory interactions and level‑up logic.

### 3.3 Notable Design Choices
- **Object‑Oriented Weapon System**: Weapons now inherit from a common base, allowing polymorphic `effect()` behavior.
- **Weight & Capacity**: The `backpack()` function references `weight` and `max_weight` variables (currently undefined), hinting at future load‑based stat changes.
- **Extensible Class Skeletons**: Classes for consumables, armor, trinkets, abilities, enemies, and bosses exist but lack implementation, providing a scaffold for future development.

### 3.4 Planned Features for RPG_V3
- Implement `effect()` logic for weapon subclasses.
- Complete `hero_chooser()` to load characters.
- Develop a robust combat system using weapon effects and enemy classes.
- Add weight handling and inventory limits.
- Flesh out consumables, armor, trinkets, abilities, and boss mechanics.
- Introduce a persistent adventure state (current map, rooms visited, enemies defeated).
- Create a more user‑friendly interface (menus, prompts, error handling).

---

*This combined summary covers the current state of the `RPG_V2` (located at `C:\Users\lucka\Documents\coding\RPG_V2`) and the newer `RPG_V3` (located at `C:\Users\lucka\Documents\coding\RPG_V3`).*
