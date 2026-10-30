# pygame_rpg/item_icons.py
"""Item icons: one 32x32 pixel sprite per item, drawn in code.

``draw_item_icon(item)`` picks the picture from the item's kind and
level-1 id (``bow_3`` draws like ``bow``): every weapon base, armour
piece, consumable, trinket, ability and piece of junk has its own
drawing.  Weapon and armour metal gets brighter with the tier (iron,
steel, blue steel, gold-trimmed), so upgrades show at a glance.  Every
shape gets a dark 1-pixel outline so it reads on any panel colour.

Nothing is saved to disk (``AssetManager.item_icon`` caches the
surfaces), so the icons work on read-only installs such as Android.
"""
import math

import pygame

SIZE = 32
OUTLINE = (22, 18, 26)

# Metal by tier: (base, light, dark).
METAL = {
    1: ((150, 154, 160), (205, 208, 214), (96, 100, 108)),
    2: ((176, 184, 196), (232, 236, 242), (112, 120, 134)),
    3: ((120, 160, 210), (190, 220, 250), (70, 100, 150)),
    4: ((214, 180, 90), (250, 228, 150), (150, 112, 50)),
}
WOOD = ((140, 92, 50), (182, 128, 76), (92, 58, 30))
LEATHER = ((150, 100, 60), (190, 140, 92), (100, 64, 36))
GOLD = ((230, 190, 80), (255, 236, 150), (170, 128, 40))
CLOTH = ((180, 60, 60), (226, 110, 100), (120, 36, 40))
BONE = ((226, 218, 196), (250, 246, 232), (170, 160, 136))

# Ailment colours (staff orbs, bombs, wards): (base, light, dark).
ELEMENT = {
    "poison": ((90, 190, 70), (170, 240, 130), (40, 120, 40)),
    "burning": ((240, 120, 40), (255, 210, 110), (180, 50, 30)),
    "electrocuted": ((90, 200, 240), (210, 245, 255), (40, 120, 190)),
    "bleeding": ((200, 40, 50), (250, 110, 110), (130, 20, 30)),
    "stun": ((240, 210, 70), (255, 245, 170), (170, 140, 30)),
}


def _base_id(item_id: str) -> str:
    head, _, tail = item_id.rpartition("_")
    return head if head and tail.isdigit() else item_id


def _outlined(surf: pygame.Surface) -> pygame.Surface:
    """``surf`` with a dark 1-pixel outline around everything drawn."""
    sil = pygame.mask.from_surface(surf).to_surface(
        setcolor=(*OUTLINE, 255), unsetcolor=(0, 0, 0, 0))
    out = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        out.blit(sil, (dx, dy))
    out.blit(surf, (0, 0))
    return out


def _line(s, color, a, b, w=1):
    pygame.draw.line(s, color, a, b, w)


def _poly(s, color, pts):
    pygame.draw.polygon(s, color, pts)


def _diag_blade(s, metal, x0, y0, x1, y1, w):
    """A blade from (x0, y0) (hilt end) to the tip (x1, y1), ``w`` wide."""
    base, light, dark = metal
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    px, py = -dy / n * w / 2, dx / n * w / 2
    tip = (x1, y1)
    back = (x1 - dx / n * w, y1 - dy / n * w)
    _poly(s, base, [(x0 + px, y0 + py), (back[0] + px, back[1] + py), tip,
                    (back[0] - px, back[1] - py), (x0 - px, y0 - py)])
    _line(s, light, (x0 + px * 0.4, y0 + py * 0.4), (back[0] + px * 0.4, back[1] + py * 0.4))
    _line(s, dark, (x0 - px * 0.6, y0 - py * 0.6), (back[0] - px * 0.6, back[1] - py * 0.6))


def _hilt(s, metal, x, y, guard=5):
    """Crossguard at (x, y) across the up-right diagonal, grip below-left."""
    _line(s, metal[2], (x - guard, y - guard), (x + guard, y + guard), 3)
    _line(s, LEATHER[2], (x, y), (x - 5, y + 5), 3)
    pygame.draw.circle(s, GOLD[0], (x - 6, y + 6), 2)


# ---------------------------------------------------------------------------
# Weapons
# ---------------------------------------------------------------------------

