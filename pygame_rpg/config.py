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
START_MP = 20    # magic points (ability cost pool, M2-6)

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
