# pygame_rpg/audio.py
"""Sound effects and the sewer ambience, all synthesised at start-up.

No audio files: every sound is built from sine / square / saw waves and
filtered noise in plain Python (``_Synth`` and the ``_RECIPES`` table),
so nothing needs licensing and the repo stays text-only.  Building them
takes a moment, so ``init()`` does it on a background thread; a sound
asked for before it is ready is simply skipped.

Use the module-level helpers:

* ``play(name, delay=0)``: a one-shot effect.  A name with variants
  ("step" -> "step0".."step2") picks one at random.  ``delay`` (seconds)
  lets a follow-up (the enemy's counter-hit) land after the first sound.
* ``set_ambience(name)``: the loop for the current screen ("sewer" or
  None).  Changing it fades the old loop out and the new one in.  The
  sewer loop is bubbling, flowing water; ``update`` scatters drips,
  distant metal clanks, pipe groans and the odd rat squeak over it.
* ``update(dt)``: once per frame from ``main.py`` (delays, ambience).
* ``toggle_mute()``: M in game.

If the mixer can't start (no sound device, or the dummy driver in a
broken state) every call is a no-op, so the game and tests run silent.

The built sounds are cached as raw PCM in ``saves/cache/audio-<key>/``
(``<key>`` changes with the mixer format and the synthesis code), so
later starts skip the synthesis; that matters on a phone, where it is
slow.  A missing, partial or unwritable cache just means building.
"""

import hashlib
import marshal
import math
import random
import shutil
import sys
import threading
import time
from array import array

import pygame

from . import savegame, settings

RATE = 22050          # mixer frequency asked for in pre_init()
AMBIENT_FADE = 800    # ms to fade the ambience loop in / out


# --- synthesis ----------------------------------------------------------
class _Synth:
    """Mono float buffers (lists, -1..1) at ``rate`` and the building
    blocks the recipes combine."""

    def __init__(self, rate, seed=7):
        self.rate = rate
        self.rng = random.Random(seed)

    def n(self, seconds):
        return max(1, int(seconds * self.rate))

    def silence(self, seconds):
        return [0.0] * self.n(seconds)

    def noise(self, seconds):
        r = self.rng.uniform
        return [r(-1, 1) for _ in range(self.n(seconds))]

    def tone(self, f0, f1, seconds, wave="sine", vibrato=0.0, vib_rate=6.0):
        """A tone gliding exponentially from ``f0`` to ``f1`` Hz."""
        n = self.n(seconds)
        out, phase = [], 0.0
        ratio = f1 / f0
        for i in range(n):
            t = i / n
            f = f0 * ratio ** t
            if vibrato:
                f *= 1 + vibrato * math.sin(2 * math.pi * vib_rate * i / self.rate)
            phase = (phase + f / self.rate) % 1.0
            if wave == "sine":
                v = math.sin(2 * math.pi * phase)
            elif wave == "square":
                v = 1.0 if phase < 0.5 else -1.0
            elif wave == "saw":
                v = 2 * phase - 1
            else:  # triangle
                v = 4 * abs(phase - 0.5) - 1
            out.append(v)
        return out

    @staticmethod
    def lowpass(buf, alpha):
        """One-pole low-pass; smaller ``alpha`` = darker."""
        y, out = 0.0, []
        for x in buf:
            y += alpha * (x - y)
            out.append(y)
        return out

    def highpass(self, buf, alpha):
        lo = self.lowpass(buf, alpha)
        return [a - b for a, b in zip(buf, lo)]

    def sweep_lowpass(self, buf, a0, a1):
        """Low-pass whose ``alpha`` moves from a0 to a1 (a whoosh)."""
        y, out, n = 0.0, [], len(buf)
        for i, x in enumerate(buf):
            y += (a0 + (a1 - a0) * i / n) * (x - y)
            out.append(y)
        return out

    def env(self, buf, attack=0.005, decay=8.0, hold=0.0):
        """Linear attack over ``attack`` s, then exponential decay
        (``decay`` per second) after an optional ``hold``."""
        a, h = max(1, self.n(attack)), self.n(hold)
        out = []
        for i, x in enumerate(buf):
            if i < a:
                g = i / a
            elif i < a + h:
                g = 1.0
            else:
                g = math.exp(-decay * (i - a - h) / self.rate)
            out.append(x * g)
        return out

    @staticmethod
    def swell(buf):
        """Rise then fall (sin envelope) over the whole buffer."""
        n = len(buf)
        return [x * math.sin(math.pi * i / n) for i, x in enumerate(buf)]

    @staticmethod
    def gain(buf, g):
        return [x * g for x in buf]

    def mix(self, *parts):
        """Sum ``(buffer, start seconds)`` pairs (or bare buffers at 0)."""
        placed = [(p, 0.0) if isinstance(p, list) else p for p in parts]
        n = max(self.n(s) + len(b) for b, s in placed)
        out = [0.0] * n
        for buf, start in placed:
            o = self.n(start) if start else 0
            for i, x in enumerate(buf):
                out[o + i] += x
        return out

    def seq(self, notes, wave="square", step=0.08, decay=10.0, vol=0.35):
        """Notes (Hz, or None for a rest) one after another."""
        parts = []
        for i, f in enumerate(notes):
            if f:
                parts.append((self.env(self.tone(f, f, step * 2.5, wave),
                                       decay=decay), i * step))
        return self.gain(self.mix(*parts), vol)

    def echo(self, buf, delay=0.11, feedback=0.35, taps=4):
        """Repeating, fading copies: the sewer tunnels' reverb."""
        parts = [(buf, 0.0)]
        for k in range(1, taps + 1):
            parts.append((self.gain(self.lowpass(buf, 0.5), feedback ** k),
                          delay * k))
        return self.mix(*parts)

    def loop(self, buf, fade_seconds):
        """Crossfade the tail into the head so the buffer loops cleanly."""
        f = self.n(fade_seconds)
        body = buf[:-f]
        for i in range(f):
            t = i / f
            body[i] = body[i] * t + buf[len(buf) - f + i] * (1 - t)
        return body