def _w_sword(s, m, lvl, base):
    if base == "greatsword":
        _diag_blade(s, m, 10, 22, 28, 3, 6)
        _hilt(s, m, 10, 22, 6)
    elif base == "dagger":
        _diag_blade(s, m, 13, 19, 25, 7, 5)
        _hilt(s, m, 13, 19, 4)
    else:
        _diag_blade(s, m, 11, 21, 27, 5, 4)
        _hilt(s, m, 11, 21)


def _w_saber(s, m, lvl, base):
    # A curved blade: a thick arc, light inner edge.
    pygame.draw.arc(s, m[0], (4, 2, 34, 34), math.pi * 0.52, math.pi * 0.98, 4)
    pygame.draw.arc(s, m[1], (6, 4, 30, 30), math.pi * 0.55, math.pi * 0.95, 1)
    _line(s, GOLD[2], (2, 19), (10, 19), 3)          # guard
    _line(s, LEATHER[2], (6, 20), (6, 28), 3)        # grip
    pygame.draw.circle(s, GOLD[0], (6, 29), 2)


def _w_spear(s, m, lvl, base):
    _line(s, WOOD[0], (5, 27), (22, 10), 3)
    _line(s, WOOD[1], (5, 26), (21, 10), 1)
    _poly(s, m[0], [(20, 9), (28, 3), (24, 12)])
    _poly(s, m[1], [(21, 9), (28, 3), (23, 8)])
    _line(s, CLOTH[0], (19, 13), (16, 18), 2)        # tassel


def _w_warhammer(s, m, lvl, base):
    _line(s, WOOD[0], (7, 27), (19, 13), 3)
    _poly(s, m[0], [(14, 6), (22, 2), (29, 11), (21, 16)])
    _poly(s, m[1], [(15, 6), (22, 3), (23, 5), (16, 8)])
    _poly(s, m[2], [(21, 16), (29, 11), (28, 13), (22, 17)])


def _w_mace(s, m, lvl, base):
    _line(s, WOOD[2], (7, 27), (17, 15), 3)
    for a in range(8):
        ang = a * math.pi / 4
        _line(s, m[2], (21, 11), (21 + 9 * math.cos(ang), 11 + 9 * math.sin(ang)), 2)
    pygame.draw.circle(s, m[0], (21, 11), 6)
    pygame.draw.circle(s, m[1], (19, 9), 2)


def _w_club(s, m, lvl, base):
    _poly(s, WOOD[0], [(5, 26), (8, 28), (26, 10), (23, 3), (17, 7)])
    _line(s, WOOD[1], (7, 25), (20, 8), 2)
    for (x, y) in ((22, 7), (19, 13), (24, 11)):
        pygame.draw.circle(s, WOOD[2], (x, y), 1)
    if lvl > 1:                                      # iron bands on tiers
        _line(s, m[0], (16, 11), (20, 15), 2)


def _w_bow(s, m, lvl, base):
    if base == "crossbow":
        _line(s, WOOD[0], (6, 26), (21, 11), 4)                  # stock
        pygame.draw.arc(s, m[0], (11, 1, 20, 20), math.pi * 0.75, math.pi * 1.75, 3)
        _line(s, (230, 226, 210), (13, 5), (27, 19), 1)          # string
        _line(s, m[1], (17, 15), (26, 6), 1)                     # bolt
    else:
        # Bow arcs across the top left, string on the diagonal, arrow nocked.
        pygame.draw.arc(s, WOOD[0], (2, 2, 42, 42), math.pi * 0.5, math.pi, 3)
        pygame.draw.arc(s, WOOD[1], (3, 3, 40, 40), math.pi * 0.56, math.pi * 0.94, 1)
        _line(s, (230, 226, 210), (23, 2), (2, 23), 1)           # string
        _line(s, WOOD[2], (25, 25), (8, 8), 1)                   # arrow
        _poly(s, m[1], [(4, 4), (10, 6), (6, 10)])
        _line(s, CLOTH[1], (25, 25), (25, 21), 2)                # fletching
        _line(s, CLOTH[1], (25, 25), (21, 25), 2)
        if lvl > 1:
            pygame.draw.circle(s, m[0], (8, 8), 2)               # grip ring


