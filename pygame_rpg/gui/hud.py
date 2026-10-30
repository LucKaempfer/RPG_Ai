# pygame_rpg/gui/hud.py
"""In-dungeon HUD (M4): HP / MP / XP bars, floor, gold, equipped weapon icon
and a short message log ("+20 XP", "Found: Bow II", ...).

The minimap is drawn by ``Dungeon.draw_minimap``; the dungeon screen
places it next to this overlay.
"""

import pygame

from ..assets import AssetManager
from .screen import font, TEXT_COLOR, DIM_TEXT, GOLD, BORDER_COLOR

HP_COLOR = (200, 70, 70)
MP_COLOR = (80, 120, 220)
XP_COLOR = GOLD
MESSAGE_TIME = 6.0      # seconds a message stays fully visible
MESSAGE_FADE = 1.5      # then fades out over this long
MAX_MESSAGES = 5


_PANEL = []


def _panel():
    if not _PANEL:
        panel = pygame.Surface((236, 104), pygame.SRCALPHA)
        panel.fill((10, 10, 16, 170))
        _PANEL.append(panel)
    return _PANEL[0]


class Hud:
    def __init__(self):
        self.messages = []      # [text, age_seconds]
        self.assets = AssetManager()
        self._icons = {}

    def say(self, text: str) -> None:
        self.messages.append([text, 0.0])
        self.messages = self.messages[-MAX_MESSAGES:]

    def update(self, dt: float) -> None:
        for m in self.messages:
            m[1] += dt
        self.messages = [m for m in self.messages
                         if m[1] < MESSAGE_TIME + MESSAGE_FADE]

    def _icon(self, item):
        if item.id not in self._icons:
            surf = self.assets.item_icon(item)
            self._icons[item.id] = pygame.transform.scale(surf, (32, 32))
        return self._icons[item.id]

    @staticmethod
    def _bar(surface, x, y, w, h, value, maximum, color, label):
        pygame.draw.rect(surface, (15, 15, 20), (x, y, w, h), border_radius=4)
        if maximum > 0 and value > 0:
            fill = max(2, int(w * min(value, maximum) / maximum))
            pygame.draw.rect(surface, color, (x, y, fill, h), border_radius=4)
        pygame.draw.rect(surface, BORDER_COLOR, (x, y, w, h), width=1,
                         border_radius=4)
        txt = font(16).render(label, True, TEXT_COLOR)
        surface.blit(txt, txt.get_rect(midleft=(x + 6, y + h // 2)))

    def draw(self, surface, player, floor: int, log_x: int = 14) -> None:
        """``log_x``: left edge of the message log (moved right on a touch
        screen, where the D-pad sits in that corner)."""
        # Backing panel for legibility over the map.
        surface.blit(_panel(), (8, 8))
        surface.blit(font(22).render(f"Floor {floor}", True, GOLD), (16, 14))
        lvl = font(18).render(f"Lv {player.lvl}", True, DIM_TEXT)
        surface.blit(lvl, (100, 17))
        gold = font(18).render(f"{player.gold} g", True, GOLD)
        surface.blit(gold, gold.get_rect(topright=(196, 17)))
        weapon = player.equipment.get("weapon")
        if weapon is not None:
            surface.blit(self._icon(weapon), (204, 12))
        p = player
        self._bar(surface, 16, 40, 220, 16, p.current_hp, p.max_hp, HP_COLOR,
                  f"HP {p.current_hp}/{p.max_hp}")
        self._bar(surface, 16, 60, 220, 16, p.current_mp, p.max_mp, MP_COLOR,
                  f"MP {p.current_mp}/{p.max_mp}")
        self._bar(surface, 16, 80, 220, 12, p.xp, p.max_xp, XP_COLOR,
                  f"XP {p.xp}/{p.max_xp}")

        # Message log, bottom left, newest last.
        y = surface.get_height() - 30 - 22 * len(self.messages)
        for text, age in self.messages:
            alpha = 255 if age < MESSAGE_TIME else int(
                255 * (1 - (age - MESSAGE_TIME) / MESSAGE_FADE))
            img = font(20).render(text, True, TEXT_COLOR)
            shadow = font(20).render(text, True, (0, 0, 0))
            img.set_alpha(alpha)
            shadow.set_alpha(alpha)
            surface.blit(shadow, (log_x + 1, y + 1))
            surface.blit(img, (log_x, y))
            y += 22
