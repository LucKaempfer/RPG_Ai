# pygame_rpg/gui/battle_screen.py
"""Battle screen (M4): one turn-based fight, drawn over ``combat.Battle``.

Top right: the enemy (sprite x4, HP bar, ailments).  Left: the hero
(back view x4, HP / MP bars, ailments, shield).  Bottom left: the
battle log.  Bottom right: the menu.

Menu: Attack / Abilities / Items / Run.  Attack opens the attack styles
(Strike / Slash / Bash / Heavy), Abilities the 4 ability slots with MP
cost and cooldown, Items the backpack's battle consumables; Back or Esc
returns to the main menu.  Every damaging entry shows the damage it
would deal now, and the hero panel shows the enemy's next hit.  Mouse
or keyboard (Up / Down / Enter, Esc).

When the fight ends the menu becomes one Continue button:
won / fled -> back to the same dungeon floor (``resume``); lost -> the
hero is carried back to the Base and rests (full HP / MP); the run
is over (its save is deleted).
"""

import random

import pygame

from .. import audio
from ..assets import (
    AssetManager, HERO_COLS, HERO_ROWS, HERO_IDLE_COLS, HERO_DIR_UP,
    ENEMY_COLS, ENEMY_ROWS, ENEMY_IDLE, ENEMY_HURT, ENEMY_DEATH,
)
from ..combat import Battle, STYLES, AFFLICTED, ONGOING, WON, LOST, FLED
from ..config import SCREEN_WIDTH, SCREEN_HEIGHT
from ..savegame import save_player, delete_run
from .effects import Particles
from .screen import (
    QUIT, Screen, Button, font,
    BG_COLOR, PANEL_COLOR, TEXT_COLOR, DIM_TEXT, GOLD, BORDER_COLOR,
)

HP_COLOR = (200, 70, 70)
MP_COLOR = (80, 120, 220)
GOOD = (110, 200, 110)
BAD = (220, 110, 110)
LOG_LINES = 7
HURT_TIME = 0.35   # seconds a side shows it was hit (enemy hurt frames,
                   # hero red flash + shake)
SHAKE = 6          # pixels the hero sprite jolts when hit
POP_TIME = 1.0     # seconds a damage / heal number floats up
END_TIME = 0.8     # seconds the victory / defeat animation plays

MENU = ("Attack", "Abilities", "Items", "Run")


def _bar(surface, rect, value, maximum, color):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, (15, 15, 20), rect, border_radius=5)
    if maximum > 0 and value > 0:
        fill = rect.copy()
        fill.w = max(2, int(rect.w * min(value, maximum) / maximum))
        pygame.draw.rect(surface, color, fill, border_radius=5)
    pygame.draw.rect(surface, BORDER_COLOR, rect, width=1, border_radius=5)


