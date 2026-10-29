"""Character and run saves (``savegame.py``)."""
import json

from pygame_rpg import items as I, savegame as S
from pygame_rpg.player import Player


def test_player_round_trip(saves):
    p = Player(name="Ada", lvl=3, xp=40)
    sword = I.item_by_id("sword_2")
    potion = I.item_by_id("ration")
    potion.charges = 1
    p.inventory += [sword, potion]
    p.equip(sword)
    p.current_hp = 42
    S.save_player(p)
    q = S.load_player("Ada")
    assert (q.lvl, q.xp, q.current_hp) == (3, 40, 42)
    assert q.equipment["weapon"].id == "sword_2"
    assert [i.charges for i in q.inventory if i.id == "ration"] == [1]
    assert S.list_players() == ["Ada"]


def test_old_save_migrates(saves):
    data = Player(name="Old").to_dict(lambda _id: None)
    data.pop("current_hp")
    data["equipment"] = {"accessory": "weight_belt"}
    (saves / "Old.json").write_text(json.dumps(data))
    q = S.load_player("Old")
    assert q.current_hp == q.max_hp
    assert q.equipment["trinket1"].id == "weight_belt"


def test_run_save_round_trip(saves):
    assert S.load_run("Ada") is None
    S.save_run("Ada", {"floor": 2, "seed": 7})
    assert S.load_run("Ada") == {"floor": 2, "seed": 7}
    S.delete_run("Ada")
    assert S.load_run("Ada") is None


def test_broken_run_is_ignored(saves):
    S.save_run("Ada", {"floor": 2})
    (saves / "runs" / "Ada.json").write_text("not json")
    assert S.load_run("Ada") is None


def test_runs_are_not_heroes(saves):
    S.save_player(Player(name="Ada"))
    S.save_run("Ada", {"floor": 1, "seed": 1})
    (saves / "index.json").unlink()             # force the folder scan
    assert S.list_players() == ["Ada"]
    S.delete_player("Ada")
    assert S.load_run("Ada") is None


def test_old_run_version_is_dropped(saves):
    import pygame
    from pygame_rpg.gui.base_screen import BaseScreen
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    S.save_run("Ada", {"floor": 3, "seed": 1})          # no version: old
    assert BaseScreen(screen, Player(name="Ada")).run is None
    assert S.load_run("Ada") is None
