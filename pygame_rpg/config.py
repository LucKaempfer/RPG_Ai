"""Shared constants for the RPG.

Numbers mirror the V3 text game (RPG_V3/main_V3.py) so the pygame port
keeps the same stats, XP curve and weight limits.
"""

# --- Display (shared by all GUI screens) ---
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
FPS = 60

# --- Starting character stats ---
# V3 hero_maker writes: name / 1 / 0 / 100 / 5 / 5 / 5 / 5 / 5 / 5
# (name / lvl / xp / hp / ap / rap / map / dp / rdp / mdp)
START_LEVEL = 1
START_XP = 0
START_HP = 100
START_AP = 5     # attack points
START_RAP = 5    # raw attack points
START_MAP = 5    # magic attack points
START_DP = 5     # defence points
START_RDP = 5    # raw defence points
START_MDP = 5    # magic defence points
START_MP = 20    # magic points: the pool abilities cast from
MP_PER_LEVEL = 5 # max MP grows by this much per level above 1

# --- XP / level-up ---
# V3 xp_check: max_xp = lvl * 100; each level-up the player
# adds +1 to exactly one attribute.
XP_PER_LEVEL = 100
LEVEL_UP_BONUS = 1

def max_xp_for(level: int) -> int:
    """XP needed to reach the next level (V3: lvl * 100)."""
    return level * XP_PER_LEVEL

# --- Weight ---
# V3 references weight/max_weight in backpack() but never defines them,
# so this is a reasonable default for the GUI port.
BASE_MAX_WEIGHT = 50

# --- Saves ---
SAVE_DIR = "saves"
# Bumped whenever the same seed would build a different floor; run saves
# from another version are dropped (the hero just starts a new run).
RUN_VERSION = 3

# --- Rarity (M2 wiring; loot rolls in M4) ---
# Relative spawn weights for a loot roll.  A rarity with no matching
# item falls back to the next more common one.
RARITIES = ("common", "rare", "epic", "legendary")
RARITY_WEIGHTS = {"common": 70, "rare": 22, "epic": 7, "legendary": 1}

# --- Balance (M4 numbers, collected here in M5) ---
# Simulated, not yet play-tested: tune here.  DEVELOPMENT.md §4 explains
# how they combine.
# Hero hits: (attack stat + power) x variance - enemy defense.
WEAPON_POWER_BASE = 4      # weapon power = base + per_level x weapon level
WEAPON_POWER_PER_LEVEL = 2
UNARMED_POWER = 2
# Enemy hits: ENEMY_HIT_MULT x attack x variance - hero defense - guard.
ENEMY_HIT_MULT = 2
DAMAGE_VARIANCE = (0.85, 1.15)
# Ailment chance (%) bonuses on top of combat.AILMENTS; wards cut the
# hero's chance by WARD_PER_LEVEL % per ward level.
ABILITY_CHANCE_BONUS = 20
LEVEL_CHANCE_BONUS = 5
WARD_PER_LEVEL = 25
BOMB_EFFECT_CHANCE = 60
RUN_CHANCE = 60            # % to flee (never from the boss)
LOOT_CHANCE = 50           # % drop for normal enemies (+ trinket loot bonus)
WIN_HEAL_PCT = 10          # after a won fight: % of max HP back
WIN_MP = 5                 # ... and this much MP
# Enemy growth per floor above 1 (HP / XP as fractions, attack / defense flat).
ENEMY_HP_GROWTH = 0.20
ENEMY_ATTACK_GROWTH = 1
ENEMY_DEFENSE_GROWTH = 1
ENEMY_XP_GROWTH = 0.30
ENEMIES_PER_ROOM = (0, 2)  # min, max (never in the entrance room)
CHESTS_PER_FLOOR = 2
# Money and junk (sold at the shop).  Gold amounts are x floor.
ENEMY_GOLD = (3, 8)        # every won fight; the boss pays BOSS_GOLD_MULT x
BOSS_GOLD_MULT = 5
ENEMY_JUNK_CHANCE = 25     # % a beaten enemy also drops a piece of junk
PROP_GOLD = (1, 4)
PROP_GOLD_CHANCE = 30      # % a smashed prop holds some coins
PROP_JUNK_CHANCE = 12      # % it holds a piece of junk
PROPS_PER_ROOM = (1, 3)    # min, max scenery props per room (+1 per 30 cells)

# --- Audio (audio.py synthesises everything; M mutes in game) ---
SFX_VOLUME = 0.7       # 0..1, all one-shot effects
AMBIENT_VOLUME = 0.35  # 0..1, the sewer water loop and its drips
