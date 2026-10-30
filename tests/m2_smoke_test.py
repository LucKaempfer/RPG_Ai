"""M2 headless smoke test: bug-fix pass (slots, stats, HP, saves) +
consumables.  Run from the repo root:  python tests/m2_smoke_test.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import os, json, tempfile
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame
from pygame_rpg import items as I, savegame as S
from pygame_rpg.player import Player
checks = 0
def ok(cond, msg):
    global checks
    assert cond, msg
    checks += 1

# Catalog
all_items = I.WEAPONS + I.WEAPON_TIERS + I.ARMOR + I.ARMOR_TIERS + I.CONSUMABLES + I.CONSUMABLE_TIERS + I.TRINKETS + I.TRINKET_TIERS + I.ABILITIES + I.ABILITY_TIERS + I.JUNK
ok(len(all_items) == len(I.CATALOG) == 222, "catalog size / duplicate ids")
ok(len(I.CONSUMABLES) == 6 and len(I.CONSUMABLE_TIERS) == 18, "consumable counts")
OLD_IDS = [i.id for i in I.WEAPONS + I.WEAPON_TIERS + I.ARMOR + I.ARMOR_TIERS] + ["potion"]
for i in OLD_IDS:
    ok(I.item_by_id(i).id == i, f"old id {i}")
ok(I.CATALOG["potion"].heal == 25 and I.CATALOG["potion"].charges == 1, "potion unchanged")
ok(I.CATALOG["potion_4"].heal == 100 and I.CATALOG["ration_3"].heal == 30, "heal growth")
ok(I.CATALOG["fire_bomb_4"].damage == 45 and I.CATALOG["fire_bomb_4"].combat_only, "bomb growth")
ok(I.CATALOG["mana_potion_2"].mana == 40, "mana growth")
ok(all(c.kind == "consumable" and c.charges >= 1 for c in I.CONSUMABLES + I.CONSUMABLE_TIERS), "charges set")

# Equip armor (former crash) + stats + max HP
p = Player(name="T", lvl=3)  # meets the level gate of the tier-2/3 gear below
ok(p.current_hp == p.max_hp == 100, "fresh hp")
cap, vest = I.item_by_id("leather_cap"), I.item_by_id("chainmail_3")
p.inventory += [cap, vest, I.item_by_id("sword_2")]
for it in list(p.inventory): p.equip(it)
ok(p.equipment["head"] is cap and p.equipment["torso"] is vest, "armor equipped")
ok(p.bonus("hp") == 2 + 5 and p.max_hp == 107, "hp bonus")
ok(p.total("dp") == 5 + 1 + 3 + 2 and p.dp == 5, "dp total, base untouched")
ok(p.total("ap") == 7, "weapon ap")
p.unequip("torso"); ok(vest in p.inventory and p.max_hp == 102, "unequip")
# Trinket slots (no trinket items in the catalog yet)
t1 = I.Item(id="t", name="T", kind="trinket", slot="trinket"); t2 = I.Item(id="t2", name="T2", kind="trinket", slot="trinket")
p.inventory += [t1, t2]; p.equip(t1); p.equip(t2)
ok(p.equipment["trinket1"] is t1 and p.equipment["trinket2"] is t2, "two trinkets")
p.drop(t1); p.drop(t2)

# Healing is capped; charges
p.current_hp = 90
ration = I.item_by_id("ration"); p.inventory.append(ration)
ok(p.can_use(ration), "can use ration")
ok(p.use(ration) == 10 and ration.charges == 2 and ration in p.inventory, "ration charge 1")
p.current_hp = p.max_hp
ok(not p.can_use(ration), "full hp blocks use")
p.current_hp = p.max_hp - 1
ok(p.use(ration) == 1 and p.current_hp == p.max_hp, "heal capped")
bomb = I.item_by_id("fire_bomb"); p.inventory.append(bomb)
p.current_hp = 50
ok(not p.can_use(bomb), "bomb battle only")
p.apply_level_up("hp"); ok(p.hp == 101 and p.current_hp == 51, "hp level-up adds current hp")

# Save round-trip + old-save migration
tmp = pathlib.Path(tempfile.mkdtemp()); S.SAVE_ROOT = tmp; S.INDEX_FILE = tmp / "index.json"
S.save_player(p)
raw = json.loads((tmp / "T.json").read_text())
ok({"id": "ration", "charges": 1} in raw["inventory"], "charges saved")
q = S.load_player("T")
ok(q.current_hp == 51 and q.max_hp == p.max_hp, "hp round-trip")
ok([getattr(i, "charges", 0) for i in q.inventory] == [i.charges for i in p.inventory], "charges round-trip")
ok(q.equipment["head"].id == "leather_cap", "equipment round-trip")
old = {"name": "Old", "lvl": 2, "xp": 10, "hp": 100, "ap": 6, "rap": 5, "map": 5, "dp": 5, "rdp": 5, "mdp": 5,
       "lvl_up_counts": {"ap": 1},
       "equipment": {"weapon": "sword", "armor": None, "accessory": None},
       "inventory": ["potion", "dagger"]}
(tmp / "Old.json").write_text(json.dumps(old))
o = S.load_player("Old")
ok(o.equipment["weapon"].id == "sword" and set(o.equipment) == set(__import__("pygame_rpg.player", fromlist=["x"]).EQUIP_SLOTS), "old save slots")
ok(o.current_hp == 100, "old save full hp")
old["equipment"] = {"weapon": "sword", "armor": "leather_cap", "accessory": "dagger"}
(tmp / "Old.json").write_text(json.dumps(old))
o = S.load_player("Old")
ok(sorted(i.id for i in o.inventory) == ["dagger", "dagger", "leather_cap", "potion"], "misplaced items -> backpack")

# GUI smoke: every screen renders; inventory equips armor via the button
pygame.init(); screen = pygame.display.set_mode((800, 600))
from pygame_rpg.main import build_screen
from pygame_rpg.gui.inventory_screen import InventoryScreen
for name in ("title", "tutorial", "hero_maker", "hero_chooser", "base", "inventory", "stats", "level_up"):
    sc = build_screen(name, screen, {"player": q}); sc.draw(screen); sc.handle_update(0.016)
ok(True, "screens render")
inv = InventoryScreen(screen, q)
helm = I.item_by_id("iron_helmet_2"); q.inventory.insert(0, helm)
def click(pos):
    return inv.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
click(inv._row_rects()[0].center)
ok(inv.selected is helm and inv.btn_equip in inv._enabled_actions(), "equip enabled")
click(inv.btn_equip.rect.center)
ok(q.equipment["head"] is helm, "armor equipped via GUI")
inv.draw(screen)
q.current_hp = 10; pot = I.item_by_id("potion"); q.inventory.insert(0, pot)
click(inv._row_rects()[0].center); click(inv.btn_use.rect.center)
ok(q.current_hp == 35 and pot not in q.inventory, "potion via GUI")
inv.draw(screen)

# --- Trinkets (sub-milestone 4) ---
ok(len(I.TRINKETS) == 13 and len(I.TRINKET_TIERS) == 39, "trinket counts")
ok(all(t.description for t in I.TRINKETS + I.TRINKET_TIERS), "trinket descriptions")
tp = Player(name="Tr", lvl=2)
belt = I.item_by_id("iron_belt_2"); tp.inventory.append(belt); tp.equip(belt)
ok(tp.max_weight == 55, "belt raises max weight")

# --- Abilities (sub-milestone 5) ---
from pygame_rpg.player import ABILITY_SLOTS
from pygame_rpg.config import START_MP, MP_PER_LEVEL
ok(len(I.ABILITIES) == 6 and len(I.ABILITY_TIERS) == 18, "ability counts")
ok(all(a.kind == "ability" and a.slot == "ability" and a.weight == 0
       and a.mp_cost > 0 for a in I.ABILITIES + I.ABILITY_TIERS), "ability shape")
fb4 = I.CATALOG["fireball_4"]
ok(fb4.damage == 50 and fb4.mp_cost == 10 and fb4.level == 4, "fireball growth")
ok(I.CATALOG["heal_3"].heal == 55 and I.CATALOG["shield_2"].guard == 5, "heal/shield growth")
ok("fireball" in I.STARTER_INVENTORY, "starter ability")
ap = Player(name="Ab")
ok(ap.current_mp == ap.max_mp == START_MP, "fresh mp")
abl = [I.item_by_id(i) for i in ("fireball", "heal", "shield", "power_strike", "piercing_shot")]
ap.inventory += abl
for a in abl[:4]:
    ap.equip(a)
ok([ap.equipment[s] for s in ABILITY_SLOTS] == abl[:4], "four ability slots")
ok(ap.equipped_abilities() == abl[:4], "battle menu order")
ap.equip(abl[4])
ok(ap.equipment["ability1"] is abl[4] and abl[0] in ap.inventory, "fifth ability swaps slot 1")
high = I.item_by_id("fireball_3"); ap.inventory.append(high)
ok(not ap.can_equip(high), "level gate blocks")
try:
    ap.equip(high); ok(False, "level gate raises")
except ValueError:
    ok(True, "level gate raises")
ok(not ap.can_equip(I.item_by_id("iron_helmet_2")), "level gate on armor too")
ok(ap.can_cast(abl[1]) and not ap.can_cast(abl[0]), "can_cast needs a slot")
ap.spend_mp(abl[1]); ok(ap.current_mp == START_MP - 6, "spend mp")
ap.current_mp = 2
ok(not ap.can_cast(abl[1]), "not enough mp")
ok(ap.restore_mp(100) == START_MP - 2 and ap.current_mp == ap.max_mp, "mp capped")
ap.current_mp = 0
ok(ap.add_xp(100) == 1 and ap.max_mp == START_MP + MP_PER_LEVEL and ap.current_mp == MP_PER_LEVEL, "level-up mp")
ok(ap.can_equip(I.item_by_id("fireball_2")), "level 2 unlocks tier II")
ap.current_mp = 7
S.save_player(ap)
ab2 = S.load_player("Ab")
ok(ab2.current_mp == 7 and ab2.equipment["ability1"].id == "piercing_shot", "mp + ability round-trip")
raw = json.loads((tmp / "Ab.json").read_text()); raw.pop("current_mp")
(tmp / "Ab.json").write_text(json.dumps(raw))
ok(S.load_player("Ab").current_mp == ab2.max_mp, "old save full mp")

# GUI: equip an ability through the inventory, level-gated item stays disabled
inv = InventoryScreen(screen, ab2)
ab2.inventory.insert(0, I.item_by_id("chain_lightning"))
ab2.inventory.insert(1, I.item_by_id("chain_lightning_4"))
click(inv._row_rects()[1].center)
ok(inv.btn_equip not in inv._enabled_actions(), "gated item: equip disabled")
inv.draw(screen)
click(inv._row_rects()[0].center); click(inv.btn_equip.rect.center)
ok(ab2.slot_of(next(a for a in ab2.equipped_abilities() if a.id == "chain_lightning")) in ABILITY_SLOTS, "ability via GUI")
for name in ("base", "inventory", "stats", "level_up"):
    build_screen(name, screen, {"player": ab2}).draw(screen)
ok(True, "screens render with abilities")

# --- Rarity (sub-milestone 6) ---
import random
from collections import Counter
from pygame_rpg.config import RARITIES, RARITY_WEIGHTS
ok(all(i.rarity == I.RARITY_BY_LEVEL[i.level] for i in I.CATALOG.values()), "rarity by tier")
ok(I.item_by_id("sword_3").rarity == "rare" and I.item_by_id("fireball_4").rarity == "epic"
   and I.item_by_id("potion").rarity == "common", "rarity spot-checks")
rng = random.Random(1)
counts = Counter(I.roll_rarity(rng) for _ in range(20000))
total = sum(RARITY_WEIGHTS.values())
ok(all(abs(counts[r] / 20000 - RARITY_WEIGHTS[r] / total) < 0.02 for r in RARITIES), "roll_rarity weights")
rng = random.Random(2)
drops = [I.roll_loot(rng, max_level=2) for _ in range(500)]
ok(all(d.level <= 2 and d.rarity == "common" for d in drops), "loot respects max level (falls back)")
drops = [I.roll_loot(rng, kinds=("weapon",)) for _ in range(500)]
ok(all(d.kind == "weapon" for d in drops) and {d.rarity for d in drops} == {"common", "rare", "epic"}, "loot by kind, all rarities")
d = drops[0]; d.ap += 99
ok(I.CATALOG[d.id].ap != d.ap, "loot is a copy")
inv = InventoryScreen(screen, ab2); inv.selected = ab2.inventory[0]; inv.draw(screen)
ok(True, "inventory renders rarity")
print(f"m2 OK ({checks} checks)")
