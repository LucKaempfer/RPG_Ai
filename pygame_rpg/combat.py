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

Attack styles (``STYLES``) depend on the weapon: every weapon family
(``FAMILY_STYLES``: blades, daggers, spears, blunt weapons, bows,
blowpipes, boomerangs, slingshots, whips, and each element's staves and
wands) offers its own few, the first being the plain hit with the
weapon's own ailment.  The others trade damage for something: a likelier
ailment, ignoring part of the enemy's defense (``pierce``), several
weaker hits (``hits``), hitting every enemy at once (``sweep``), or a
big hit that can miss.

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
    BOMB_EFFECT_CHANCE, RUN_CHANCE, LOOT_CHANCE, WIN_HEAL_PCT, WIN_MP,
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
    sound: str = "strike"


def _s(name, mult, sound, note, **kw):
    return AttackStyle(name, mult, note=note, sound=sound, **kw)


# Every attack in the game, by key.  Each weapon family offers four of
# them (``FAMILY_STYLES``); the first one is the family's plain hit.
STYLES = {
    # bare hands
    "punch": _s("Punch", 1.0, "strike", "plain hit"),
    "kick": _s("Kick", 0.8, "bash", "may stun", effect="stun", chance=15),
    "haymaker": _s("Haymaker", 1.35, "heavy", "25% miss", effect="", miss=25),
    # swords and sabers
    "strike": _s("Strike", 1.0, "strike", "weapon ailment"),
    "slash": _s("Slash", 0.75, "slash", "more bleeding", effect="bleeding", chance=30),
    "thrust": _s("Thrust", 0.9, "strike", "ignores half armor", pierce=0.5),
    "cleave": _s("Cleave", 0.6, "slash", "all foes", sweep=True),
    # daggers
    "stab": _s("Stab", 1.0, "strike", "weapon ailment"),
    "flurry": _s("Flurry", 0.55, "slash", "2 quick stabs", hits=2),
    "gash": _s("Gash", 0.75, "slash", "more bleeding", effect="bleeding", chance=30),
    "vital": _s("Vital Stab", 1.4, "heavy", "25% miss", effect="", miss=25),
    # spears
    "jab": _s("Jab", 1.0, "strike", "weapon ailment"),
    "impale": _s("Impale", 0.9, "heavy", "ignores armor", pierce=1.0),
    "sweep": _s("Sweep", 0.6, "slash", "all foes", sweep=True),
    "skewer": _s("Skewer", 0.75, "slash", "more bleeding", effect="bleeding", chance=30),
    # hammers, maces, clubs
    "smash": _s("Smash", 1.0, "bash", "weapon ailment"),
    "crush": _s("Crush", 0.9, "heavy", "ignores half armor", pierce=0.5),
    "daze": _s("Daze", 0.7, "bash", "likely stun", effect="stun", chance=25),
    "heavy": _s("Heavy Swing", 1.35, "heavy", "25% miss", effect="", miss=25),
    # bows and crossbows
    "shot": _s("Shot", 1.0, "shoot", "weapon ailment"),
    "aimed": _s("Aimed Shot", 0.9, "shoot", "ignores armor", pierce=1.0),
    "volley": _s("Volley", 0.6, "shoot", "all foes", sweep=True),
    "barbed": _s("Barbed Arrow", 0.75, "shoot", "more bleeding",
                 effect="bleeding", chance=30),
    # blowpipes
    "dart": _s("Dart", 1.0, "shoot", "weapon ailment"),
    "poison_dart": _s("Poison Dart", 0.7, "shoot", "poisons", effect="poison", chance=30),
    "darts": _s("Twin Darts", 0.55, "shoot", "2 quick darts", hits=2),
    "aimed_dart": _s("Aimed Dart", 0.9, "shoot", "ignores armor", pierce=1.0),
    # boomerangs
    "throw": _s("Throw", 1.0, "shoot", "weapon ailment"),
    "ricochet": _s("Ricochet", 0.6, "shoot", "all foes", sweep=True),
    "return": _s("Round Trip", 0.55, "shoot", "hits twice", hits=2),
    "knock": _s("Knockout", 0.7, "bash", "likely stun", effect="stun", chance=25),
    # slingshots
    "pebble": _s("Pebble", 1.0, "shoot", "weapon ailment"),
    "headshot": _s("Headshot", 0.7, "bash", "likely stun", effect="stun", chance=25),
    "scatter": _s("Scattershot", 0.6, "shoot", "all foes", sweep=True),
    "rock": _s("Big Rock", 1.35, "heavy", "25% miss", effect="", miss=25),
    # whips
    "lash": _s("Lash", 1.0, "slash", "weapon ailment"),
    "crack": _s("Crack", 0.7, "bash", "likely stun", effect="stun", chance=25),
    "wide_lash": _s("Wide Lash", 0.6, "slash", "all foes", sweep=True),
    "lacerate": _s("Lacerate", 0.75, "slash", "makes them bleed",
                   effect="bleeding", chance=30),
    # poison staves and wands
    "toxic_bolt": _s("Toxic Bolt", 1.0, "magic", "weapon ailment"),
    "venom_cloud": _s("Venom Cloud", 0.55, "magic", "all foes", sweep=True),
    "envenom": _s("Envenom", 0.7, "magic", "strong poison", effect="poison", chance=30),
    # fire staves and wands
    "firebolt": _s("Firebolt", 1.0, "magic", "weapon ailment"),
    "flame_wave": _s("Flame Wave", 0.55, "magic", "all foes", sweep=True),
    "ignite": _s("Ignite", 0.7, "magic", "sets ablaze", effect="burning", chance=30),
    # electric staves and wands
    "spark": _s("Spark", 1.0, "magic", "weapon ailment"),
    "chain_shock": _s("Chain Shock", 0.55, "magic", "all foes", sweep=True),
    "thunderclap": _s("Thunderclap", 0.7, "magic", "likely shock",
                      effect="electrocuted", chance=25),
    # every staff's big spell, every wand's double bolt
    "big_spell": _s("Overcharge", 1.35, "magic", "25% fizzle", miss=25),
    "twin_bolts": _s("Twin Bolts", 0.55, "magic", "2 quick bolts", hits=2),
}

