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

Attack styles (``STYLES``) trade damage for ailments: Strike is the plain
hit with the weapon's own ailment; Slash cuts for less but makes the
target bleed more often; Bash hits a bit softer with a good stun chance;
Heavy hits hardest but can miss and causes no ailment.

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
    mult: float          # damage multiplier
    effect: str = None   # ailment it causes; None = the weapon's own
    chance: int = 0      # extra ailment chance (%)
    miss: int = 0        # chance to miss (%)
    note: str = ""       # one-line description for the menu


STYLES = {
    "strike": AttackStyle("Strike", 1.0, note="weapon ailment"),
    "slash": AttackStyle("Slash", 0.75, "bleeding", 30, note="more bleeding"),
    "bash": AttackStyle("Bash", 0.8, "stun", 15, note="may stun"),
    "heavy": AttackStyle("Heavy", 1.35, "", 0, 25, note="25% miss"),
}

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

    def _hit_range(self, stat, power, mult=1.0):
        base = self.player.total(stat) + power
        lo, hi = DAMAGE_VARIANCE
        return tuple(max(1, round(base * v * mult) - self.enemy.defense)
                     for v in (lo, hi))

    def _hit_enemy(self, out, stat, power, effect, chance_bonus, what,
                   mult=1.0):
        e = self.enemy
        dmg = max(1, round(self._vary(self.player.total(stat) + power) * mult)
                  - e.defense)
        e.hp = max(0, e.hp - dmg)
        self._say(out, f"{what} hits the {self.name_of(e)} for {dmg}.")
        if e.alive:
            self._try_ailment(out, effect, chance_bonus, on_hero=False)
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

    def attack_preview(self, style="strike"):
        """(min, max) damage of an attack in ``style`` right now."""
        stat, power, *_ = self._weapon()
        return self._hit_range(stat, power, STYLES[style].mult)

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
    def attack(self, style="strike") -> list:
        out = []
        if self.state != ONGOING or not self._start_hero_turn(out):
            return out
        st = STYLES[style]
        stat, power, effect, bonus, what = self._weapon()
        if st.effect is not None:
            effect = st.effect
        if style != "strike":
            what = f"{what} ({st.name})"
        if st.miss and self.rng.uniform(0, 100) < st.miss:
            self._say(out, f"{what} misses!")
        else:
            self._hit_enemy(out, stat, power, effect, bonus + st.chance, what,
                            st.mult)
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
