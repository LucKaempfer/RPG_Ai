# pygame_rpg/gui/effects.py
"""Small visual effects shared by the screens (M5 polish).

``Particles`` is a pool of short-lived sparks: ``burst()`` spawns a ring
of them, ``update(dt)`` moves and ages them, ``draw()`` blits them.  No
assets and no audio, so it works headless and needs no new files.
"""

import math
import random

import pygame

GRAVITY = 220          # px/s^2 pulling sparks down


class Particles:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.items = []    # [x, y, vx, vy, age, life, color, size]

    def burst(self, x, y, color, count=18, speed=140, life=0.7, size=3):
        for i in range(count):
            angle = 2 * math.pi * i / count + self.rng.uniform(-0.3, 0.3)
            v = speed * self.rng.uniform(0.5, 1.0)
            self.items.append([x, y, math.cos(angle) * v,
                               math.sin(angle) * v - speed * 0.4, 0.0,
                               life * self.rng.uniform(0.7, 1.0), color, size])

    def update(self, dt):
        for p in self.items:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += GRAVITY * dt
            p[4] += dt
        self.items = [p for p in self.items if p[4] < p[5]]

    def draw(self, surface, offset=(0, 0)):
        ox, oy = offset
        for x, y, _, _, age, life, color, size in self.items:
            r = max(1, round(size * (1 - age / life)))
            pygame.draw.circle(surface, color, (int(x - ox), int(y - oy)), r)

    def __bool__(self):
        return bool(self.items)


def menu_key(event, count, focus):
    """Keyboard navigation for a vertical button list.

    Returns ``(focus, activate)``: Up / Down (or W / S) move the focus
    (wrapping), Enter / Space activate the focused entry.  ``focus`` may
    be None (nothing focused yet): the first key press focuses entry 0.
    """
    if event.type != pygame.KEYDOWN or count == 0:
        return focus, False
    if event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
        step = -1 if event.key in (pygame.K_UP, pygame.K_w) else 1
        focus = 0 if focus is None else (focus + step) % count
        return focus, False
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
        return (focus if focus is not None else 0), True
    return focus, False
