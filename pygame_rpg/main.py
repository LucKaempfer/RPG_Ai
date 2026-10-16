# pygame_rpg/main.py
"""M3 entry point: the pre-dungeon flow, run inside the GUI.

Flow: Title -> Tutorial -> Hero Maker -> Hero Chooser -> Base,
with the Base branching into Inventory, Stats and Level-Up.

Screens never reference each other directly.  Each one's
``handle_event`` returns a transition request (``None``, the ``QUIT``
sentinel, a screen name string, or a ``(name, kwargs)`` tuple) and
this state machine performs the actual swap.

The M1 dungeon demo loop is kept in git history; ``dungeon.py`` and
``assets.py`` stay available for the Phase 5 adventure.
"""

import pygame

from . import config
from .gui.screen import QUIT
from .gui.title_screen import TitleScreen
from .gui.tutorial_screen import TutorialScreen
from .gui.hero_maker import HeroMakerScreen
from .gui.hero_chooser import HeroChooserScreen
from .gui.base_screen import BaseScreen
from .gui.inventory_screen import InventoryScreen
from .gui.stats_screen import StatsScreen
from .gui.level_up_screen import LevelUpScreen


def build_screen(name, display, kwargs=None):
    """Construct the screen called ``name`` with ``kwargs`` as its
    constructor keyword arguments (the transition payload)."""
    kwargs = kwargs or {}
    if name == "title":
        return TitleScreen(display)
    if name == "tutorial":
        return TutorialScreen(display, next=kwargs.get("next", "hero_maker"))
    if name == "hero_maker":
        return HeroMakerScreen(display)
    if name == "hero_chooser":
        return HeroChooserScreen(display)
    if name in ("base", "inventory", "stats", "level_up"):
        player = kwargs.get("player")
        if name == "base":
            return BaseScreen(display, player)
        if name == "inventory":
            return InventoryScreen(display, player)
        if name == "stats":
            return StatsScreen(display, player)
        return LevelUpScreen(display, player)
    raise ValueError(f"unknown screen name: {name!r}")


def main():
    pygame.init()
    screen = pygame.display.set_mode(
        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    )
    pygame.display.set_caption("Dungeon Crawler")
    clock = pygame.time.Clock()

    current = TitleScreen(screen)
    while True:
        for event in pygame.event.get():
            result = current.handle_event(event)
            if result is QUIT:          # sentinel object: identity check
                pygame.quit()
                return
            if result is None:          # stay on the current screen
                continue
            if isinstance(result, tuple):
                name, kwargs = result
            else:
                name, kwargs = result, {}
            current = build_screen(name, screen, kwargs)

        dt = clock.tick(config.FPS) / 1000.0
        current.handle_update(dt)
        current.draw(screen)
        pygame.display.flip()


if __name__ == "__main__":
    main()
