"""Turn-based battle logic (M4): pure rules, no drawing.

One ``Battle`` is one fight between the hero and every enemy in the
room (one or more).  The hero picks a target (``set_target`` /
``cycle_target``; it moves on by itself when the target falls); attacks,
damaging abilities and bombs hit the target only.  Every hero action
(attack / cast / use item / run) is followed by the enemies' turn: each
living enemy acts once.  The fight is won when all of them are down.
Actions return the log lines they produced; ``gui/battle_screen.py``
shows them.

Damage
    hero hit  = (attack stat + power) x 0.85..1.15 - enemy defense
    enemy hit = (2 x enemy attack) x 0.85..1.15 - hero defense - guard
    (minimum 1).  The attack stat follows the attack type: melee -> ap,
    ranged -> rap, magic -> map, using ``Player.total()`` (equipment
    included); the hero's defense likewise uses dp / rdp / mdp.
    Weapon power = 4 + 2 x weapon level (2 unarmed); an ability's power
    is half its ``damage`` (it adds on top of the stat and the ailment);
    bombs deal their ``damage`` flat, ignoring defense.  The numbers in
    this docstring are the defaults in ``config.py`` (Balance section).

Ailments (``AILMENTS``) tick at the start of the afflicted side's turn:
damage over time, and stun / electrocuted skip that turn.  Weapon and
ability tiers raise the chance (+5 per level above 1, abilities +20);
a ward trinket cuts the chance by 25% per ward level (level 4 = immune).

Attack styles (``STYLES``) depend on the weapon: every weapon
(``WEAPON_STYLES``, by level-1 id; tiers share it) offers its own four,
the first being the plain hit with the weapon's own ailment.  The others
trade damage for something: a likelier ailment, ignoring part of the
enemy's defense (``pierce``), several weaker hits (``hits``), hitting
every enemy at once (``sweep``), double damage on a target that already
has an ailment (``exploit``), healing from the damage (``drain``), extra
defense during the enemies' reply (``guard``), or a big hit that can
miss.  Staff and wand power spells cost MP (``mp``).

Previews: ``attack_preview`` / ``cast_preview`` give the min-max damage an
action would deal right now, ``incoming_preview`` the enemy's next hit
on the hero from all living enemies together (shown by the battle
screen before you choose).

Winning adds the XP of every enemy to ``player.xp`` (trinket xp bonus
applied); gold, loot, junk and blueprints are rolled per enemy.  Levels are
*not* banked here: the Base's level-up screen still lets the player pick
stats, exactly as before.  Loot comes from ``items.roll_loot``.
"""
from dataclasses import dataclass

from .config import (
    WEAPON_POWER_BASE, WEAPON_POWER_PER_LEVEL, UNARMED_POWER, ENEMY_HIT_MULT,
    DAMAGE_VARIANCE, ABILITY_CHANCE_BONUS, LEVEL_CHANCE_BONUS, WARD_PER_LEVEL,
    BOMB_EFFECT_CHANCE, RUN_CHANCE, RUN_PER_EXTRA_ENEMY, RUN_CHANCE_RANGE,
    LOOT_CHANCE, WIN_HEAL_PCT, WIN_MP,
)
from .config import (
    ENEMY_GOLD, BOSS_GOLD_MULT, ENEMY_JUNK_CHANCE, BLUEPRINT_ENEMY_CHANCE,
)
from .crafting import roll_blueprint
from .items import roll_loot, roll_junk, item_by_id

ONGOING, WON, LOST, FLED = "ongoing", "won", "lost", "fled"


@dataclass(frozen=True)
class Ailment:
    chance: int      # % per hit at level 1
    turns: int       # how long it lasts
    dot: int = 0     # damage at the start of each afflicted turn
    skip: bool = False  # afflicted side loses its turn


AILMENTS = {
    "bleeding": Ailment(chance=25, turns=3, dot=3),
    "poison": Ailment(chance=30, turns=3, dot=3),
    "burning": Ailment(chance=25, turns=2, dot=5),
    "stun": Ailment(chance=20, turns=1, skip=True),
    "electrocuted": Ailment(chance=20, turns=1, dot=2, skip=True),
}
# How the log names someone who just got an ailment ("You are poisoned!").
AFFLICTED = {"bleeding": "bleeding", "poison": "poisoned", "burning": "burning",
             "stun": "stunned", "electrocuted": "electrocuted"}