def _note(name):
    """'A4' style note name -> Hz."""
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    semis = names[name[0]] + (1 if "#" in name else 0)
    octave = int(name[-1])
    return 440.0 * 2 ** ((semis + 12 * (octave - 4)) / 12)


def _notes(text):
    return [None if t == "-" else _note(t) for t in text.split()]


# Each recipe takes a _Synth and returns a buffer.  Kept short and
# quiet-ish; the effects volume setting scales them all.
def _step(s, pitch):
    # A splashy footstep in shallow sewer water.
    thud = s.env(s.lowpass(s.noise(0.09), 0.08 * pitch), attack=0.004, decay=40)
    splash = s.env(s.highpass(s.noise(0.14), 0.3), attack=0.01, decay=28)
    return s.gain(s.mix(s.gain(thud, 1.6), (s.gain(splash, 0.35), 0.015)), 0.9)


def _whoosh(s, seconds=0.2, a0=0.05, a1=0.4, vol=0.6):
    return s.gain(s.swell(s.sweep_lowpass(s.noise(seconds), a0, a1)), vol)


def _thud(s, f0=150, f1=60, seconds=0.18, vol=0.8, crunch=0.4):
    body = s.env(s.tone(f0, f1, seconds), attack=0.002, decay=18)
    grit = s.env(s.lowpass(s.noise(seconds * 0.5), 0.3), attack=0.001, decay=40)
    return s.gain(s.mix(body, s.gain(grit, crunch)), vol)


def _door(s):
    # Rusty grate: a wobbling, scraping creak, then a clank.
    creak = s.tone(70, 105, 0.5, "saw", vibrato=0.08, vib_rate=23)
    creak = s.gain(s.swell(s.lowpass(creak, 0.25)), 0.35)
    clank = s.env(s.mix(s.tone(420, 400, 0.25), s.gain(s.tone(587, 560, 0.25), 0.6)),
                  decay=14)
    return s.echo(s.mix(creak, (s.gain(clank, 0.3), 0.45),
                        (_thud(s, 120, 70, 0.15, 0.6), 0.45)))


def _chest(s):
    lid = s.mix(_thud(s, 180, 90, 0.12, 0.6, 0.6),
                (s.gain(s.swell(s.lowpass(s.tone(300, 380, 0.2, "saw"), 0.2)), 0.2),
                 0.02))
    sparkle = s.seq(_notes("E6 G6 B6 E7"), "sine", step=0.055, decay=14, vol=0.3)
    return s.mix(lid, (sparkle, 0.18))


def _strike(s):
    return s.mix(_whoosh(s, 0.16, 0.06, 0.35), (_thud(s, 160, 70, 0.18), 0.1))


