"""Turn-based battle logic (M4): pure rules, no drawing.

One ``Battle`` is one fight between the hero and one enemy.  Every hero
action (attack / cast / use item / run) is followed by the enemy's turn
unless the fight ended.  Actions return the log lines they produced;
``gui/battle_screen.py`` shows them.

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

Winning adds XP to ``player.xp`` (trinket xp bonus applied).  Levels are
*not* banked here: the Base's level-up screen still lets the player pick
stats, exactly as before.  Loot comes from ``items.roll_loot``.
"""
from dataclasses import dataclass

from .config import (
    WEAPON_POWER_BASE, WEAPON_POWER_PER_LEVEL, UNARMED_POWER, ENEMY_HIT_MULT,
    DAMAGE_VARIANCE, ABILITY_CHANCE_BONUS, LEVEL_CHANCE_BONUS, WARD_PER_LEVEL,
    BOMB_EFFECT_CHANCE, RUN_CHANCE, LOOT_CHANCE, WIN_HEAL_PCT, WIN_MP,
)
from .items import roll_loot

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


class Battle:
    def __init__(self, player, enemy, rng):
        self.player = player
        self.enemy = enemy
        self.rng = rng
        self.state = ONGOING
        self.cooldowns = {}       # ability id -> turns left
        self.statuses = {}        # hero ailments: name -> turns left
        self.guard = 0            # Shield bonus to every defense
        self.guard_turns = 0
        self.xp_gained = 0
        self.loot = []            # items put into the backpack
        self.log = [f"A {enemy.name} appears!" if not enemy.boss
                    else f"The {enemy.name} blocks the way!"]

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

    def _try_ailment(self, out, effect, bonus, on_hero):
        if not effect or effect not in AILMENTS:
            return
        chance = AILMENTS[effect].chance + bonus
        if on_hero:
            chance *= max(0, 1 - WARD_PER_LEVEL * self._ward(effect) / 100)
        if self.rng.uniform(0, 100) < chance:
            target = self.statuses if on_hero else self.enemy.statuses
            target[effect] = AILMENTS[effect].turns
            who = "You are" if on_hero else f"The {self.enemy.name} is"
            self._say(out, f"{who} {AFFLICTED[effect]}!")

    def _tick(self, out, statuses, on_hero) -> bool:
        """Apply start-of-turn ailments; returns True if the turn is lost."""
        skip = False
        for name in list(statuses):
            a = AILMENTS[name]
            if a.dot:
                if on_hero:
                    self.player.current_hp = max(0, self.player.current_hp - a.dot)
                    self._say(out, f"You take {a.dot} {name} damage.")
                else:
                    self.enemy.hp = max(0, self.enemy.hp - a.dot)
                    self._say(out, f"The {self.enemy.name} takes {a.dot} {name} damage.")
            skip = skip or a.skip
            statuses[name] -= 1
            if statuses[name] <= 0:
                del statuses[name]
        return skip

    def _hit_enemy(self, out, stat, power, effect, chance_bonus, what):
        dmg = max(1, round(self._vary(self.player.total(stat) + power))
                  - self.enemy.defense)
        self.enemy.hp = max(0, self.enemy.hp - dmg)
        self._say(out, f"{what} hits the {self.enemy.name} for {dmg}.")
        if self.enemy.alive:
            self._try_ailment(out, effect, chance_bonus, on_hero=False)

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
        if not self.enemy.alive:
            self._win(out)
        elif self.state == ONGOING:
            self._enemy_turn(out)

    def _enemy_turn(self, out):
        e = self.enemy
        skip = self._tick(out, e.statuses, on_hero=False)
        if not e.alive:
            self._win(out)
            return
        if skip:
            self._say(out, f"The {e.name} can't move!")
        else:
            defense = self.player.total(DEFENSE_FOR[e.type.attack_type]) + self.guard
            dmg = max(1, round(self._vary(ENEMY_HIT_MULT * e.attack)) - defense)
            self.player.current_hp = max(0, self.player.current_hp - dmg)
            self._say(out, f"The {e.name} hits you for {dmg}.")
            if self.player.current_hp > 0:
                self._try_ailment(out, e.type.effect, 0, on_hero=True)
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
        p, e = self.player, self.enemy
        self.xp_gained = round(e.xp * (1 + p.bonus("xp_bonus") / 100))
        p.xp += self.xp_gained
        self._say(out, f"The {e.name} is defeated! +{self.xp_gained} XP")
        p.heal(p.max_hp * WIN_HEAL_PCT // 100)
        p.restore_mp(WIN_MP)
        chance = 100 if e.boss else LOOT_CHANCE + p.bonus("loot_bonus")
        if self.rng.uniform(0, 100) < chance:
            item = roll_loot(self.rng, max_level=min(4, e.floor + (2 if e.boss else 1)))
            if p.can_carry(item):
                p.inventory.append(item)
                self.loot.append(item)
                self._say(out, f"Found: {item.name} ({item.rarity}).")
            else:
                self._say(out, f"Found {item.name}, but it is too heavy to carry.")

    def _lose(self, out):
        self.state = LOST
        self._say(out, "You collapse...")

    # -- hero actions ----------------------------------------------------------
    def attack(self) -> list:
        out = []
        if self.state != ONGOING or not self._start_hero_turn(out):
            return out
        weapon = self.player.equipment.get("weapon")
        if weapon is None:
            power, effect, bonus, what = UNARMED_POWER, "", 0, "Your fist"
        else:
            power = WEAPON_POWER_BASE + WEAPON_POWER_PER_LEVEL * weapon.level
            effect = weapon.effect
            bonus = LEVEL_CHANCE_BONUS * (weapon.level - 1)
            what = f"Your {weapon.name}"
        self._hit_enemy(out, STAT_FOR[weapon_type(weapon)], power, effect,
                        bonus, what)
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
            self.enemy.hp = max(0, self.enemy.hp - item.damage)
            self._say(out, f"The {item.name} blasts the {self.enemy.name} "
                           f"for {item.damage}.")
            if self.enemy.alive and item.effect in AILMENTS:
                # Bombs land their ailment at a flat BOMB_EFFECT_CHANCE.
                self._try_ailment(out, item.effect,
                                  BOMB_EFFECT_CHANCE - AILMENTS[item.effect].chance,
                                  on_hero=False)
        item.charges -= 1
        if item.charges <= 0:
            p.inventory.remove(item)
        self._end_hero_turn(out)
        return out

    def run(self) -> list:
        out = []
        if self.state != ONGOING:
            return out
        if self.enemy.boss:
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