# Tuning numbers (chances, powers, recovery) live in config.py.

@dataclass(frozen=True)
class AttackStyle:
    name: str
    mult: float          # damage multiplier (per hit)
    effect: str = None   # ailment it causes; None = the weapon's own
    chance: int = 0      # extra ailment chance (%)
    miss: int = 0        # chance to miss (%)
    note: str = ""       # one-line description for the menu
    pierce: float = 0.0  # share of the enemy's defense it ignores
    hits: int = 1        # hits on the target (each rolls damage + ailment)
    sweep: bool = False  # hits every living enemy instead of the target
    exploit: float = 0.0  # extra multiplier on a target that has an ailment
    drain: int = 0       # % of the damage dealt healed back
    guard: int = 0       # + to every defense during the enemies' reply
    mp: int = 0          # MP the attack costs
    sound: str = "strike"


def _s(name, mult, sound, note, **kw):
    return AttackStyle(name, mult, note=note, sound=sound, **kw)


# Every attack in the game, by key.  Each weapon (by level-1 id) offers
# its own four (``WEAPON_STYLES``); the first one is its plain hit with
# the weapon's own ailment.
STYLES = {
    # bare hands
    "punch": _s("Punch", 1.0, "strike", "plain hit"),
    "kick": _s("Kick", 0.8, "bash", "may stun", effect="stun", chance=15),
    "haymaker": _s("Haymaker", 1.35, "heavy", "25% miss", effect="", miss=25),
    # sword: the all-rounder
    "strike": _s("Strike", 1.0, "strike", "weapon ailment"),
    "slash": _s("Slash", 0.75, "slash", "more bleeding", effect="bleeding", chance=30),
    "thrust": _s("Thrust", 0.9, "strike", "ignores half armor", pierce=0.5),
    "parry": _s("Parry", 0.6, "strike", "+4 defense", guard=4),
    # saber: quick curved cuts
    "cut": _s("Cut", 1.0, "slash", "weapon ailment"),
    "twin_cut": _s("Twin Cuts", 0.55, "slash", "2 quick cuts", hits=2),
    "draw_cut": _s("Draw Cut", 0.75, "slash", "deep bleeding", effect="bleeding", chance=35),
    "flourish": _s("Flourish", 0.6, "slash", "all foes", sweep=True),
    # greatsword: slow, huge swings
    "hew": _s("Hew", 1.0, "heavy", "weapon ailment"),
    "cleave": _s("Cleave", 0.65, "slash", "all foes", sweep=True),
    "overhead": _s("Overhead", 1.5, "heavy", "30% miss", effect="", miss=30),
    "pommel": _s("Pommel Bash", 0.7, "bash", "may stun", effect="stun", chance=20),
    # dagger: fast and dirty
    "stab": _s("Stab", 1.0, "strike", "weapon ailment"),
    "flurry": _s("Flurry", 0.4, "slash", "3 quick stabs", hits=3),
    "backstab": _s("Backstab", 0.8, "strike", "x2 on ailing foe", exploit=1.0),
    "venom_edge": _s("Venom Edge", 0.7, "slash", "poisons", effect="poison", chance=30),
    # spear: reach and armor piercing
    "jab": _s("Jab", 1.0, "strike", "weapon ailment"),
    "impale": _s("Impale", 0.9, "heavy", "ignores armor", pierce=1.0),
    "sweep": _s("Sweep", 0.6, "slash", "all foes", sweep=True),
    "brace": _s("Brace", 0.6, "strike", "+5 defense", guard=5),
    # warhammer: crushing power
    "smash": _s("Smash", 1.0, "bash", "weapon ailment"),
    "slam": _s("Ground Slam", 0.55, "heavy", "all foes", sweep=True),
    "armor_break": _s("Armor Break", 0.85, "heavy", "ignores armor", pierce=1.0),
    "colossal": _s("Colossal Swing", 1.6, "heavy", "35% miss", effect="", miss=35),
    # mace: steady blows
    "bash": _s("Bash", 1.0, "bash", "weapon ailment"),
    "crush": _s("Crush", 0.9, "heavy", "ignores half armor", pierce=0.5),
    "daze": _s("Daze", 0.7, "bash", "likely stun", effect="stun", chance=25),
    "flail": _s("Flail", 0.55, "bash", "hits twice", hits=2),
    # club: crude brawling
    "whack": _s("Whack", 1.0, "bash", "weapon ailment"),
    "clobber": _s("Clobber", 0.8, "bash", "may stun", effect="stun", chance=15),
    "wild_swing": _s("Wild Swing", 1.4, "heavy", "25% miss", effect="", miss=25),
    "shove": _s("Shove", 0.5, "bash", "+4 defense", guard=4),
    # bow: range and volleys
    "shot": _s("Shot", 1.0, "shoot", "weapon ailment"),
    "aimed": _s("Aimed Shot", 0.9, "shoot", "ignores armor", pierce=1.0),
    "volley": _s("Volley", 0.6, "shoot", "all foes", sweep=True),
    "barbed": _s("Barbed Arrow", 0.75, "shoot", "more bleeding",
                 effect="bleeding", chance=30),
    # crossbow: heavy bolts
    "bolt": _s("Bolt", 1.0, "shoot", "weapon ailment"),
    "heavy_bolt": _s("Heavy Bolt", 1.4, "shoot", "20% miss", miss=20, pierce=0.5),
    "piercer": _s("Armor Piercer", 0.9, "shoot", "no armor", pierce=1.0),
    "pin": _s("Pin Down", 0.7, "shoot", "likely stun", effect="stun", chance=25),
    # blowpipe: poisons and tricks
    "dart": _s("Dart", 1.0, "shoot", "weapon ailment"),
    "poison_dart": _s("Poison Dart", 0.6, "shoot", "strong poison", effect="poison", chance=40),
    "darts": _s("Twin Darts", 0.5, "shoot", "2 quick darts", hits=2),
    "sleep_dart": _s("Sleep Dart", 0.4, "shoot", "very likely stun", effect="stun", chance=35),
    # boomerang: comes back around
    "throw": _s("Throw", 1.0, "shoot", "weapon ailment"),
    "ricochet": _s("Ricochet", 0.6, "shoot", "all foes", sweep=True),
    "round_trip": _s("Round Trip", 0.55, "shoot", "hits twice", hits=2),
    "knockout": _s("Knockout", 0.7, "bash", "likely stun", effect="stun", chance=25),
    # slingshot: stones
    "pebble": _s("Pebble", 1.0, "shoot", "weapon ailment"),
    "headshot": _s("Headshot", 0.7, "bash", "likely stun", effect="stun", chance=25),
    "scatter": _s("Scattershot", 0.6, "shoot", "all foes", sweep=True),
    "rock": _s("Big Rock", 1.35, "heavy", "25% miss", effect="", miss=25),
    # whip: control
    "lash": _s("Lash", 1.0, "slash", "weapon ailment"),
    "crack": _s("Crack", 0.7, "bash", "likely stun", effect="stun", chance=25),
    "wide_lash": _s("Wide Lash", 0.6, "slash", "all foes", sweep=True),
    "lacerate": _s("Lacerate", 0.75, "slash", "makes them bleed",
                   effect="bleeding", chance=30),
    # poisonous staff: plagues
    "toxic_bolt": _s("Toxic Bolt", 1.0, "magic", "weapon ailment"),
    "venom_cloud": _s("Venom Cloud", 0.6, "magic", "all, 3 MP", sweep=True, mp=3),
    "plague": _s("Plague", 1.4, "magic", "strong, 5 MP", chance=20, mp=5),
    "wither": _s("Wither", 0.8, "magic", "x2 on ailing foe", exploit=1.0),
    # poisonous wand: siphoning
    "toxic_dart": _s("Toxic Dart", 1.0, "magic", "weapon ailment"),
    "needles": _s("Twin Needles", 0.5, "magic", "2 quick bolts", hits=2),
    "siphon": _s("Siphon", 0.8, "magic", "heals you 50%", drain=50),
    "envenom": _s("Envenom", 0.6, "magic", "strong poison", effect="poison", chance=40),
    # fiery staff: big fire
    "firebolt": _s("Firebolt", 1.0, "magic", "weapon ailment"),
    "flame_wave": _s("Flame Wave", 0.6, "magic", "all, 3 MP", sweep=True, mp=3),
    "meteor": _s("Meteor", 1.7, "magic", "5 MP, 25% miss", miss=25, mp=5),
    "ignite": _s("Ignite", 0.7, "magic", "sets ablaze", effect="burning", chance=30),
    # fiery wand: quick sparks
    "ember": _s("Ember", 1.0, "magic", "weapon ailment"),
    "fire_darts": _s("Fire Darts", 0.4, "magic", "3 quick bolts", hits=3),
    "flare": _s("Flare", 0.5, "magic", "blinds: stun", effect="stun", chance=25),
    "kindle": _s("Kindle", 0.7, "magic", "strong burning", effect="burning", chance=35),
    # electric staff: storms
    "spark": _s("Spark", 1.0, "magic", "weapon ailment"),
    "chain": _s("Chain Lightning", 0.6, "magic", "all, 3 MP", sweep=True, mp=3),
    "storm": _s("Thunderstorm", 0.9, "magic", "all, 5 MP", sweep=True, mp=5),
    "static_ward": _s("Static Ward", 0.5, "magic", "+5 defense", guard=5),
    # electric wand: precise shocks
    "zap": _s("Zap", 1.0, "magic", "weapon ailment"),
    "arc": _s("Arc", 0.55, "magic", "2 quick bolts", hits=2),
    "shock": _s("Shock", 0.6, "magic", "likely shock", effect="electrocuted", chance=35),
    "overload": _s("Overload", 1.0, "magic", "no armor, 3 MP", pierce=1.0, mp=3),
}