def _w_blowpipe(s, m, lvl, base):
    _line(s, (120, 150, 80), (4, 27), (26, 5), 4)
    _line(s, (170, 200, 120), (4, 26), (25, 5), 1)
    for t in (0.3, 0.6):
        x, y = 4 + 22 * t, 27 - 22 * t
        _line(s, (80, 100, 50), (x - 2, y - 2), (x + 2, y + 2), 2)
    _line(s, m[1], (27, 5), (30, 2), 1)                         # dart


def _w_boomerang(s, m, lvl, base):
    _poly(s, WOOD[0], [(4, 8), (9, 5), (18, 18), (27, 9), (29, 14), (17, 26)])
    _line(s, WOOD[1], (7, 7), (17, 20), 1)
    _line(s, WOOD[1], (18, 21), (27, 12), 1)
    if lvl > 1:
        pygame.draw.circle(s, m[0], (17, 21), 2)


def _w_slingshot(s, m, lvl, base):
    _line(s, WOOD[0], (16, 29), (16, 18), 4)
    _line(s, WOOD[0], (16, 19), (8, 6), 3)
    _line(s, WOOD[0], (16, 19), (24, 6), 3)
    _line(s, (200, 80, 60), (8, 7), (16, 15), 1)
    _line(s, (200, 80, 60), (24, 7), (16, 15), 1)
    pygame.draw.circle(s, m[0], (16, 15), 3)


def _w_whip(s, m, lvl, base):
    _line(s, LEATHER[2], (4, 27), (10, 21), 4)                  # handle
    pygame.draw.circle(s, GOLD[0], (10, 21), 2)
    pygame.draw.arc(s, LEATHER[0], (9, 6, 18, 18), math.pi * 0.8, math.pi * 2.6, 2)
    pygame.draw.arc(s, LEATHER[1], (14, 10, 10, 10), 0, math.pi * 1.6, 1)
    _line(s, LEATHER[0], (27, 15), (29, 24), 1)


def _w_staff(s, m, lvl, base, effect):
    el = ELEMENT.get(effect, ELEMENT["burning"])
    _line(s, WOOD[0], (5, 28), (21, 10), 3)
    _line(s, WOOD[1], (5, 27), (20, 10), 1)
    pygame.draw.arc(s, WOOD[2], (17, 2, 13, 13), math.pi * 0.9, math.pi * 2.4, 2)
    pygame.draw.circle(s, el[0], (24, 8), 4)
    pygame.draw.circle(s, el[1], (23, 7), 1)


def _w_wand(s, m, lvl, base, effect):
    el = ELEMENT.get(effect, ELEMENT["burning"])
    _line(s, WOOD[2], (8, 25), (20, 13), 3)
    _line(s, GOLD[0], (9, 22), (11, 24), 2)
    for k in range(4):                                         # sparkle
        ang = k * math.pi / 2 + math.pi / 4
        _line(s, el[1], (23, 10), (23 + 5 * math.cos(ang), 10 + 5 * math.sin(ang)), 1)
    pygame.draw.circle(s, el[0], (22, 11), 3)
    pygame.draw.circle(s, el[1], (21, 10), 1)


_WEAPONS = {
    "sword": _w_sword, "greatsword": _w_sword, "dagger": _w_sword,
    "saber": _w_saber, "spear": _w_spear,
    "warhammer": _w_warhammer, "mace": _w_mace, "club": _w_club,
    "bow": _w_bow, "crossbow": _w_bow, "blowpipe": _w_blowpipe,
    "boomerang": _w_boomerang, "slingshot": _w_slingshot, "whip": _w_whip,
}


def _weapon(s, item, base):
    m = METAL.get(item.level, METAL[1])
    if base.endswith("_staff"):
        _w_staff(s, m, item.level, base, item.effect)
    elif base.endswith("_wand"):
        _w_wand(s, m, item.level, base, item.effect)
    else:
        _WEAPONS.get(base, _w_sword)(s, m, item.level, base)


# ---------------------------------------------------------------------------
# Armour
# ---------------------------------------------------------------------------

