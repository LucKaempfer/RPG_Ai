# pygame_rpg/main.py
"""Entry point: the state machine that runs every GUI screen.

Flow: Title -> Tutorial -> Hero Maker -> Hero Chooser -> Base,
with the Base branching into Inventory, Stats, Level-Up and the
Dungeon (Adventure).

Screens never reference each other directly.  Each one's
``handle_event`` (and, for things that happen on their own such as
bumping into an enemy, ``handle_update``) returns a transition request
(``None``, the ``QUIT`` sentinel, a screen name string, or a
``(name, kwargs)`` tuple) and this state machine performs the actual
swap.  ``("resume", {"screen": s})`` switches back to an existing
screen object ``s`` instead of building a new one (the dungeon keeps
its floor while a battle or level-up screen is shown).

``dungeon.py`` and ``assets.py`` (the M1 crawler) back the M4
adventure in ``gui/dungeon_screen.py``.

Sound: ``audio.py`` synthesises every effect at start-up; screens call
``audio.play`` for their actions and declare an ``ambience`` (the loop
played while they are shown).  M toggles mute.

Window: screens draw on a fixed 800 x 600 canvas; ``gui/display.py``
scales it into a resizable window (F11: fullscreen) and maps the mouse
back onto the canvas.

Settings (``settings.py``, ``gui/settings_screen.py``): brightness,
volumes, fullscreen and the dungeon keys, saved in
``saves/settings.json``; reached from the title screen and the Base.
"""

import pygame

from . import audio, config, settings
from .gui.display import Display
from .gui.screen import QUIT
from .gui.title_screen import TitleScreen
from .gui.tutorial_screen import TutorialScreen
from .gui.hero_maker import HeroMakerScreen
from .gui.hero_chooser import HeroChooserScreen
from .gui.base_screen import BaseScreen
from .gui.inventory_screen import InventoryScreen
from .gui.stats_screen import StatsScreen
from .gui.level_up_screen import LevelUpScreen
from .gui.dungeon_screen import DungeonScreen
from .gui.battle_screen import BattleScreen
from .gui.shop_screen import ShopScreen
from .gui.forge_screen import ForgeScreen
from .gui.settings_screen import SettingsScreen


def build_screen(name, display, kwargs=None):
    """Construct the screen called ``name`` with ``kwargs`` as its
    constructor keyword arguments (the transition payload)."""
    kwargs = kwargs or {}
    if name == "resume":
        return kwargs["screen"]
    if name == "title":
        return TitleScreen(display)
    if name == "tutorial":
        return TutorialScreen(display, next=kwargs.get("next", "hero_maker"))
    if name == "hero_maker":
        return HeroMakerScreen(display)
    if name == "hero_chooser":
        return HeroChooserScreen(display)
    if name == "settings":
        return SettingsScreen(display, return_to=kwargs.get("return_to"))
    if name in ("base", "inventory", "stats", "level_up", "dungeon",
                "battle", "shop", "forge"):
        player = kwargs.get("player")
        if name == "base":
            return BaseScreen(display, player)
        if name == "inventory":
            return InventoryScreen(display, player,
                                   return_to=kwargs.get("return_to"))
        if name == "stats":
            return StatsScreen(display, player)
        if name == "shop":
            return ShopScreen(display, player, kwargs["stock"], kwargs["sold"],
                              return_to=kwargs.get("return_to"))
        if name == "forge":
            return ForgeScreen(display, player, return_to=kwargs.get("return_to"))
        if name == "battle":
            return BattleScreen(display, player, kwargs["enemy"],
                                kwargs["dungeon"])
        if name == "dungeon":
            return DungeonScreen(display, player,
                                 floor=kwargs.get("floor", 1),
                                 seed=kwargs.get("seed"),
                                 run=kwargs.get("run"))
        return LevelUpScreen(display, player,
                             return_to=kwargs.get("return_to"))
    raise ValueError(f"unknown screen name: {name!r}")


def main():
    audio.pre_init()
    pygame.init()
    audio.init()
    settings.load()
    display = Display()
    screen = display.canvas
    pygame.display.set_caption("Dungeon Crawler")
    clock = pygame.time.Clock()

    current = TitleScreen(screen)

    def switch(result):
        """Apply a transition request; returns the screen to run next,
        or QUIT."""
        if result is QUIT or result is None:   # QUIT: identity check
            return result
        if isinstance(result, tuple):
            name, kwargs = result
        else:
            name, kwargs = result, {}
        return build_screen(name, screen, kwargs)

    while True:
        for event in pygame.event.get():
            event = display.handle_event(event)
            if event is None:
                continue
            # M mutes everywhere except while typing a hero name.
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_m
                    and current.name != "hero_maker"):
                audio.toggle_mute()
                continue
            nxt = switch(current.handle_event(event))
            if nxt is QUIT:
                pygame.quit()
                return
            current = nxt or current

        dt = clock.tick(config.FPS) / 1000.0
        nxt = switch(current.handle_update(dt))
        if nxt is QUIT:
            pygame.quit()
            return
        current = nxt or current
        audio.set_ambience(current.ambience)
        audio.update(dt)
        current.draw(screen)
        display.present()


if __name__ == "__main__":
    main()