WEAPON_STYLES = {
    None: ("punch", "kick", "haymaker"),
    "sword": ("strike", "slash", "thrust", "parry"),
    "saber": ("cut", "twin_cut", "draw_cut", "flourish"),
    "greatsword": ("hew", "cleave", "overhead", "pommel"),
    "dagger": ("stab", "flurry", "backstab", "venom_edge"),
    "spear": ("jab", "impale", "sweep", "brace"),
    "warhammer": ("smash", "slam", "armor_break", "colossal"),
    "mace": ("bash", "crush", "daze", "flail"),
    "club": ("whack", "clobber", "wild_swing", "shove"),
    "bow": ("shot", "aimed", "volley", "barbed"),
    "crossbow": ("bolt", "heavy_bolt", "piercer", "pin"),
    "blowpipe": ("dart", "poison_dart", "darts", "sleep_dart"),
    "boomerang": ("throw", "ricochet", "round_trip", "knockout"),
    "slingshot": ("pebble", "headshot", "scatter", "rock"),
    "whip": ("lash", "crack", "wide_lash", "lacerate"),
    "poisonous_staff": ("toxic_bolt", "venom_cloud", "plague", "wither"),
    "poisonous_wand": ("toxic_dart", "needles", "siphon", "envenom"),
    "fiery_staff": ("firebolt", "flame_wave", "meteor", "ignite"),
    "fiery_wand": ("ember", "fire_darts", "flare", "kindle"),
    "electric_staff": ("spark", "chain", "storm", "static_ward"),
    "electric_wand": ("zap", "arc", "shock", "overload"),
}


