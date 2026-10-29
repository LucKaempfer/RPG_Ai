# Dungeon RPG (pygame)

A 2-D, sprite-based dungeon battler. You create a hero, gear them up in the Base, and fight your
way down generated floors in turn-based battles.

## How to run

```bash
# Python 3.9+; on Python 3.14 use pygame-ce (plain pygame 2.6.1 has no 3.14 wheel).
pip install -r requirements.txt

# From the repo root:
python -m pygame_rpg.main

# Tests (headless):
python -m pytest
```

## Controls

* Menus: mouse, or Up / Down + Enter; Esc goes back.
* Dungeon: arrows / WASD to walk, bump into an enemy to fight, Esc returns to the Base (the run
  is kept: *Continue (Floor N)*).
* Battle: Attack / Abilities / Items / Run.

Everything else (architecture, rules, numbers, roadmap) is in `DEVELOPMENT.md` at the repo root.
