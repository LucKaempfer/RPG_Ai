# pygame_rpg/gui/base_screen.py
"""Base / Lobby screen (port of the V3 lobby()) — the in-game hub.

On entry it runs the V3 xp_check() equivalent *in read-only mode*:
pending level-ups are counted but not banked, so nothing is lost if
the player wanders off before resolving them.  The actual level-up
(banking XP and picking stats) happens on the level-up screen.

Buttons: Inventory, View Stats, Journal (the story so far), Adventure, Settings, Save & Exit.  With a saved
dungeon run (M5) the Adventure button reads "Continue (Floor N)" and
resumes it as it was (HP included), and an extra New Adventure button
drops it.  A new adventure starts rested (full HP / MP) on floor 1.
Mouse or keyboard (Up / Down + Enter).  Escape auto-saves and returns
to the title screen.
"""

import pygame

from ..assets import AssetManager, gear_of, upscale
from ..classes import class_name
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT, RUN_VERSION, max_xp_for
from ..savegame import save_player, load_run, delete_run
from ..stat_names import TYPES, ATTACK, DEFENSE
from .effects import menu_key
from .screen import (
    draw_bar, draw_background, draw_panel, QUIT, Screen, Button, font,
    TEXT_COLOR, DIM_TEXT, GOLD,
)



def pending_levels(player) -> int:
    """How many level-ups the current xp would grant (pure, no mutation).

    Uses the >= semantics of Player.add_xp: reaching exactly max_xp
    counts as a level-up.
    """
    xp, lvl, ups = player.xp, player.lvl, 0
    while xp >= max_xp_for(lvl):
        xp -= max_xp_for(lvl)
        lvl += 1
        ups += 1
    return ups