def styles_for(weapon) -> tuple:
    """The attack keys a weapon (or bare hands, ``None``) offers; the
    first is its plain hit.  Unknown weapons fall back by type."""
    if weapon is None:
        return WEAPON_STYLES[None]
    head, _, tail = weapon.id.rpartition("_")
    base = head if head and tail.isdigit() else weapon.id
    if base not in WEAPON_STYLES:
        kind = weapon_type(weapon)
        base = ("bow" if kind == "ranged"
                else {"poison": "poisonous_staff", "electrocuted": "electric_staff"}
                .get(weapon.effect, "fiery_staff") if kind == "magic"
                else "mace" if weapon.effect == "stun" else "sword")
    return WEAPON_STYLES[base]


STAT_FOR = {"melee": "ap", "ranged": "rap", "magic": "map"}
DEFENSE_FOR = {"melee": "dp", "ranged": "rdp", "magic": "mdp"}


def weapon_type(weapon) -> str:
    """Attack type of a weapon from the stats it carries: rap -> ranged,
    map without ap -> magic, otherwise melee (also unarmed)."""
    if weapon is None:
        return "melee"
    if weapon.rap:
        return "ranged"
    if weapon.map and not weapon.ap:
        return "magic"
    return "melee"


def _labels(enemies) -> dict:
    """id(enemy) -> name in the log; enemies sharing a name get letters
    ("Slime A", "Slime B")."""
    count, seen, out = {}, {}, {}
    for e in enemies:
        count[e.name] = count.get(e.name, 0) + 1
    for e in enemies:
        if count[e.name] > 1:
            seen[e.name] = seen.get(e.name, 0) + 1
            out[id(e)] = f"{e.name} {chr(64 + seen[e.name])}"
        else:
            out[id(e)] = e.name
    return out