def _armor(s, item, base):
    iron = base.startswith(("iron", "chain"))
    c = METAL.get(item.level, METAL[1]) if iron else LEATHER
    trim = METAL.get(item.level, METAL[1])[0] if not iron and item.level > 1 else None
    if item.slot == "head":
        if iron:
            pygame.draw.ellipse(s, c[0], (6, 5, 20, 22))
            pygame.draw.rect(s, (0, 0, 0, 0), (6, 21, 20, 8))
            _poly(s, c[0], [(6, 16), (12, 16), (12, 25), (6, 22)])
            _poly(s, c[0], [(26, 16), (20, 16), (20, 25), (26, 22)])
            _line(s, c[2], (11, 15), (21, 15), 2)              # visor slit
            _line(s, c[1], (16, 6), (16, 13), 2)               # ridge
        else:
            pygame.draw.ellipse(s, c[0], (6, 7, 20, 18))
            pygame.draw.rect(s, (0, 0, 0, 0), (5, 18, 22, 8))
            _poly(s, c[2], [(4, 18), (28, 18), (26, 21), (6, 21)])  # brim
            _line(s, c[1], (11, 10), (15, 9), 2)
            pygame.draw.circle(s, c[2], (16, 7), 2)
    elif item.slot == "torso":
        pts = [(9, 5), (13, 5), (16, 9), (19, 5), (23, 5), (29, 10), (25, 15),
               (24, 28), (8, 28), (7, 15), (3, 10)]
        _poly(s, c[0], pts)
        if iron:
            for y in range(10, 28, 3):
                for x in range(9 + (y % 2), 24, 3):
                    s.set_at((x, y), c[2])
                    s.set_at((x + 1, y), c[1])
        else:
            _line(s, c[2], (16, 10), (16, 27), 1)
            for y in (13, 18, 23):
                pygame.draw.circle(s, GOLD[2], (18, y), 1)
            _line(s, c[1], (9, 12), (10, 24), 1)
        if trim:
            _line(s, trim, (8, 27), (24, 27), 2)
    elif item.slot == "hands":
        _poly(s, c[0], [(9, 14), (9, 6), (12, 5), (13, 12), (14, 4), (17, 4),
                        (17, 12), (18, 5), (21, 6), (21, 13), (24, 11), (26, 13),
                        (21, 21), (10, 21)])
        _poly(s, c[2] if iron else c[2], [(9, 21), (22, 21), (22, 27), (9, 27)])  # cuff
        _line(s, c[1], (11, 8), (11, 13), 1)
        _line(s, c[1], (15, 6), (15, 12), 1)
        if trim or iron:
            _line(s, (trim or c[1]), (9, 23), (22, 23), 1)
    else:  # feet
        _poly(s, c[0], [(9, 4), (19, 4), (19, 19), (28, 22), (28, 27), (8, 27), (8, 18)])
        _poly(s, c[2], [(8, 25), (28, 25), (28, 28), (8, 28)])   # sole
        _line(s, c[1], (11, 6), (11, 18), 1)
        if iron:
            _line(s, c[1], (9, 12), (18, 12), 1)
        if trim:
            _line(s, trim, (9, 5), (18, 5), 2)


# ---------------------------------------------------------------------------
# Consumables
# ---------------------------------------------------------------------------

def _flask(s, liquid, big):
    glass = (210, 230, 240)
    w = 9 if big else 7
    pygame.draw.circle(s, glass, (16, 20), w + 1)
    pygame.draw.circle(s, liquid[0], (16, 21), w)
    pygame.draw.rect(s, (0, 0, 0, 0), (16 - w, 20 - w, 2 * w + 1, 3))
    pygame.draw.ellipse(s, liquid[1], (16 - w + 1, 16, 2 * w - 2, 4))
    pygame.draw.rect(s, glass, (13, 6, 7, 7))
    pygame.draw.rect(s, WOOD[0], (12, 3, 9, 4))                  # cork
    _line(s, (255, 255, 255), (11, 17), (10, 22), 1)


def _bomb(s, el):
    pygame.draw.circle(s, (56, 56, 64), (15, 19), 9)
    pygame.draw.circle(s, el[0], (15, 19), 6)
    pygame.draw.circle(s, el[1], (13, 17), 2)
    pygame.draw.rect(s, (90, 90, 96), (17, 8, 5, 4))
    _line(s, (190, 160, 110), (20, 8), (24, 4), 1)
    for k in range(4):
        ang = k * math.pi / 2
        _line(s, (255, 220, 120), (25, 4), (25 + 3 * math.cos(ang), 4 + 3 * math.sin(ang)), 1)