class BaseScreen(Screen):
    name = "base"

    def __init__(self, screen, player):
        super().__init__(screen)
        self.player = player
        self.pending_ups = pending_levels(player)
        self.hot = None
        self.focus = None

        # Portrait: first idle frame of the hero sheet, scaled up 4x.
        frame = AssetManager().hero_frames(
            player.look, gear_of(player.equipment))[0]
        self.portrait = upscale(frame, 128, outline=True)

        self.run = load_run(player.name)
        if self.run is not None and self.run.get("version") != RUN_VERSION:
            # Saved by an older dungeon generator: the seed no longer
            # builds the same floor, so the run can't be continued.
            delete_run(player.name)
            self.run = None
        x, w, h, step = 420, 340, 42, 47
        self.btn_inventory = Button("Inventory", (x, 84, w, h))
        self.btn_stats = Button("View Stats", (x, 84 + step, w, h))
        self.btn_journal = Button("Journal", (x, 84 + 2 * step, w, h))
        label = (f"Continue (Floor {self.run['floor']})" if self.run
                 else "Adventure")
        self.btn_adventure = Button(label, (x, 84 + 3 * step, w, h))
        self.btn_new_run = Button("New Adventure", (x, 84 + 4 * step, w, h))
        self.btn_settings = Button("Settings", (x, 84 + 5 * step, w, h))
        self.btn_saveexit = Button("Save & Exit", (x, 84 + 6 * step, w, h))
        self.btn_choose = Button("Choose Stat", (x, 458, w, 52), size=28)

    # -- helpers ---------------------------------------------------------
    def _active_buttons(self):
        """Buttons that react to input; the rest are drawn disabled."""
        if self.pending_ups > 0:
            return [self.btn_choose]
        return [b for b in self._menu() if b is not self.btn_new_run or self.run]

    def _menu(self):
        return (self.btn_inventory, self.btn_stats, self.btn_journal, self.btn_adventure,
                self.btn_new_run, self.btn_settings, self.btn_saveexit)

    def _hover(self, pos):
        for btn in self._active_buttons():
            if btn.rect.collidepoint(pos):
                return btn
        return None

    def _save(self):
        save_player(self.player)

    # -- Screen hooks ------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self._save()
            return QUIT
        if event.type == pygame.MOUSEMOTION:
            self.hot = self._hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._press(self._hover(event.pos))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._save()
            return "title"
        elif event.type == pygame.KEYDOWN:
            active = self._active_buttons()
            self.focus, activate = menu_key(event, len(active), self.focus)
            if self.focus is not None:
                self.hot = active[self.focus]
            if activate:
                return self._press(active[self.focus])
        return None

    def _press(self, btn):
        if btn is self.btn_choose:
            return ("level_up", {"player": self.player})
        if btn is self.btn_inventory:
            return ("inventory", {"player": self.player})
        if btn is self.btn_stats:
            return ("stats", {"player": self.player})
        if btn is self.btn_journal:
            return ("journal", {"player": self.player})
        if btn is self.btn_adventure and self.run:
            self._save()
            return ("dungeon", {"player": self.player, "run": self.run})
        if btn is self.btn_adventure or btn is self.btn_new_run:
            delete_run(self.player.name)
            self.player.rest()
            self._save()
            return ("dungeon", {"player": self.player})
        if btn is self.btn_settings:
            return ("settings", {"return_to": self})
        if btn is self.btn_saveexit:
            self._save()
            return QUIT
        return None

    def draw(self, surface):
        draw_background(surface)
        p = self.player

        header = font(32).render(
            f"Welcome in your Base, {p.name}.", True, GOLD)
        surface.blit(header, header.get_rect(midtop=(SCREEN_WIDTH // 2, 24)))

        # Left panel: portrait + summary.
        panel = pygame.Rect(30, 80, 330, 440)
        draw_panel(surface, panel, radius=8)

        surface.blit(self.portrait, (45, 100))
        name = font(28).render(p.name, True, TEXT_COLOR)
        surface.blit(name, name.get_rect(midtop=(panel.centerx, 245)))
        lvl = font(22).render(f"Level {p.lvl} {class_name(p)}", True, DIM_TEXT)
        surface.blit(lvl, lvl.get_rect(midtop=(panel.centerx, 278)))

        # XP bar.
        bar = pygame.Rect(panel.centerx - 100, 305, 200, 12)
        draw_bar(surface, bar, p.xp, p.max_xp, GOLD)
        xpt = font(18).render(f"XP {p.xp} / {p.max_xp}", True, DIM_TEXT)
        surface.blit(xpt, xpt.get_rect(midtop=(panel.centerx, 324)))

        # Health and mana, then attack / defense per type as a table.
        cx = panel.centerx
        hm = font(20).render(f"Health {p.current_hp}/{p.max_hp}     "
                             f"Mana {p.current_mp}/{p.max_mp}", True, TEXT_COLOR)
        surface.blit(hm, hm.get_rect(midtop=(cx, 350)))
        cols = (cx + 30, cx + 110)
        for x, head in zip(cols, ("Attack", "Defense")):
            img = font(18).render(head, True, DIM_TEXT)
            surface.blit(img, img.get_rect(midtop=(x, 378)))
        for row, kind in enumerate(TYPES):
            y = 400 + row * 24
            label = font(20).render(kind.capitalize(), True, DIM_TEXT)
            surface.blit(label, label.get_rect(topright=(cx - 30, y)))
            for x, stat in zip(cols, (ATTACK[kind], DEFENSE[kind])):
                img = font(20).render(str(p.total(stat)), True, TEXT_COLOR)
                surface.blit(img, img.get_rect(midtop=(x, y)))
        wt = font(18).render(
            f"Weight {p.weight} / {p.max_weight}    Gold {p.gold}", True, DIM_TEXT)
        surface.blit(wt, wt.get_rect(midbottom=(panel.centerx, panel.bottom - 12)))

        # Right: menu buttons.
        active = set(map(id, self._active_buttons()))
        for btn in self._menu():
            if btn is self.btn_new_run and not self.run:
                continue
            if id(btn) in active:
                btn.draw(surface, hot=(btn is self.hot))
            else:
                self._draw_disabled(surface, btn, "")
        if self.pending_ups > 0:
            note = font(26).render(
                f"LEVEL UP! ({self.pending_ups} pending)", True, GOLD)
            surface.blit(note, note.get_rect(
                midtop=(self.btn_choose.rect.centerx, 424)))
            self.btn_choose.draw(surface, hot=(self.btn_choose is self.hot))
        hint = font(18).render(
            "Up/Down + Enter or click.  Esc: save & return to title", True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(
            SCREEN_WIDTH - 20, SCREEN_HEIGHT - 14)))

    def _draw_disabled(self, surface, btn, suffix):
        """Draw a button in its inactive state (no input, dimmed)."""
        pygame.draw.rect(surface, (30, 30, 42), btn.rect, border_radius=6)
        pygame.draw.rect(surface, (60, 60, 80), btn.rect,
                         width=2, border_radius=6)
        text = font(btn.font_size).render(btn.label + suffix, True, DIM_TEXT)
        surface.blit(text, text.get_rect(center=btn.rect.center))
