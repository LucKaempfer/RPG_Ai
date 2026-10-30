"""The story: prologue, lost writings on floors 1-5, journal, epilogue."""
from types import SimpleNamespace

import pygame
import pytest

from pygame_rpg import lore, savegame as S
from pygame_rpg.combat import WON
from pygame_rpg.dungeon import Dungeon
from pygame_rpg.player import Player


@pytest.fixture(scope="module")
def display():
    from pygame_rpg.gui import screen
    screen._FONTS.clear()
    pygame.init()
    yield pygame.display.set_mode((800, 600))
    pygame.quit()
    screen._FONTS.clear()


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")


def test_three_writings_per_story_floor_and_none_after():
    for floor in range(1, lore.LORE_FLOORS + 1):
        entries = lore.entries_for_floor(floor)
        assert len(entries) == 3 and floor in lore.CHAPTERS
        assert all(e.kind in lore.LORE_KINDS and e.pages for e in entries)
    assert lore.entries_for_floor(lore.LORE_FLOORS + 1) == []
    assert len(lore.BY_ID) == len(lore.LORE)        # ids are unique


@pytest.mark.parametrize("seed", range(20))
def test_writings_lie_on_free_interior_cells(seed):
    d = Dungeon()
    d.generate(seed)
    blocked = {d.rooms[1].rect.center}
    spots = lore.lore_cells(d, seed, 1, blocked)
    assert spots == lore.lore_cells(d, seed, 1, blocked)     # seeded
    rooms = [d.get_room_at(c) for _, c in spots]
    assert len(spots) == min(3, len(d.rooms) - 1)
    assert len(set(map(id, rooms))) == len(rooms)            # one per room
    for room, (_, cell) in zip(rooms, spots):
        r = room.rect
        assert room is not d.rooms[0] and cell not in blocked
        assert r.left < cell[0] < r.right - 1 and r.top < cell[1] < r.bottom - 1
        assert d.is_walkable(cell)
    assert lore.lore_cells(d, seed, 6) == []


def test_every_page_fits_the_parchment(display):
    from pygame_rpg.gui.story_screen import layout, PAGE, LINE_H, MARGIN
    pages = [p for e in lore.LORE for p in e.pages]
    pages += list(lore.EPILOGUE) + lore.prologue("Maximilianus")
    for page in pages:
        lines = layout(page)
        height = sum(LINE_H if ln else 10 for ln in lines)
        assert height <= PAGE.h - 2 * MARGIN + 12, page[:40]


def test_lore_found_is_saved(saves):
    p = Player(name="Reader")
    p.lore = ["tally", "chronicle", "epilogue"]
    S.save_player(p)
    assert S.load_player("Reader").lore == ["tally", "chronicle", "epilogue"]
    data = p.to_dict()
    data["lore"] = ["tally", "not_a_writing"]
    assert Player.from_dict(data, S._resolve).lore == ["tally"]
    del data["lore"]
    assert Player.from_dict(data, lambda r: None).lore == []


def test_story_screen_pages_and_return(display):
    from pygame_rpg.gui.story_screen import StoryScreen
    s = StoryScreen(display, "Prologue", ["one", "two"], next="base")
    s.draw(display)
    assert s.handle_event(key(pygame.K_RETURN)) is None and s.page == 1
    s.handle_event(key(pygame.K_LEFT))
    assert s.page == 0
    s.handle_event(key(pygame.K_RIGHT))
    s.draw(display)
    assert s.handle_event(key(pygame.K_RETURN)) == "base"
    s.page = 0
    assert s.handle_event(key(pygame.K_ESCAPE)) == "base"   # B closes it
    back = SimpleNamespace(ambience="sewer", suspend=lambda: None)
    r = StoryScreen(display, "Note", ["x"], return_to=back)
    assert r.handle_event(key(pygame.K_RETURN)) == ("resume", {"screen": back})


def _floor_with_lore(player, floor=1):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    for seed in range(50):
        ds = DungeonScreen(pygame.display.get_surface(), player, floor=floor, seed=seed)
        if ds.lore:
            return ds
    raise AssertionError("no floor with writings")


def test_walking_onto_a_writing_reads_and_files_it(display, saves):
    p = Player(name="Finder")
    ds = _floor_with_lore(p)
    entry, cell = ds.lore[0]
    ds.enemies.clear()
    ds.x, ds.y = ds._centre(cell)
    name, kw = ds.step(0, 0, 0.016)
    assert name == "story" and kw["return_to"] is ds and kw["title"] == entry.title
    assert entry.id in p.lore and entry.id in S.load_player("Finder").lore
    assert all(e is not entry for e, _ in ds.lore)
    ds.draw(display)
    # A new run on the same floor leaves the found writing out.
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    again = DungeonScreen(display, p, floor=1, seed=ds.seed)
    assert all(e is not entry for e, _ in again.lore)


def test_floor_five_boss_tells_the_epilogue_once(display, saves):
    from pygame_rpg.gui.dungeon_screen import DungeonScreen
    p = Player(name="Victor")
    ds = DungeonScreen(display, p, floor=lore.LORE_FLOORS, seed=4)
    ds.lore.clear()
    boss = next(e for e in ds.enemies if e.boss)
    boss.hp = 0
    battle = SimpleNamespace(state=WON, enemies=[boss], xp_gained=0,
                             gold_gained=0, loot=[], blueprint=None)
    ds.battle_over(battle)
    ds.check_levels = False
    name, kw = ds.step(0, 0, 0.016)
    assert name == "story" and kw["title"] == lore.EPILOGUE_TITLE
    assert "epilogue" in p.lore
    assert ds.step(0, 0, 0.016) is None
    early = DungeonScreen(display, Player(name="Early"), floor=2, seed=4)
    boss = next(e for e in early.enemies if e.boss)
    boss.hp = 0
    early.battle_over(SimpleNamespace(state=WON, enemies=[boss], xp_gained=0,
                                      gold_gained=0, loot=[], blueprint=None))
    assert early.story is None


def test_journal_lists_found_and_hides_the_rest(display, saves):
    from pygame_rpg.gui.journal_screen import JournalScreen
    p = Player(name="Scribe")
    p.lore = ["ledger"]
    j = JournalScreen(display, p)
    j.draw(display)
    assert j.found_count == 1 and len(j.rows) == len(lore.LORE) + 2
    name, kw = j.open(0)                            # the prologue
    assert name == "story" and kw["return_to"] is j
    ledger = 1 + [e.id for e in lore.LORE].index("ledger")
    assert j.open(ledger)[1]["title"] == lore.BY_ID["ledger"].title
    assert j.open(1) is None                        # "tally" not found yet
    assert j.open(len(j.rows) - 1) is None          # no epilogue yet
    assert j.handle_event(key(pygame.K_ESCAPE)) == ("base", {"player": p})


def test_hero_maker_tells_the_prologue_then_the_base(display, saves):
    from pygame_rpg.main import build_screen
    from pygame_rpg.gui.story_screen import StoryScreen
    from pygame_rpg.gui.hero_maker import HeroMakerScreen
    h = HeroMakerScreen(display)
    h.text = "Wren2"
    name, kw = h._create()
    story = build_screen(name, display, kw)
    assert isinstance(story, StoryScreen) and "Wren2" in " ".join(
        " ".join(p) for p in story.pages)
    story.page = len(story.pages) - 1
    nxt, nkw = story.handle_event(key(pygame.K_RETURN))
    assert nxt == "base" and nkw["player"].name == "Wren2"
    assert build_screen("journal", display, {"player": nkw["player"]}).rows
