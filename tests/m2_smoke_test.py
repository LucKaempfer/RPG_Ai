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
all_items = I.WEAPONS + I.WEAPON_TIERS + I.ARMOR + I.ARMOR_TIERS + I.CONSUMABLES + I.CONSUMABLE_TIERS + I.TRINKETS + I.TRINKET_TIERS
ok(len(all_items) == len(I.CATALOG) == 188, "catalog size / duplicate ids")
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
p = Player(name="T")
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
print(f"m2 OK ({checks} checks)")
