# Pygame RPG Skeleton

This repository contains a minimal 2‑D dungeon crawler built with **Pygame**.

## Features

- Procedurally generated dungeon with rooms and corridors.
- Player movement with arrow keys / WASD.
- Minimap in the top left corner showing visited rooms.
- Basic tile‑based rendering (walls, floor, doors).

## How to run

```bash
# Ensure you have Python 3.9+ and a pygame variant installed.
# On Python 3.14 use pygame-ce (drop-in replacement; plain pygame 2.6.1
# has no prebuilt wheel for 3.14):
pip install pygame-ce

# Run the game
python -m pygame_rpg.main
```

The game starts in the first generated room. Walk around to explore.

## Extending the game

- **Add combat** – create `Enemy` and `Item` classes.
- **Add inventory UI** – draw a panel and handle item pickup.
- **Improve graphics** – replace colored squares with spritesheets.

Happy hacking!