def _slash(s):
    shing = s.env(s.mix(s.tone(2400, 2300, 0.3), s.tone(3170, 3100, 0.3)),
                  decay=16)
    return s.mix(_whoosh(s, 0.14, 0.15, 0.7, 0.55),
                 (s.gain(shing, 0.16), 0.09),
                 (_thud(s, 220, 120, 0.1, 0.45, 0.7), 0.09))


def _bash(s):
    return s.mix(_whoosh(s, 0.2, 0.03, 0.2, 0.5),
                 (_thud(s, 95, 40, 0.3, 1.0, 0.9), 0.14))


def _heavy(s):
    boom = s.env(s.lowpass(s.noise(0.5), 0.06), attack=0.003, decay=7)
    return s.mix(_whoosh(s, 0.38, 0.02, 0.25, 0.7),
                 (_thud(s, 110, 30, 0.45, 1.0, 1.0), 0.3),
                 (s.gain(boom, 0.9), 0.3))


def _shoot(s):
    # A bow string's twang and the arrow's whoosh.
    twang = s.env(s.tone(220, 180, 0.25, "triangle", vibrato=0.03, vib_rate=30),
                  decay=14)
    return s.mix(s.gain(twang, 0.4), (_whoosh(s, 0.18, 0.2, 0.6, 0.4), 0.02))


def _crack(s):
    # Wood splintering: sharp snaps over a hollow knock.
    snaps = [(s.gain(s.env(s.highpass(s.noise(0.06), 0.4), attack=0.001,
                           decay=60), 0.6), t) for t in (0.0, 0.03, 0.07, 0.12)]
    return s.mix(_thud(s, 200, 90, 0.2, 0.7, 0.8), *snaps)


def _shatter(s):
    # Clay or stone breaking: a crunch and a few bright shards.
    crunch = s.env(s.lowpass(s.noise(0.25), 0.5), attack=0.001, decay=18)
    shards = s.seq([2600, 3100, 2200, 3600], "sine", step=0.035, decay=30, vol=0.15)
    return s.mix(s.gain(crunch, 0.7), (shards, 0.02),
                 _thud(s, 160, 80, 0.12, 0.5, 0.6))


def _miss(s):
    return s.mix(_whoosh(s, 0.3, 0.3, 0.04, 0.55))


def _hurt(s):
    grunt = s.env(s.lowpass(s.tone(240, 120, 0.2, "square"), 0.2), decay=12)
    return s.mix(_thud(s, 140, 60, 0.15, 0.7, 0.8), s.gain(grunt, 0.35))


def _magic(s):
    sweep = s.env(s.tone(380, 1500, 0.4, "triangle", vibrato=0.03, vib_rate=11),
                  attack=0.03, decay=5)
    return s.mix(s.gain(sweep, 0.3),
                 (s.seq(_notes("A6 C#7 E7"), "sine", 0.05, 16, 0.18), 0.2),
                 (_thud(s, 300, 140, 0.12, 0.4, 0.5), 0.35))


def _heal(s):
    return s.mix(s.seq(_notes("C5 E5 G5 C6 E6"), "triangle", 0.07, 8, 0.4),
                 (s.env(s.tone(1046, 1046, 0.5, "sine", 0.01, 5), decay=5), 0.3))


def _guard(s):
    chord = s.mix(*[s.tone(f, f, 0.6, "triangle", 0.005, 4)
                    for f in (_note("D5"), _note("A5"), _note("D6"))])
    return s.gain(s.env(chord, attack=0.08, decay=4), 0.18)


def _potion(s):
    parts = [(s.env(s.tone(f, f * 1.8, 0.06), attack=0.005, decay=30), i * 0.07)
             for i, f in enumerate((300, 380, 340, 460))]
    return s.gain(s.mix(*parts), 0.45)


def _bomb(s):
    blast = s.env(s.lowpass(s.noise(0.8), 0.12), attack=0.002, decay=5)
    return s.mix(s.gain(blast, 1.0), _thud(s, 90, 25, 0.5, 1.0, 1.0))


def _ailment(s):
    return s.gain(s.env(s.tone(330, 220, 0.3, "square", 0.06, 14),
                        attack=0.01, decay=7), 0.2)


def _run(s):
    return s.mix(*[(_step(s, 1.3), i * 0.09) for i in range(4)])


def _fail(s):
    return s.seq([110, 98], "square", 0.12, 12, 0.3)