def _consumable(s, item, base):
    big = item.level >= 3
    if base == "potion":
        _flask(s, ELEMENT["bleeding"], big)
    elif base == "mana_potion":
        _flask(s, ((70, 110, 230), (150, 180, 255), (40, 60, 160)), big)
    elif base == "ration":
        _poly(s, (200, 150, 80), [(4, 22), (8, 12), (16, 8), (25, 10), (29, 18), (27, 25), (6, 25)])
        _poly(s, (230, 190, 120), [(7, 14), (16, 10), (24, 12), (18, 15)])
        for x in (12, 17, 22):
            _line(s, (150, 100, 50), (x, 12), (x - 2, 18), 1)
        pygame.draw.ellipse(s, (240, 220, 170), (10, 19, 14, 5))    # cheese
    elif base.endswith("_bomb"):
        _bomb(s, ELEMENT.get(item.effect, ELEMENT["burning"]))
    else:
        _flask(s, ELEMENT["poison"], big)


# ---------------------------------------------------------------------------
# Trinkets
# ---------------------------------------------------------------------------

_WARD_ELEMENT = {"bleed_ward": "bleeding", "stun_ward": "stun",
                 "poison_ward": "poison", "burn_ward": "burning",
                 "shock_ward": "electrocuted"}


def _trinket(s, item, base):
    if base in ("weight_belt", "iron_belt"):
        c = LEATHER if base == "weight_belt" else ((96, 100, 108), (150, 154, 162), (56, 58, 64))
        pygame.draw.rect(s, c[0], (2, 13, 28, 7))
        _line(s, c[1], (2, 14), (29, 14), 1)
        pygame.draw.rect(s, GOLD[0], (12, 10, 9, 13), 2)
        _line(s, GOLD[2], (16, 12), (16, 21), 1)
    elif base == "wisdom_amulet":
        pygame.draw.arc(s, GOLD[0], (6, 1, 20, 22), 0, math.pi, 1)
        _line(s, GOLD[0], (6, 12), (13, 18), 1)
        _line(s, GOLD[0], (26, 12), (19, 18), 1)
        pygame.draw.circle(s, GOLD[0], (16, 21), 6)
        pygame.draw.circle(s, (80, 120, 230), (16, 21), 4)
        pygame.draw.circle(s, (180, 210, 255), (15, 20), 1)
    elif base == "scholar_coin":
        pygame.draw.circle(s, GOLD[2], (16, 16), 11)
        pygame.draw.circle(s, GOLD[0], (16, 16), 9)
        pygame.draw.rect(s, GOLD[2], (12, 11, 8, 10), 1)          # book
        _line(s, GOLD[2], (16, 11), (16, 20), 1)
        _line(s, GOLD[1], (10, 9), (13, 7), 1)
    elif base == "greed_ring":
        pygame.draw.circle(s, GOLD[0], (16, 19), 9, 3)
        _poly(s, (60, 200, 110), [(16, 4), (21, 9), (16, 14), (11, 9)])
        _poly(s, (170, 250, 200), [(16, 5), (18, 8), (16, 9)])
    elif base == "fortune_charm":
        for dx, dy in ((-4, -4), (4, -4), (-4, 4), (4, 4)):
            pygame.draw.circle(s, (70, 170, 70), (16 + dx, 14 + dy), 5)
        pygame.draw.circle(s, (130, 220, 120), (12, 10), 2)
        _line(s, (50, 120, 50), (16, 18), (21, 29), 2)
    elif base == "haste_scarf":
        # A striped scarf lying diagonally, fringe at both ends.
        _poly(s, CLOTH[0], [(4, 9), (9, 4), (28, 23), (23, 28)])
        for t in (8, 14, 20):
            _line(s, (240, 230, 210), (5 + t, 9 + t), (9 + t, 5 + t), 2)
        _line(s, CLOTH[1], (8, 5), (27, 24), 1)
        for k in range(3):
            _line(s, CLOTH[2], (4 + 2 * k, 9 - 2 * k), (2 + 2 * k, 7 - 2 * k), 1)
            _line(s, CLOTH[2], (24 + 2 * k, 28 - 2 * k), (26 + 2 * k, 30 - 2 * k), 1)
    elif base == "swift_feather":
        _poly(s, (230, 236, 245), [(6, 28), (12, 16), (22, 4), (26, 6), (20, 18)])
        _poly(s, (160, 200, 240), [(10, 22), (14, 15), (20, 13)])
        _line(s, (120, 130, 150), (6, 28), (24, 5), 1)
    elif base in _WARD_ELEMENT:
        el = ELEMENT[_WARD_ELEMENT[base]]
        _poly(s, (96, 100, 108), [(6, 5), (26, 5), (26, 15), (16, 28), (6, 15)])
        _poly(s, el[0], [(9, 8), (23, 8), (23, 15), (16, 24), (9, 15)])
        pygame.draw.circle(s, el[1], (16, 14), 3)
    else:
        pygame.draw.circle(s, GOLD[0], (16, 16), 8)
    if item.level > 1:                                           # tier gem
        pygame.draw.circle(s, METAL[item.level][1], (27, 27), 2)


