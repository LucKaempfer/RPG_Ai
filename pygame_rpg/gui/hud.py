# pygame_rpg/gui/hud.py
"""In-dungeon HUD (M4): HP / MP / XP bars, floor, gold, a gear strip with
what the hero has equipped (weapon, head, torso, hands, feet; an empty
slot shows as a dim outline) and a short message log ("+20 XP",
"Found: Bow II", ...).  Clicking / tapping the gear strip opens the
inventory (the dungeon screen checks ``Hud.gear_rect``).

The minimap is drawn by ``Dungeon.draw_minimap``; the dungeon screen
places it next to this overlay.
"""

import pygame

from ..assets import AssetManager
from ..items import item_by_id
from .inventory_screen import RARITY_COLOR
from .screen import draw_bar, font, TEXT_COLOR, DIM_TEXT, GOLD, BORDER_COLOR

HP_COLOR = (200, 70, 70)
MP_COLOR = (80, 120, 220)
XP_COLOR = GOLD
MESSAGE_TIME = 6.0      # seconds a message stays fully visible
MESSAGE_FADE = 1.5      # then fades out over this long
MAX_MESSAGES = 5

# The gear strip: slot -> item whose icon, as a dim silhouette, marks
# the slot while it is empty.
GEAR_SLOTS = (("weapon", "sword"), ("head", "leather_cap"),
              ("torso", "leather_vest"), ("hands", "leather_gloves"),
              ("feet", "leather_boots"))
GEAR_X, GEAR_Y = 16, 100        # top-left of the first slot box
GEAR_BOX, GEAR_STEP = 34, 44    # box size, distance between boxes
SLOT_BG = (24, 24, 34)
TIERS = {2: "II", 3: "III", 4: "IV", 5: "V"}


_PANEL = []


def _panel():
    if not _PANEL:
        panel = pygame.Surface((236, 144), pygame.SRCALPHA)
        panel.fill((10, 10, 16, 170))
        _PANEL.append(panel)
    return _PANEL[0]


class Hud:
    def __init__(self):
        self.messages = []      # [text, age_seconds]
        self.assets = AssetManager()
        self._icons = {}
        self._ghosts = {}
        # Screen rect of the gear strip (set by ``draw``), for taps.
        self.gear_rect = pygame.Rect(GEAR_X, GEAR_Y,
                                     GEAR_STEP * (len(GEAR_SLOTS) - 1) + GEAR_BOX,
                                     GEAR_BOX)

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

    def _ghost(self, item_id):
        """Dim silhouette of an item's icon (marks an empty slot)."""
        if item_id not in self._ghosts:
            surf = self._icon(item_by_id(item_id)).copy()
            surf.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surf.fill((62, 62, 80, 0), special_flags=pygame.BLEND_RGBA_ADD)
            surf.set_alpha(150)
            self._ghosts[item_id] = surf
        return self._ghosts[item_id]

    def draw_gear(self, surface, player) -> None:
        """One box per GEAR_SLOTS slot: the equipped item's icon framed in
        its rarity colour (with its tier, II-V, in the corner), or a dim
        outline when the slot is empty."""
        for i, (slot, ghost) in enumerate(GEAR_SLOTS):
            box = pygame.Rect(GEAR_X + i * GEAR_STEP, GEAR_Y, GEAR_BOX, GEAR_BOX)
            item = player.equipment.get(slot)
            pygame.draw.rect(surface, SLOT_BG, box, border_radius=5)
            rim = (RARITY_COLOR.get(getattr(item, "rarity", ""), BORDER_COLOR)
                   if item is not None else (60, 60, 76))
            icon = self._icon(item) if item is not None else self._ghost(ghost)
            surface.blit(icon, icon.get_rect(center=box.center))
            pygame.draw.rect(surface, rim, box, 2 if item else 1, border_radius=5)
            tier = TIERS.get(getattr(item, "level", 1)) if item else None
            if tier:
                tag = font(13).render(tier, True, GOLD)
                r = tag.get_rect(bottomright=(box.right + 3, box.bottom + 3))
                pygame.draw.rect(surface, SLOT_BG, r.inflate(4, 0), border_radius=3)
                surface.blit(tag, r)

    @staticmethod
    def _bar(surface, x, y, w, h, value, maximum, color, label):
        draw_bar(surface, (x, y, w, h), value, maximum, color, radius=4)
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
        surface.blit(gold, gold.get_rect(topright=(236, 17)))
        p = player
        self._bar(surface, 16, 40, 220, 16, p.current_hp, p.max_hp, HP_COLOR,
                  f"HP {p.current_hp}/{p.max_hp}")
        self._bar(surface, 16, 60, 220, 16, p.current_mp, p.max_mp, MP_COLOR,
                  f"MP {p.current_mp}/{p.max_mp}")
        self._bar(surface, 16, 80, 220, 12, p.xp, p.max_xp, XP_COLOR,
                  f"XP {p.xp}/{p.max_xp}")
        self.draw_gear(surface, p)

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