def _encounter(s):
    tremolo = s.mix(s.tone(_note("A2"), _note("A2"), 0.7, "saw"),
                    s.tone(_note("D#3"), _note("D#3"), 0.7, "saw"))
    tremolo = [x * (0.6 + 0.4 * math.sin(i / s.rate * 2 * math.pi * 14))
               for i, x in enumerate(tremolo)]
    sting = s.env(s.lowpass(tremolo, 0.2), attack=0.01, decay=4)
    return s.mix(s.gain(sting, 0.4), _thud(s, 80, 40, 0.3, 0.7, 0.5))


def _victory(s):
    return s.seq(_notes("G4 C5 E5 G5 - E5 G5"), "square", 0.1, 6, 0.22)


def _defeat(s):
    return s.seq(_notes("E4 D#4 D4 C#4"), "triangle", 0.28, 3, 0.4)


def _level_up(s):
    run = s.seq(_notes("C5 E5 G5 C6 E6 G6"), "square", 0.06, 10, 0.2)
    chord = s.mix(*[s.env(s.tone(_note(n), _note(n), 0.8, "triangle"), decay=3)
                    for n in ("C6", "E6", "G6")])
    return s.mix(run, (s.gain(chord, 0.15), 0.36))


def _stairs(s):
    steps = [(s.gain(_step(s, 0.7 - 0.08 * i), 2.0 - 0.3 * i), i * 0.16)
             for i in range(5)]
    return s.echo(s.mix(*steps), 0.15, 0.4)


def _click(s):
    return s.gain(s.env(s.tone(1200, 900, 0.04, "square"), decay=60), 0.12)


def _drip(s, f):
    plink = s.env(s.tone(f, f * 1.9, 0.07), attack=0.001, decay=45)
    return s.echo(s.gain(plink, 0.5), 0.13, 0.45, 5)


def _groan(s):
    # ~70 Hz so laptop speakers still carry it.
    pipe = s.tone(72, 62, 2.2, "saw", vibrato=0.04, vib_rate=0.9)
    return s.gain(s.swell(s.lowpass(s.lowpass(pipe, 0.04), 0.08)), 0.9)


def _squeak(s):
    parts = [(s.env(s.tone(f, f * 1.2, 0.05, "triangle"), decay=40), i * 0.08)
             for i, f in enumerate((3200, 3600, 3000))]
    return s.gain(s.mix(*parts), 0.12)


def _clank(s, base, hits=1):
    """Distant metal: inharmonic bar partials, muffled, with a long
    tunnel echo.  ``hits`` > 1 knocks a few times (a pipe being hit)."""
    parts = []
    for k in range(hits):
        bar = s.mix(*[s.gain(s.env(s.tone(base * r, base * r, 1.2), attack=0.001,
                                   decay=4 + 3 * r), 1 / (1 + r))
                      for r in (1.0, 2.76, 5.4, 8.93)])
        parts.append((s.gain(bar, 0.8 if k else 1.0), k * 0.28))
    muffled = s.lowpass(s.lowpass(s.mix(*parts), 0.35), 0.5)
    return s.echo(muffled, 0.19, 0.5, 6)


def _sewer_loop(s, seconds=8.0):
    """Flowing water built from bubbles: a stream of tiny rising "blip"
    grains (trickle) over slower, deeper gurgles, plus a faint rumble to
    glue them.  Grains wrap around the end, so the buffer loops cleanly."""
    n = s.n(seconds)
    out = s.gain(s.loop(s.lowpass(s.lowpass(s.noise(seconds + 0.5), 0.03), 0.06),
                        0.5), 4.0)
    out = (out + [0.0] * n)[:n]
    layers = [  # (grains per second, Hz range, grain seconds, loudness)
        (34, (700, 1900), (0.02, 0.05), 0.16),   # trickle
        (14, (220, 520), (0.05, 0.11), 0.28),    # gurgle
        (4, (110, 200), (0.10, 0.18), 0.30),     # deep glugs
    ]
    rng = s.rng
    for rate, (f_lo, f_hi), (d_lo, d_hi), vol in layers:
        for _ in range(int(rate * seconds)):
            f = rng.uniform(f_lo, f_hi)
            grain = s.env(s.tone(f, f * rng.uniform(1.3, 2.0), rng.uniform(d_lo, d_hi)),
                          attack=0.003, decay=rng.uniform(25, 60))
            amp = vol * rng.uniform(0.3, 1.0)
            o = rng.randrange(n)
            for i, x in enumerate(grain):
                out[(o + i) % n] += x * amp
    return out