# ---------------------------------------------------------------------------
# Abilities: a rune tile with the spell's symbol
# ---------------------------------------------------------------------------

_ABILITY_TILE = {
    "fireball": (150, 50, 30), "chain_lightning": (40, 80, 150),
    "power_strike": (110, 70, 40), "piercing_shot": (60, 100, 60),
    "heal": (40, 120, 70), "shield": (60, 70, 130),
}


def _ability(s, item, base):
    tile = _ABILITY_TILE.get(base, (90, 70, 120))
    pygame.draw.rect(s, tile, (3, 3, 26, 26), border_radius=5)
    pygame.draw.rect(s, tuple(min(255, c + 50) for c in tile), (3, 3, 26, 26), 1,
                     border_radius=5)
    if base == "fireball":
        _poly(s, ELEMENT["burning"][0], [(9, 22), (11, 11), (14, 15), (16, 6), (19, 14),
                                         (22, 10), (23, 22), (16, 26)])
        pygame.draw.circle(s, ELEMENT["burning"][1], (16, 20), 4)
    elif base == "chain_lightning":
        _poly(s, ELEMENT["electrocuted"][1], [(18, 5), (9, 17), (15, 17), (12, 27),
                                              (23, 13), (17, 13), (21, 5)])
    elif base == "power_strike":
        for k in range(8):
            ang = k * math.pi / 4
            r = 11 if k % 2 == 0 else 6
            _line(s, (250, 220, 120), (16, 16), (16 + r * math.cos(ang), 16 + r * math.sin(ang)), 2)
        pygame.draw.circle(s, (255, 250, 220), (16, 16), 3)
    elif base == "piercing_shot":
        _line(s, (230, 220, 200), (7, 25), (24, 8), 2)
        _poly(s, (230, 236, 245), [(21, 6), (27, 5), (26, 11)])
        _line(s, CLOTH[1], (7, 25), (6, 20), 2)
        _line(s, CLOTH[1], (7, 25), (12, 26), 2)
    elif base == "heal":
        pygame.draw.rect(s, (240, 250, 240), (13, 7, 6, 18))
        pygame.draw.rect(s, (240, 250, 240), (7, 13, 18, 6))
        pygame.draw.rect(s, (120, 230, 140), (14, 8, 4, 16))
        pygame.draw.rect(s, (120, 230, 140), (8, 14, 16, 4))
    else:  # shield
        _poly(s, (170, 190, 230), [(8, 7), (24, 7), (24, 16), (16, 26), (8, 16)])
        _poly(s, (90, 120, 200), [(11, 10), (21, 10), (21, 16), (16, 22), (11, 16)])
    for k in range(item.level - 1):                              # tier pips
        pygame.draw.circle(s, GOLD[1], (7 + 4 * k, 26), 1)


# ---------------------------------------------------------------------------
# Junk
# ---------------------------------------------------------------------------