FAMILY_STYLES = {
    "unarmed": ("punch", "kick", "haymaker"),
    "blade": ("strike", "slash", "thrust", "cleave"),
    "dagger": ("stab", "flurry", "gash", "vital"),
    "spear": ("jab", "impale", "sweep", "skewer"),
    "blunt": ("smash", "crush", "daze", "heavy"),
    "bow": ("shot", "aimed", "volley", "barbed"),
    "blowpipe": ("dart", "poison_dart", "darts", "aimed_dart"),
    "boomerang": ("throw", "ricochet", "return", "knock"),
    "slingshot": ("pebble", "headshot", "scatter", "rock"),
    "whip": ("lash", "crack", "wide_lash", "lacerate"),
    "poison_staff": ("toxic_bolt", "venom_cloud", "envenom", "big_spell"),
    "poison_wand": ("toxic_bolt", "venom_cloud", "envenom", "twin_bolts"),
    "fire_staff": ("firebolt", "flame_wave", "ignite", "big_spell"),
    "fire_wand": ("firebolt", "flame_wave", "ignite", "twin_bolts"),
    "electric_staff": ("spark", "chain_shock", "thunderclap", "big_spell"),
    "electric_wand": ("spark", "chain_shock", "thunderclap", "twin_bolts"),
}

# Level-1 weapon id -> family (higher tiers share their base's family).
WEAPON_FAMILY = {
    "saber": "blade", "sword": "blade", "greatsword": "blade",
    "dagger": "dagger", "spear": "spear",
    "warhammer": "blunt", "mace": "blunt", "club": "blunt",
    "bow": "bow", "crossbow": "bow", "blowpipe": "blowpipe",
    "boomerang": "boomerang", "slingshot": "slingshot", "whip": "whip",
    "poisonous_staff": "poison_staff", "poisonous_wand": "poison_wand",
    "fiery_staff": "fire_staff", "fiery_wand": "fire_wand",
    "electric_staff": "electric_staff", "electric_wand": "electric_wand",
}


def styles_for(weapon) -> tuple:
    """The attack keys a weapon (or bare hands, ``None``) offers; the
    first is its plain hit.  Unknown weapons fall back by type."""
    if weapon is None:
        return FAMILY_STYLES["unarmed"]
    head, _, tail = weapon.id.rpartition("_")
    base = head if head and tail.isdigit() else weapon.id
    fam = WEAPON_FAMILY.get(base)
    if fam is None:
        kind = weapon_type(weapon)
        fam = ("bow" if kind == "ranged"
               else {"poison": "poison_staff", "electrocuted": "electric_staff"}
               .get(weapon.effect, "fire_staff") if kind == "magic"
               else "blunt" if weapon.effect == "stun" else "blade")
    return FAMILY_STYLES[fam]


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
                   mult=1.0, enemy=None, pierce=0.0):
        e = enemy or self.enemy
        dmg = max(1, round(self._vary(self.player.total(stat) + power) * mult)
                  - self._defense(e, pierce))
        e.hp = max(0, e.hp - dmg)
        self._say(out, f"{what} hits the {self.name_of(e)} for {dmg}.")
        if e.alive:
            self._try_ailment(out, effect, chance_bonus, on_hero=False, enemy=e)
        else:
            self._fallen(out, e)

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
                defense = self.player.total(DEFENSE_FOR[e.type.attack_type]) + self.guard
                dmg = max(1, round(self._vary(ENEMY_HIT_MULT * e.attack)) - defense)
                self.player.current_hp = max(0, self.player.current_hp - dmg)
                self._say(out, f"The {name} hits you for {dmg}.")
                if self.player.current_hp > 0:
                    self._try_ailment(out, e.type.effect, 0, on_hero=True)
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
        lo, hi = self._hit_range(stat, power, st.mult, st.pierce)
        return lo * st.hits, hi * st.hits

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

    # -- hero actions ----------------------------------------------------------
    def attack(self, style=None) -> list:
        """Attack with one of the weapon's styles (``styles()``); anything
        else, or no style, is the weapon's plain hit."""
        out = []
        if self.state != ONGOING or not self._start_hero_turn(out):
            return out
        style = self._style(style)
        st = STYLES[style]
        stat, power, effect, bonus, what = self._weapon()
        if st.effect is not None:
            effect = st.effect
        if style != self.styles()[0]:
            what = f"{what} ({st.name})"
        if st.miss and self.rng.uniform(0, 100) < st.miss:
            self._say(out, f"{what} misses!")
        else:
            for e in (self.alive() if st.sweep else [self.enemy]):
                for _ in range(st.hits):
                    if e.alive:
                        self._hit_enemy(out, stat, power, effect,
                                        bonus + st.chance, what, st.mult,
                                        enemy=e, pierce=st.pierce)
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
        if self.rng.uniform(0, 100) < RUN_CHANCE:
            self.state = FLED
            self._say(out, "You got away.")
        else:
            self._say(out, "You couldn't get away!")
            self._enemy_turn(out)
        return out