_RECIPES = {
    "step0": lambda s: _step(s, 1.0),
    "step1": lambda s: _step(s, 0.8),
    "step2": lambda s: _step(s, 1.2),
    "door": _door,
    "chest": _chest,
    "strike": _strike,
    "slash": _slash,
    "bash": _bash,
    "heavy": _heavy,
    "miss": _miss,
    "shoot": _shoot,
    "crack": _crack,
    "shatter": _shatter,
    "hurt": _hurt,
    "magic": _magic,
    "heal": _heal,
    "guard": _guard,
    "potion": _potion,
    "bomb": _bomb,
    "ailment": _ailment,
    "run": _run,
    "fail": _fail,
    "encounter": _encounter,
    "victory": _victory,
    "defeat": _defeat,
    "level_up": _level_up,
    "stairs": _stairs,
    "click": _click,
    "drip0": lambda s: _drip(s, 900),
    "drip1": lambda s: _drip(s, 1150),
    "drip2": lambda s: _drip(s, 1400),
    "drip3": lambda s: _drip(s, 1700),
    "groan": _groan,
    "clank0": lambda s: _clank(s, 190),
    "clank1": lambda s: _clank(s, 260, hits=2),
    "clank2": lambda s: _clank(s, 330),
    "clank3": lambda s: _clank(s, 150, hits=3),
    "squeak": _squeak,
    "sewer": _sewer_loop,
}

# Ambient one-shots per ambience: (sound, mean seconds between plays).
_SCATTER = {
    "sewer": [("drip", 1.8), ("clank", 9.0), ("groan", 30.0), ("squeak", 45.0)],
}


def _to_pcm(buf, channels, peak=0.9):
    """Float buffer -> int16 PCM bytes, ``channels`` interleaved."""
    top = max((abs(x) for x in buf), default=0.0)
    scale = 32767 * peak / top if top > 1.0 else 32767 * peak
    pcm = array("h")
    for x in buf:
        v = int(x * scale)
        pcm.extend((v,) * channels)
    return pcm.tobytes()


# --- cache --------------------------------------------------------------------
def _code_key():
    """Fingerprint of the synthesis code: every function and _Synth
    method in this module (works from .pyc files too, as in the APK)."""
    h = hashlib.sha1()
    funcs = [v for v in globals().values() if callable(getattr(v, "__code__", None))]
    funcs += [v for v in vars(_Synth).values()
              if callable(getattr(v, "__code__", None))]
    for f in sorted(funcs, key=lambda f: f.__qualname__):
        h.update(f.__qualname__.encode())
        h.update(marshal.dumps(f.__code__.co_code))
        h.update(repr(f.__code__.co_consts).encode())
    return h.hexdigest()[:12]


def cache_root():
    return savegame.SAVE_ROOT / "cache"


def _cache_folder(freq, channels):
    return cache_root() / f"audio-{freq}-{channels}-{_code_key()}"


def _load_cache(folder):
    """{name: pcm bytes} for every recipe, or None unless all are there."""
    try:
        return {name: (folder / f"{name}.pcm").read_bytes() for name in _RECIPES}
    except OSError:
        return None


