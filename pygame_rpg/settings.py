"""Player settings: brightness, volumes, fullscreen and key bindings.

One :data:`current` object is shared by the whole game: ``gui/display``
reads the brightness and fullscreen flag every frame, ``audio`` reads
the volumes, and the dungeon asks :func:`pressed` / :func:`held` which
keys do what.  The settings screen changes it and calls :func:`save`;
it lives in ``saves/settings.json`` next to the heroes and is read once
at start-up (:func:`load`).  A missing or broken file means defaults.

Each action has two key slots (``None`` = empty) so a player can keep
both the arrows and WASD, as the defaults do.
"""

import json

import pygame

from . import config, savegame

BRIGHTNESS_RANGE = (0.5, 2.0)

# Action -> label on the settings screen, in display order.
ACTIONS = {
    "up": "Move up",
    "down": "Move down",
    "left": "Move left",
    "right": "Move right",
    "attack": "Attack",
    "interact": "Talk / use",
    "inventory": "Inventory",
}
DEFAULT_KEYS = {
    "up": [pygame.K_UP, pygame.K_w],
    "down": [pygame.K_DOWN, pygame.K_s],
    "left": [pygame.K_LEFT, pygame.K_a],
    "right": [pygame.K_RIGHT, pygame.K_d],
    "attack": [pygame.K_SPACE, pygame.K_f],
    "interact": [pygame.K_e, None],
    "inventory": [pygame.K_i, None],
}
# Keys with a fixed job everywhere: back / Base, fullscreen, mute.
RESERVED_KEYS = (pygame.K_ESCAPE, pygame.K_F11, pygame.K_m)


class Settings:
    def __init__(self):
        self.brightness = 1.0
        self.ambience_volume = config.AMBIENT_VOLUME
        self.effects_volume = config.SFX_VOLUME
        self.fullscreen = False
        self.keys = {a: list(k) for a, k in DEFAULT_KEYS.items()}

    def to_dict(self):
        return {"brightness": self.brightness,
                "ambience_volume": self.ambience_volume,
                "effects_volume": self.effects_volume,
                "fullscreen": self.fullscreen,
                "keys": self.keys}

    @classmethod
    def from_dict(cls, data):
        """Settings from a saved dict; anything missing or odd keeps its
        default."""
        s = cls()
        lo, hi = BRIGHTNESS_RANGE
        s.brightness = _number(data.get("brightness"), s.brightness, lo, hi)
        s.ambience_volume = _number(data.get("ambience_volume"),
                                    s.ambience_volume, 0.0, 1.0)
        s.effects_volume = _number(data.get("effects_volume"),
                                   s.effects_volume, 0.0, 1.0)
        s.fullscreen = data.get("fullscreen") is True
        keys = data.get("keys")
        if isinstance(keys, dict):
            for action in ACTIONS:
                slots = keys.get(action)
                if (isinstance(slots, list) and len(slots) == 2
                        and all(k is None or (isinstance(k, int)
                                              and k not in RESERVED_KEYS)
                                for k in slots)):
                    s.keys[action] = list(slots)
        return s

    # -- key bindings ------------------------------------------------------
    def bind(self, action, slot, key):
        """Put ``key`` in ``action``'s ``slot``; a key does one thing
        only, so it is taken off any other slot first.  ``key=None``
        clears the slot."""
        if key is not None:
            for slots in self.keys.values():
                for i, k in enumerate(slots):
                    if k == key:
                        slots[i] = None
        self.keys[action][slot] = key

    def reset_keys(self):
        self.keys = {a: list(k) for a, k in DEFAULT_KEYS.items()}


def _number(value, default, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return min(max(float(value), lo), hi)


current = Settings()


def settings_file():
    return savegame.SAVE_ROOT / "settings.json"


def load():
    """Read the saved settings into :data:`current` (defaults if none)."""
    global current
    try:
        with open(settings_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        current = Settings.from_dict(data if isinstance(data, dict) else {})
    except (OSError, ValueError):
        current = Settings()
    return current


def save():
    path = settings_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(current.to_dict(), f, indent=2)
    except OSError:
        pass   # settings still apply for this session


def pressed(event, action):
    """True for a KEYDOWN of one of ``action``'s keys."""
    return (event.type == pygame.KEYDOWN
            and event.key in current.keys[action])


def held(keys, action):
    """True while one of ``action``'s keys is down (``keys`` from
    ``pygame.key.get_pressed()``)."""
    return any(keys[k] for k in current.keys[action] if k is not None)


def key_label(key):
    """Short display name of a key (``"-"`` for an empty slot)."""
    if key is None:
        return "-"
    name = pygame.key.name(key)
    return name.title() if name else f"#{key}"


def action_label(action):
    """The first bound key of ``action``, for hints ("E", "Space")."""
    for k in current.keys[action]:
        if k is not None:
            return key_label(k)
    return "-"