class BattleScreen(Screen):
    name = "battle"
    ambience = "sewer"   # the fight happens down in the sewer

    def __init__(self, screen, player, enemy, dungeon, rng=None):
        super().__init__(screen)
        self.player = player
        self.enemy = enemy
        self.dungeon = dungeon          # the DungeonScreen to resume
        self.battle = Battle(player, enemy, rng or random.Random())
        self.mode = "main"              # "main" | "abilities" | "items"
        self.focus = 0
        self.hot = None
        self.anim_t = 0.0
        self.hurt_t = 0.0
        self.hero_hurt_t = 0.0
        self.pops = []      # [text, color, x, y, age]: floating numbers
        self.fx = Particles()
        self.end_t = None   # seconds since the fight ended (animations)
        self.panel_log = pygame.Rect(24, 404, 470, 176)
        self.panel_menu = pygame.Rect(510, 404, 266, 176)

        assets = AssetManager()
        hero = assets.load_sheet("player/hero_sheet.png", HERO_COLS, HERO_ROWS)
        self.hero_frames = [
            pygame.transform.scale(hero[HERO_DIR_UP * HERO_COLS + c], (128, 128))
            for c in HERO_IDLE_COLS]
        size = 192 if enemy.boss else 128
        sheet = assets.load_sheet(f"enemies/{enemy.type.sprite}.png",
                                  ENEMY_COLS, ENEMY_ROWS)
        self.enemy_frames = [pygame.transform.scale(f, (size, size))
                             for f in sheet]
        self._build_buttons()

    # -- menu ----------------------------------------------------------
    def _entries(self):
        """(label, action, enabled) rows for the current menu."""
        b = self.battle
        if b.state != ONGOING:
            return [("Continue", ("continue",), True)]
        if self.mode == "attack":
            rows = []
            for key, st in STYLES.items():
                lo, hi = b.attack_preview(key)
                rows.append((f"{st.name} {lo}-{hi}  ({st.note})",
                             ("attack", key), True))
            return rows + [("Back", ("back",), True)]
        if self.mode == "abilities":
            rows = []
            for a in self.player.equipped_abilities():
                cd = b.cooldowns.get(a.id)
                tag = f"wait {cd}" if cd else f"{a.mp_cost} MP"
                dmg = b.cast_preview(a)
                hit = f" {dmg[0]}-{dmg[1]}" if dmg else ""
                rows.append((f"{a.name}{hit}  ({tag})", ("cast", a), b.can_cast(a)))
            return rows + [("Back", ("back",), True)]
        if self.mode == "items":
            rows = []
            for item in b.battle_items()[:4]:
                uses = f" x{item.charges}" if item.charges > 1 else ""
                rows.append((f"{item.name}{uses}", ("use", item),
                             b.can_use(item)))
            return rows + [("Back", ("back",), True)]
        lo, hi = b.attack_preview()
        return [
            (f"Attack  ({lo}-{hi})", ("mode", "attack"), True),
            ("Abilities", ("mode", "abilities"),
             bool(self.player.equipped_abilities())),
            ("Items", ("mode", "items"), bool(b.battle_items())),
            ("Run", ("run",), not self.enemy.boss),
        ]

    def _build_buttons(self):
        rows = self._entries()
        self.buttons = []
        h = min(34, (self.panel_menu.h - 16) // max(1, len(rows)) - 4)
        for i, (label, action, enabled) in enumerate(rows):
            rect = (self.panel_menu.x + 10, self.panel_menu.y + 8 + i * (h + 4),
                    self.panel_menu.w - 20, h)
            self.buttons.append((Button(label, rect, size=20), action, enabled))
        self.focus = min(self.focus, len(self.buttons) - 1)

    def _do(self, action):
        b = self.battle
        kind = action[0]
        hp_before = self.enemy.hp
        hero_before = self.player.current_hp
        out = []
        if kind == "continue":
            audio.play("click")
            return self._leave()
        if kind == "mode":
            self.mode, self.focus = action[1], 0
        elif kind == "back":
            self.mode, self.focus = "main", 0
        elif kind == "attack":
            out = b.attack(action[1] if len(action) > 1 else "strike")
            self.mode = "main"
        elif kind == "cast":
            out = b.cast(action[1])
            self.mode = "main"
        elif kind == "use":
            out = b.use_item(action[1])
            self.mode = "main"
        elif kind == "run":
            out = b.run()
        self._sounds(action, out, hp_before, hero_before)
        if self.enemy.hp < hp_before:
            self.hurt_t = HURT_TIME
            self._pop(f"-{hp_before - self.enemy.hp}", BAD, 590, 170)
        lost = hero_before - self.player.current_hp
        if lost > 0:
            self.hero_hurt_t = HURT_TIME
            self._pop(f"-{lost}", BAD, 134, 200)
        elif lost < 0:
            self._pop(f"+{-lost}", GOOD, 134, 200)
        if b.state != ONGOING and self.end_t is None:
            self.end_t = 0.0
            if b.state == WON:
                self.fx.burst(590, 270, GOLD, count=28, speed=180)
                self.fx.burst(590, 270, (255, 255, 255), count=12, speed=120)
        self._build_buttons()
        return None

    def _sounds(self, action, out, hp_before, hero_before):
        """Sound for what the last menu pick did: the hero's move, then
        (slightly later) the enemy's counter-hit and the fight's end."""
        kind, b = action[0], self.battle
        if kind in ("mode", "back"):
            audio.play("click")
            return
        if any(line == "You can't move this turn!" for line in out):
            audio.play("ailment")
        elif kind == "attack":
            hit = self.enemy.hp < hp_before
            audio.play(action[1] if hit and len(action) > 1
                       else "strike" if hit else "miss")
        elif kind == "cast":
            a = action[1]
            audio.play("magic" if a.damage else "heal" if a.heal else "guard")
        elif kind == "use":
            audio.play("bomb" if action[1].damage else "potion")
        elif kind == "run":
            audio.play("run" if b.state == FLED else "fail")
        if any(line.endswith(f"{word}!") for line in out
               for word in AFFLICTED.values()):
            audio.play("ailment", delay=0.25)
        if self.player.current_hp < hero_before:
            audio.play("hurt", delay=0.4)
        if b.state == WON:
            audio.play("victory", delay=0.45)
        elif b.state == LOST:
            audio.play("defeat", delay=0.6)

    def _pop(self, text, color, x, y):
        self.pops.append([text, color, x, y, 0.0])

    def _leave(self):
        b = self.battle
        if b.state == LOST:
            # Defeat ends the run; the hero wakes up rested in the Base.
            self.player.rest()
            save_player(self.player)
            delete_run(self.player.name)
            return ("base", {"player": self.player})
        self.dungeon.battle_over(b)
        return ("resume", {"screen": self.dungeon})

    # -- Screen hooks ------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            save_player(self.player)
            return QUIT
        if event.type == pygame.MOUSEMOTION:
            self.hot = next((i for i, (btn, _, en) in enumerate(self.buttons)
                             if en and btn.rect.collidepoint(event.pos)), None)
            if self.hot is not None:
                self.focus = self.hot
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for btn, action, enabled in self.buttons:
                if enabled and btn.rect.collidepoint(event.pos):
                    return self._do(action)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                step = -1 if event.key == pygame.K_UP else 1
                self.focus = (self.focus + step) % len(self.buttons)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                btn, action, enabled = self.buttons[self.focus]
                if enabled:
                    return self._do(action)
            elif event.key == pygame.K_ESCAPE and self.mode != "main":
                return self._do(("back",))
        return None

    def handle_update(self, dt):
        self.anim_t += dt
        self.hurt_t = max(0.0, self.hurt_t - dt)
        self.hero_hurt_t = max(0.0, self.hero_hurt_t - dt)
        for pop in self.pops:
            pop[4] += dt
        self.pops = [p for p in self.pops if p[4] < POP_TIME]
        self.fx.update(dt)
        if self.end_t is not None:
            self.end_t += dt

    # -- drawing -------------------------------------------------------------
    def _statuses(self, surface, statuses, pos, extra=()):
        x, y = pos
        for text in [f"{n} {t}" for n, t in statuses.items()] + list(extra):
            img = font(18).render(text, True, BAD if text not in extra else GOOD)
            surface.blit(img, (x, y))
            x += img.get_width() + 12

    def draw(self, surface):
        surface.fill(BG_COLOR)
        p, e, b = self.player, self.enemy, self.battle
        blink = int(self.anim_t / 0.4) % 2

        # Enemy (top right).
        frames = ENEMY_HURT if self.hurt_t > 0 else ENEMY_IDLE
        frame = self.enemy_frames[frames[blink]]
        if not e.alive:
            # Death frames, fading out over END_TIME.
            t = min(1.0, (self.end_t or 0.0) / END_TIME)
            frame = self.enemy_frames[ENEMY_DEATH[0 if t < 0.5 else 1]].copy()
            frame.set_alpha(int(255 * (1 - 0.6 * t)))
        ex = 590
        if frame is not None:
            surface.blit(frame, frame.get_rect(midbottom=(ex, 330)))
        title = font(26).render(e.name + (f"  (floor {e.floor})"), True,
                                GOLD if e.boss else TEXT_COLOR)
        surface.blit(title, (420, 40))
        _bar(surface, (420, 72, 300, 14), e.hp, e.max_hp, HP_COLOR)
        hpt = font(18).render(f"{e.hp} / {e.max_hp}", True, DIM_TEXT)
        surface.blit(hpt, (728, 70))
        self._statuses(surface, e.statuses, (420, 94))

        # Hero (left).
        hero_img = self.hero_frames[blink]
        hx = 70
        if self.hero_hurt_t > 0:
            hero_img = hero_img.copy()
            hero_img.fill((110, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
            hx += SHAKE if int(self.hero_hurt_t * 40) % 2 else -SHAKE
        hy = 220
        if b.state == LOST:
            # Collapse: tip over and fade.
            t = min(1.0, (self.end_t or 0.0) / END_TIME)
            hero_img = pygame.transform.rotate(hero_img, -80 * t)
            hero_img.set_alpha(int(255 * (1 - 0.5 * t)))
            hy += int(40 * t)
        surface.blit(hero_img, (hx, hy))
        name = font(26).render(p.name, True, TEXT_COLOR)
        surface.blit(name, (220, 250))
        _bar(surface, (220, 284, 170, 14), p.current_hp, p.max_hp, HP_COLOR)
        surface.blit(font(18).render(f"HP {p.current_hp}/{p.max_hp}", True, DIM_TEXT),
                     (396, 282))
        _bar(surface, (220, 306, 170, 10), p.current_mp, p.max_mp, MP_COLOR)
        surface.blit(font(18).render(f"MP {p.current_mp}/{p.max_mp}", True, DIM_TEXT),
                     (396, 302))
        if b.state == ONGOING:
            lo, hi = b.incoming_preview()
            surface.blit(font(18).render(f"Next enemy hit: {lo}-{hi}", True, BAD),
                         (220, 346))
        shield = (f"shield +{b.guard} ({b.guard_turns})",) if b.guard else ()
        self._statuses(surface, b.statuses, (220, 326), shield)

        # Log.
        pygame.draw.rect(surface, PANEL_COLOR, self.panel_log, border_radius=8)
        pygame.draw.rect(surface, BORDER_COLOR, self.panel_log, width=2,
                         border_radius=8)
        lines = b.log[-LOG_LINES:]
        for i, line in enumerate(lines):
            color = TEXT_COLOR if i == len(lines) - 1 else DIM_TEXT
            surface.blit(font(19).render(line, True, color),
                         (self.panel_log.x + 12, self.panel_log.y + 10 + i * 23))

        # Menu.
        pygame.draw.rect(surface, PANEL_COLOR, self.panel_menu, border_radius=8)
        pygame.draw.rect(surface, BORDER_COLOR, self.panel_menu, width=2,
                         border_radius=8)
        for i, (btn, _, enabled) in enumerate(self.buttons):
            if enabled:
                btn.draw(surface, hot=(i == self.focus))
            else:
                pygame.draw.rect(surface, (30, 30, 42), btn.rect, border_radius=6)
                txt = font(btn.font_size).render(btn.label, True, (95, 95, 110))
                surface.blit(txt, txt.get_rect(center=btn.rect.center))

        self.fx.draw(surface)
        for text, color, x, y, age in self.pops:
            img = font(28).render(text, True, color)
            img.set_alpha(int(255 * (1 - age / POP_TIME)))
            surface.blit(img, img.get_rect(center=(x, y - 40 * age)))

        if b.state != ONGOING:
            msg = {WON: ("Victory!", GOOD), FLED: ("You escaped.", TEXT_COLOR),
                   LOST: ("Defeated... back to the Base.", BAD)}[b.state]
            img = font(34).render(msg[0], True, msg[1])
            surface.blit(img, img.get_rect(center=(SCREEN_WIDTH // 2, 372)))
        hint = font(16).render("Up/Down + Enter, or click.  Esc: back",
                               True, DIM_TEXT)
        surface.blit(hint, hint.get_rect(bottomright=(SCREEN_WIDTH - 12,
                                                      SCREEN_HEIGHT - 2)))