class Battle:
    def __init__(self, player, enemies, rng):
        self.player = player
        # One enemy or a list (everyone in the room).
        self.enemies = list(enemies) if isinstance(enemies, (list, tuple)) else [enemies]
        self.target = 0           # index into enemies
        self.names = _labels(self.enemies)
        self.rng = rng
        self.state = ONGOING
        self.cooldowns = {}       # ability id -> turns left
        self.statuses = {}        # hero ailments: name -> turns left
        self.guard = 0            # Shield bonus to every defense
        self.guard_turns = 0
        self.brace = 0            # attack-style defense for this round
        self.xp_gained = 0
        self.gold_gained = 0
        self.blueprint = None     # weapon base id of a blueprint found
        self.loot = []            # items put into the backpack
        boss = next((e for e in self.enemies if e.boss), None)
        if boss is not None:
            self.log = [f"The {boss.name} blocks the way!"]
        elif len(self.enemies) == 1:
            self.log = [f"A {self.enemies[0].name} appears!"]
        else:
            names = [self.name_of(e) for e in self.enemies]
            self.log = [f"{', '.join(names[:-1])} and {names[-1]} attack!"]

    # -- targets -------------------------------------------------------------
    @property
    def enemy(self):
        """The enemy the hero is aiming at."""
        return self.enemies[self.target]

    def name_of(self, enemy) -> str:
        return self.names.get(id(enemy), enemy.name)

    def alive(self) -> list:
        return [e for e in self.enemies if e.alive]

    def set_target(self, index) -> bool:
        """Aim at ``enemies[index]``; only living enemies can be picked."""
        if 0 <= index < len(self.enemies) and self.enemies[index].alive:
            self.target = index
            return True
        return False

    def cycle_target(self, step=1) -> None:
        """Aim at the next (``step`` 1) or previous (-1) living enemy."""
        n = len(self.enemies)
        for k in range(1, n + 1):
            if self.set_target((self.target + step * k) % n):
                return

    def _retarget(self) -> None:
        if not self.enemy.alive:
            self.cycle_target(1)

    # -- helpers -----------------------------------------------------------
    def _say(self, out, text):
        out.append(text)
        self.log.append(text)

    def _vary(self, value) -> float:
        return value * self.rng.uniform(*DAMAGE_VARIANCE)

    def _ward(self, ailment) -> int:
        """Best ward level the hero wears against ``ailment`` (0 = none)."""
        return max((i.level for i in self.player.equipment.values()
                    if i is not None and getattr(i, "resist", "") == ailment),
                   default=0)

    def _try_ailment(self, out, effect, bonus, on_hero, enemy=None):
        if not effect or effect not in AILMENTS:
            return
        chance = AILMENTS[effect].chance + bonus
        if on_hero:
            chance *= max(0, 1 - WARD_PER_LEVEL * self._ward(effect) / 100)
        if self.rng.uniform(0, 100) < chance:
            enemy = enemy or self.enemy
            target = self.statuses if on_hero else enemy.statuses
            target[effect] = AILMENTS[effect].turns
            who = "You are" if on_hero else f"The {self.name_of(enemy)} is"
            self._say(out, f"{who} {AFFLICTED[effect]}!")

    def _tick(self, out, statuses, on_hero, enemy=None) -> bool:
        """Apply start-of-turn ailments; returns True if the turn is lost."""
        skip = False
        for name in list(statuses):
            a = AILMENTS[name]
            if a.dot:
                if on_hero:
                    self.player.current_hp = max(0, self.player.current_hp - a.dot)
                    self._say(out, f"You take {a.dot} {name} damage.")
                else:
                    enemy.hp = max(0, enemy.hp - a.dot)
                    self._say(out, f"The {self.name_of(enemy)} takes {a.dot} {name} damage.")
            skip = skip or a.skip
            statuses[name] -= 1
            if statuses[name] <= 0:
                del statuses[name]
        return skip

    def _defense(self, enemy, pierce=0.0) -> int:
        return round(enemy.defense * (1 - pierce))

    def _hit_range(self, stat, power, mult=1.0, pierce=0.0):
        base = self.player.total(stat) + power
        lo, hi = DAMAGE_VARIANCE
        defense = self._defense(self.enemy, pierce)
        return tuple(max(1, round(base * v * mult) - defense)
                     for v in (lo, hi))

    def _hit_enemy(self, out, stat, power, effect, chance_bonus, what,
                   mult=1.0, enemy=None, pierce=0.0, exploit=0.0):
        e = enemy or self.enemy
        if exploit and e.statuses:
            mult *= 1 + exploit
        dmg = max(1, round(self._vary(self.player.total(stat) + power) * mult)
                  - self._defense(e, pierce))
        e.hp = max(0, e.hp - dmg)
        self._say(out, f"{what} hits the {self.name_of(e)} for {dmg}.")
        if e.alive:
            self._try_ailment(out, effect, chance_bonus, on_hero=False, enemy=e)
        else:
            self._fallen(out, e)
        return dmg

    def _fallen(self, out, enemy):
        """Log an enemy going down while others still fight."""
        if self.alive():
            self._say(out, f"The {self.name_of(enemy)} falls!")

    # -- turn structure ------------------------------------------------------
    def _start_hero_turn(self, out) -> bool:
        """Ailments apply.  Returns False if the hero can't act this
        turn (stunned or dead)."""
        skip = self._tick(out, self.statuses, on_hero=True)
        if self.player.current_hp <= 0:
            self._lose(out)
            return False
        if skip:
            self._say(out, "You can't move this turn!")
            self._enemy_turn(out)
            return False
        return True

    def _end_hero_turn(self, out):
        if not self.alive():
            self._win(out)
        elif self.state == ONGOING:
            self._retarget()
            self._enemy_turn(out)

    def _enemy_turn(self, out):
        """Every living enemy acts once, in order."""
        for e in self.enemies:
            if not e.alive or self.player.current_hp <= 0:
                continue
            skip = self._tick(out, e.statuses, on_hero=False, enemy=e)
            if not e.alive:
                self._fallen(out, e)
                continue
            name = self.name_of(e)
            if skip:
                self._say(out, f"The {name} can't move!")
            else:
                defense = (self.player.total(DEFENSE_FOR[e.type.attack_type])
                           + self.guard + self.brace)
                dmg = max(1, round(self._vary(ENEMY_HIT_MULT * e.attack)) - defense)
                self.player.current_hp = max(0, self.player.current_hp - dmg)
                self._say(out, f"The {name} hits you for {dmg}.")
                if self.player.current_hp > 0:
                    self._try_ailment(out, e.type.effect, 0, on_hero=True)
        self.brace = 0
        if not self.alive():
            self._win(out)
            return
        self._retarget()
        # End of the round: cooldowns tick (cooldown N = usable again N
        # hero turns after the cast).
        for k in list(self.cooldowns):
            self.cooldowns[k] -= 1
            if self.cooldowns[k] <= 0:
                del self.cooldowns[k]
        if self.guard_turns:
            self.guard_turns -= 1
            if not self.guard_turns:
                self.guard = 0
                self._say(out, "Your shield fades.")
        if self.player.current_hp <= 0:
            self._lose(out)

    def _win(self, out):
        self.state = WON
        p = self.player
        self.xp_gained = round(sum(e.xp for e in self.enemies)
                               * (1 + p.bonus("xp_bonus") / 100))
        p.xp += self.xp_gained
        who = (f"The {self.enemies[0].name} is defeated!" if len(self.enemies) == 1
               else "All enemies are defeated!")
        self._say(out, f"{who} +{self.xp_gained} XP")
        p.heal(p.max_hp * WIN_HEAL_PCT // 100)
        p.restore_mp(WIN_MP)
        for e in self.enemies:
            self._spoils(out, e)
        self._say(out, f"+{self.gold_gained} gold.")

    def _spoils(self, out, e):
        """Loot, gold, junk and a blueprint chance for one beaten enemy."""
        p = self.player
        chance = 100 if e.boss else LOOT_CHANCE + p.bonus("loot_bonus")
        if self.rng.uniform(0, 100) < chance:
            item = roll_loot(self.rng, max_level=min(4, e.floor + (2 if e.boss else 1)))
            if p.can_carry(item):
                p.inventory.append(item)
                self.loot.append(item)
                self._say(out, f"Found: {item.name} ({item.rarity}).")
            else:
                self._say(out, f"Found {item.name}, but it is too heavy to carry.")
        # Money, and sometimes junk to sell (rolled after the loot, so
        # the loot a seed gives stays the same).
        lo, hi = ENEMY_GOLD
        gold = self.rng.randint(lo, hi) * e.floor * (BOSS_GOLD_MULT if e.boss else 1)
        self.gold_gained += gold
        p.gold += gold
        if self.rng.uniform(0, 100) < ENEMY_JUNK_CHANCE:
            junk = roll_junk(self.rng, e.floor)
            if p.can_carry(junk):
                p.inventory.append(junk)
                self.loot.append(junk)
                self._say(out, f"Found: {junk.name} (junk).")
        if self.blueprint is None and (
                e.boss or self.rng.uniform(0, 100) < BLUEPRINT_ENEMY_CHANCE):
            self.blueprint = roll_blueprint(self.rng, p.blueprints)
            if self.blueprint:
                p.blueprints.append(self.blueprint)
                self._say(out, f"Found a blueprint: {item_by_id(self.blueprint).name}!")

    def _lose(self, out):
        self.state = LOST
        self._say(out, "You collapse...")

    # -- previews ----------------------------------------------------------------
    def _weapon(self):
        """(stat, power, ailment, chance bonus, label) of the hero's weapon."""
        weapon = self.player.equipment.get("weapon")
        stat = STAT_FOR[weapon_type(weapon)]
        if weapon is None:
            return stat, UNARMED_POWER, "", 0, "Your fist"
        return (stat, WEAPON_POWER_BASE + WEAPON_POWER_PER_LEVEL * weapon.level,
                weapon.effect, LEVEL_CHANCE_BONUS * (weapon.level - 1),
                f"Your {weapon.name}")

    def styles(self) -> tuple:
        """Attack keys the hero's weapon offers (first = plain hit)."""
        return styles_for(self.player.equipment.get("weapon"))

    def _style(self, style):
        keys = self.styles()
        return style if style in keys else keys[0]

    def attack_preview(self, style=None):
        """(min, max) damage of an attack in ``style`` on the target right
        now (all its hits together; a sweep deals this to each enemy,
        give or take their defense).  No style = the weapon's plain hit."""
        st = STYLES[self._style(style)]
        stat, power, *_ = self._weapon()
        mult = st.mult * (1 + st.exploit if st.exploit and self.enemy.statuses else 1)
        lo, hi = self._hit_range(stat, power, mult, st.pierce)
        return lo * st.hits, hi * st.hits

    def can_attack(self, style=None) -> bool:
        """The hero can use ``style`` now (enough MP for a spell)."""
        return (self.state == ONGOING
                and self.player.current_mp >= STYLES[self._style(style)].mp)

    def cast_preview(self, ability):
        """(min, max) damage of ``ability``; None if it deals none."""
        if not ability.damage:
            return None
        return self._hit_range(STAT_FOR[ability.attack_type], ability.damage // 2)

    def incoming_preview(self):
        """(min, max) damage the living enemies deal the hero next round,
        all their hits together."""
        lo, hi = DAMAGE_VARIANCE
        total = [0, 0]
        for e in self.alive():
            defense = self.player.total(DEFENSE_FOR[e.type.attack_type]) + self.guard
            for k, v in enumerate((lo, hi)):
                total[k] += max(1, round(ENEMY_HIT_MULT * e.attack * v) - defense)
        return tuple(total)

    def run_chance(self) -> int:
        """% chance that running away works right now: RUN_CHANCE, less
        for every extra living enemy, more with trinket speed.  0 when a
        boss is in the fight."""
        if any(e.boss for e in self.enemies):
            return 0
        lo, hi = RUN_CHANCE_RANGE
        chance = (RUN_CHANCE - RUN_PER_EXTRA_ENEMY * (len(self.alive()) - 1)
                  + self.player.bonus("speed_bonus"))
        return max(lo, min(hi, chance))

    # -- hero actions ----------------------------------------------------------
    def attack(self, style=None) -> list:
        """Attack with one of the weapon's styles (``styles()``); anything
        else, or no style, is the weapon's plain hit."""
        out = []
        style = self._style(style)
        st = STYLES[style]
        if not self.can_attack(style):
            return out
        if not self._start_hero_turn(out):
            return out
        self.player.current_mp -= st.mp
        stat, power, effect, bonus, what = self._weapon()
        if st.effect is not None:
            effect = st.effect
        if style != self.styles()[0]:
            what = f"{what} ({st.name})"
        if st.guard:
            self.brace = st.guard
            self._say(out, f"You brace yourself: +{st.guard} defense this round.")
        if st.miss and self.rng.uniform(0, 100) < st.miss:
            self._say(out, f"{what} misses!")
        else:
            dealt = 0
            for e in (self.alive() if st.sweep else [self.enemy]):
                for _ in range(st.hits):
                    if e.alive:
                        dealt += self._hit_enemy(
                            out, stat, power, effect, bonus + st.chance, what,
                            st.mult, enemy=e, pierce=st.pierce, exploit=st.exploit)
            if st.drain:
                healed = self.player.heal(dealt * st.drain // 100)
                if healed:
                    self._say(out, f"You drain {healed} HP.")
        self._end_hero_turn(out)
        return out

    def can_cast(self, ability) -> bool:
        return (self.state == ONGOING and self.player.can_cast(ability)
                and ability.id not in self.cooldowns
                and not (ability.heal and self.player.current_hp >= self.player.max_hp))

    def cast(self, ability) -> list:
        out = []
        if not self.can_cast(ability):
            return out
        if not self._start_hero_turn(out):
            return out
        self.player.spend_mp(ability)
        if ability.cooldown:
            self.cooldowns[ability.id] = ability.cooldown
        if ability.damage:
            bonus = ABILITY_CHANCE_BONUS + LEVEL_CHANCE_BONUS * (ability.level - 1)
            self._hit_enemy(out, STAT_FOR[ability.attack_type], ability.damage // 2,
                            ability.effect, bonus, ability.name)
        elif ability.heal:
            healed = self.player.heal(ability.heal)
            self._say(out, f"{ability.name} restores {healed} HP.")
        elif ability.guard:
            self.guard, self.guard_turns = ability.guard, ability.duration
            self._say(out, f"{ability.name}: +{ability.guard} defense "
                           f"for {ability.duration} turns.")
        self._end_hero_turn(out)
        return out

    def battle_items(self) -> list:
        """Backpack consumables that do something in battle."""
        return [i for i in self.player.inventory
                if i.kind == "consumable" and (i.heal or i.mana or i.damage)]

    def can_use(self, item) -> bool:
        p = self.player
        if self.state != ONGOING or item not in p.inventory:
            return False
        if item.heal and not item.damage and p.current_hp >= p.max_hp:
            return False
        if item.mana and p.current_mp >= p.max_mp:
            return False
        return bool(item.heal or item.mana or item.damage)

    def use_item(self, item) -> list:
        out = []
        if not self.can_use(item):
            return out
        if not self._start_hero_turn(out):
            return out
        p = self.player
        if item.heal:
            self._say(out, f"{item.name} restores {p.heal(item.heal)} HP.")
        if item.mana:
            self._say(out, f"{item.name} restores {p.restore_mp(item.mana)} MP.")
        if item.damage:
            e = self.enemy
            e.hp = max(0, e.hp - item.damage)
            self._say(out, f"The {item.name} blasts the {self.name_of(e)} "
                           f"for {item.damage}.")
            if e.alive and item.effect in AILMENTS:
                # Bombs land their ailment at a flat BOMB_EFFECT_CHANCE.
                self._try_ailment(out, item.effect,
                                  BOMB_EFFECT_CHANCE - AILMENTS[item.effect].chance,
                                  on_hero=False)
            elif not e.alive:
                self._fallen(out, e)
        item.charges -= 1
        if item.charges <= 0:
            p.inventory.remove(item)
        self._end_hero_turn(out)
        return out

    def run(self) -> list:
        out = []
        if self.state != ONGOING:
            return out
        if any(e.boss for e in self.enemies):
            self._say(out, "You can't run from this fight!")
            return out
        if not self._start_hero_turn(out):
            return out
        if self.rng.uniform(0, 100) < self.run_chance():
            self.state = FLED
            self._say(out, "You got away.")
        else:
            self._say(out, "You couldn't get away!")
            self._enemy_turn(out)
        return out