def _save_cache(folder, pcms):
    """Write the cache (dropping caches of older code or formats)."""
    try:
        root = folder.parent
        if root.exists():
            for old in root.glob("audio-*"):
                if old != folder:
                    shutil.rmtree(old, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        for name, pcm in pcms.items():
            (folder / f"{name}.pcm").write_bytes(pcm)
    except OSError:
        pass   # no cache; the next start builds again


# --- runtime ----------------------------------------------------------------
class Audio:
    def __init__(self):
        self.ok = False
        self.muted = False
        self.sounds = {}            # name -> Sound, filled by the builder
        self.pending = []           # [seconds left, name]
        self.ambience = None
        self.loop_channel = None
        self.next_scatter = {}      # sound -> seconds until it plays
        self.rng = random.Random()

    def init(self, background=True):
        """Start building sounds if the mixer is up.  Safe to call twice."""
        if self.ok:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 2, 512)
            freq, size, channels = pygame.mixer.get_init()
        except pygame.error:
            return
        if size not in (-16, 16):
            return   # buffers are built as int16
        self.ok = True
        pygame.mixer.set_num_channels(16)
        self.loop_channel = pygame.mixer.Channel(0)
        pygame.mixer.set_reserved(1)
        if background:
            threading.Thread(target=self._build, args=(freq, channels),
                             daemon=True).start()
        else:
            self._build(freq, channels)

    def _build(self, freq, channels):
        folder = _cache_folder(freq, channels)
        cached = _load_cache(folder)
        synth = _Synth(freq)
        pcms = {}
        # Synthesis is pure Python on this thread and shares the GIL with
        # the game: hand it back to the game loop every 1 ms instead of
        # every 5 ms, and pause between sounds, so frames don't stutter
        # while it runs (it is slow on a phone, and only happens until the
        # cache exists).
        switch = sys.getswitchinterval()
        if cached is None:
            sys.setswitchinterval(0.001)
        try:
            # The loop first: it is what the dungeon needs immediately.
            for name in ["sewer"] + [k for k in _RECIPES if k != "sewer"]:
                try:
                    if cached is not None:
                        pcm = cached[name]
                    else:
                        pcm = pcms[name] = _to_pcm(_RECIPES[name](synth), channels)
                        time.sleep(0.01)
                    self.sounds[name] = pygame.mixer.Sound(buffer=pcm)
                except pygame.error:
                    return
        finally:
            sys.setswitchinterval(switch)
        if cached is None:
            _save_cache(folder, pcms)

    def _get(self, name):
        if name in self.sounds:
            return self.sounds[name]
        variants = [v for k, v in self.sounds.items()
                    if k[:-1] == name and k[-1].isdigit()]
        return self.rng.choice(variants) if variants else None

    def play(self, name, delay=0.0, volume=1.0):
        if not self.ok or self.muted:
            return
        if delay > 0:
            self.pending.append([delay, name, volume])
            return
        sound = self._get(name)
        if sound is not None:
            ch = sound.play()
            if ch is not None:
                ch.set_volume(settings.current.effects_volume * volume)

    def set_ambience(self, name):
        if not self.ok or name == self.ambience:
            return
        self.ambience = name
        self.next_scatter = {}
        self.loop_channel.fadeout(AMBIENT_FADE)
        self._start_loop()

    def _start_loop(self):
        sound = self.sounds.get(self.ambience) if self.ambience else None
        if sound is not None and not self.muted:
            self.loop_channel.play(sound, loops=-1, fade_ms=AMBIENT_FADE)
            self.loop_channel.set_volume(settings.current.ambience_volume)

    def refresh_volume(self):
        """Apply a changed ambience volume to the loop already playing
        (effects pick up theirs on the next play)."""
        if self.ok:
            self.loop_channel.set_volume(settings.current.ambience_volume)

    def toggle_mute(self):
        self.muted = not self.muted
        if not self.ok:
            return
        if self.muted:
            pygame.mixer.stop()
            self.pending.clear()
        else:
            self._start_loop()

    def pause(self):
        """The app went to the background: silence everything."""
        if self.ok:
            pygame.mixer.pause()

    def resume(self):
        if self.ok:
            pygame.mixer.unpause()

    def update(self, dt):
        if not self.ok:
            return
        due = [p for p in self.pending if p[0] - dt <= 0]
        self.pending = [[t - dt, n, v] for t, n, v in self.pending if t - dt > 0]
        for _, name, volume in due:
            self.play(name, volume=volume)
        if self.muted or self.ambience is None:
            return
        # The loop sound may finish building after the ambience was set.
        if not self.loop_channel.get_busy():
            self._start_loop()
        for name, mean in _SCATTER.get(self.ambience, ()):
            left = self.next_scatter.get(name)
            if left is None:
                left = self.rng.expovariate(1 / mean)
            left -= dt
            if left <= 0:
                sound = self._get(name)
                if sound is not None:
                    ch = sound.play()
                    if ch is not None:
                        # Random pan and distance.
                        far = self.rng.uniform(0.3, 1.0)
                        pan = self.rng.random()
                        v = settings.current.ambience_volume * far
                        ch.set_volume(v * (1 - pan) * 2 if pan > 0.5 else v,
                                      v * pan * 2 if pan < 0.5 else v)
                left = self.rng.expovariate(1 / mean)
            self.next_scatter[name] = left


_audio = Audio()
init = _audio.init
play = _audio.play
set_ambience = _audio.set_ambience
toggle_mute = _audio.toggle_mute
refresh_volume = _audio.refresh_volume
pause = _audio.pause
resume = _audio.resume
update = _audio.update


def pre_init():
    """Call before ``pygame.init()`` so the mixer opens at RATE with a
    small buffer (low latency for hits)."""
    pygame.mixer.pre_init(RATE, -16, 2, 512)