def _junk(s, item, base):
    if base == "rat_tail":
        pts = [(5, 9), (10, 14), (14, 13), (18, 18), (22, 17), (27, 24)]
        pygame.draw.lines(s, (220, 150, 160), False, pts, 2)
        pygame.draw.ellipse(s, (120, 96, 80), (2, 6, 7, 6))
    elif base == "old_boot":
        _poly(s, (90, 70, 50), [(9, 4), (18, 4), (18, 18), (27, 21), (27, 27), (7, 27), (8, 16)])
        _line(s, (60, 46, 34), (7, 25), (27, 25), 2)
        _line(s, (60, 46, 34), (20, 21), (17, 24), 1)            # crack
        pygame.draw.rect(s, (0, 0, 0, 0), (24, 25, 2, 2))
    elif base == "bent_spoon":
        pygame.draw.lines(s, (180, 184, 190), False, [(6, 27), (12, 20), (14, 14), (19, 11)], 2)
        pygame.draw.ellipse(s, (180, 184, 190), (17, 4, 9, 11))
        pygame.draw.ellipse(s, (220, 224, 230), (19, 6, 4, 5))
    elif base == "cracked_mug":
        pygame.draw.rect(s, (180, 120, 80), (7, 9, 14, 17), border_radius=2)
        pygame.draw.arc(s, (180, 120, 80), (17, 12, 10, 10), -math.pi / 2, math.pi / 2, 2)
        pygame.draw.lines(s, (90, 56, 36), False, [(12, 9), (14, 14), (11, 18), (13, 23)], 1)
        _line(s, (220, 170, 120), (9, 11), (9, 23), 1)
    elif base == "rusty_key":
        pygame.draw.circle(s, (160, 90, 50), (9, 12), 5, 2)
        _line(s, (160, 90, 50), (13, 15), (26, 26), 2)
        _line(s, (160, 90, 50), (22, 22), (25, 19), 2)
        _line(s, (160, 90, 50), (25, 25), (28, 22), 2)
        s.set_at((18, 20), (110, 60, 30))
    elif base == "copper_ring":
        pygame.draw.circle(s, (200, 120, 70), (16, 16), 8, 3)
        pygame.draw.arc(s, (240, 170, 120), (9, 9, 14, 14), math.pi * 0.6, math.pi, 1)
    elif base == "broken_compass":
        pygame.draw.circle(s, GOLD[2], (16, 16), 11)
        pygame.draw.circle(s, (230, 226, 210), (16, 16), 8)
        _poly(s, (200, 40, 50), [(16, 16), (21, 9), (18, 17)])
        _poly(s, (60, 60, 70), [(16, 16), (11, 23), (14, 15)])
        pygame.draw.lines(s, (120, 120, 120), False, [(10, 11), (15, 14), (13, 20)], 1)
    elif base == "silver_goblet":
        _poly(s, (200, 204, 212), [(7, 5), (25, 5), (22, 14), (17, 17), (15, 17), (10, 14)])
        _line(s, (200, 204, 212), (16, 17), (16, 24), 2)
        pygame.draw.ellipse(s, (200, 204, 212), (9, 23, 14, 5))
        _line(s, (245, 245, 250), (10, 7), (12, 12), 1)
        pygame.draw.circle(s, (160, 40, 60), (16, 9), 2)
    elif base == "gold_tooth":
        _poly(s, GOLD[0], [(9, 6), (23, 6), (24, 14), (21, 27), (18, 18), (14, 18),
                           (11, 27), (8, 14)])
        _line(s, GOLD[1], (11, 8), (12, 14), 2)
    elif base == "jeweled_buckle":
        pygame.draw.rect(s, GOLD[0], (6, 8, 20, 16), 3, border_radius=3)
        _line(s, GOLD[2], (16, 10), (16, 22), 2)
        for (x, y), col in zip(((9, 10), (23, 10), (9, 22), (23, 22)),
                               ((200, 40, 60), (60, 200, 110), (80, 120, 230), (230, 220, 90))):
            pygame.draw.circle(s, col, (x, y), 2)
    else:
        pygame.draw.circle(s, (130, 120, 110), (16, 18), 8)


_KINDS = {"weapon": _weapon, "armor": _armor, "consumable": _consumable,
          "trinket": _trinket, "ability": _ability, "junk": _junk}


def draw_item_icon(item) -> pygame.Surface:
    """A 32x32 icon for ``item`` (anything with ``id``, ``kind``,
    ``level``, ``slot`` and ``effect``, like ``items.Item``)."""
    surf = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    draw = _KINDS.get(item.kind)
    if draw is None:
        pygame.draw.circle(surf, (150, 140, 120), (16, 16), 9)
    else:
        draw(surf, item, _base_id(item.id))
    return _outlined(surf)
