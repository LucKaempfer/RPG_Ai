"""The story: a prologue after the hero is made, lost writings (books,
notes, scrolls, letters) lying on floors 1-LORE_FLOORS, and an epilogue
once the boss of floor LORE_FLOORS falls.

Pure data + placement, no drawing (the dungeon screen draws the
pickups, ``gui/story_screen.py`` shows the text, ``gui/journal_screen.py``
lists what the hero has found).

The hero keeps the ids of the writings found in ``Player.lore`` (saved),
so each one is found once per hero: a later run leaves found ones out.

Placement has its own RNG seeded from the floor seed, so floors,
enemies, chests and props are unchanged and old runs still load.
"""
import random
from dataclasses import dataclass

# Floors that hold writings; the epilogue follows this floor's boss.
LORE_FLOORS = 5

CHAPTERS = {
    1: "The Upper Drains",
    2: "The Overflow",
    3: "The Old Cisterns",
    4: "The Bone Galleries",
    5: "The Throne Below",
}

# What a writing looks like on the floor (the dungeon screen draws each).
LORE_KINDS = ("book", "note", "scroll", "letter", "tablet")


@dataclass(frozen=True)
class LoreEntry:
    id: str
    floor: int
    kind: str       # one of LORE_KINDS
    title: str
    pages: tuple    # one string per page; "\n" starts a new paragraph


def prologue(name: str) -> list:
    """The story shown once the hero is made (pages of text)."""
    return [
        "Beneath the city of Brackmoor runs the Undercourse: a maze of "
        "brick tunnels, cisterns and drains older than the city itself. "
        "Nobody remembers who built it. Nobody goes down there on purpose.",

        "A month ago the wells turned bitter. Then the rat-catchers "
        "stopped coming back. Then the children of the Low Ward began to "
        "dream the same dream: a small iron crown, glowing in the dark, "
        "asking for a head to sit on.",

        "The council sealed the drains and posted a bounty that nobody "
        f"claimed. Until today. The name on the bounty now reads {name}.",

        "Old Wren, the last rat-catcher of Brackmoor, pressed a lantern "
        "into your hands at the grate. \"They say a king has risen down "
        "there. Not a man. A rat, wearing iron. Kill it, and the crown "
        "just finds another head. Follow it down to where it came from.\"",

        "\"And read what the lost ones left behind,\" she added. \"They saw "
        "more than we did.\"\nYou make camp in the old pump house above "
        "the first grate: your Base. Below, something squeaks in the dark.",
    ]


EPILOGUE_TITLE = "Epilogue: The Broken Crown"

EPILOGUE = (
    "The last Rat King falls, and the crown rolls from its head onto the "
    "throne of black stone. For a moment it glows, searching for a new "
    "head. You bring your weapon down on it, again and again, until the "
    "iron splits like old bread.",

    "A sound runs through the Undercourse, like a held breath let go. "
    "All over the tunnels the rats stop, blink, and scatter into the "
    "walls as plain, frightened animals. Somewhere above, the water in "
    "the wells of Brackmoor runs clear again.",

    "In the Low Ward the children sleep without dreaming. Wren is waiting "
    "at the grate when you climb out, and for once she has nothing to say. "
    "She just takes your hand.",

    "But the tablet on the throne spoke of something that dug the "
    "Undercourse, and of a deep that goes on below the throne. The "
    "stairs behind the broken crown lead further down than any map. "
    "Your story in Brackmoor is told. The sewers are not finished with you.",
)

LORE = (
    # -- Floor 1: The Upper Drains -------------------------------------
    LoreEntry("tally", 1, "note", "A Rat-Catcher's Tally", (
        "Tally of Hobb Tanner, rat-catcher, Low Ward drains.\n"
        "Monday: 41 tails. Tuesday: 66. Wednesday: 108.\n"
        "Thursday: stopped counting.",
        "They don't run from the lantern any more. They walk in lines, "
        "nose to tail, all going the same way. Down. Wren says I'm drinking "
        "again. I'm not. I wish I were.",
    )),
    LoreEntry("ledger", 1, "book", "A Torn Works Ledger", (
        "Brackmoor City Works, year of the founding, page 212.\n"
        "Digging the north drain we broke into a tunnel that was already "
        "there. Brick, but not our brick: small, black, fired harder than "
        "anything our kilns can make.",
        "The founders came down to look and ordered it sealed. We are to "
        "call it the Undercourse and say no more about it. Foreman Aldous "
        "says he heard something breathing behind the wall. I told him it "
        "was the river.",
    )),
    LoreEntry("hobb_last", 1, "note", "Hobb's Last Note", (
        "I saw it. In the big drain under the market, sitting on a heap of "
        "the others like a throne. A grey rat, fat as a dog, with a ring of "
        "iron on its head. A crown.\n"
        "The rest bowed to it. I swear on my mother, they bowed.",
        "It looked at me. Not like an animal looks. Like a man looks at a "
        "purse. I'm going back for my nets. If I don't come up, tell Wren "
        "she was right about the water.",
    )),
    # -- Floor 2: The Overflow -----------------------------------------
    LoreEntry("child_letter", 2, "letter", "A Child's Letter", (
        "Dear Mam, I am writing this because you said to tell you about "
        "the dream if it came again. It came again.\n"
        "There is a little crown in the dark and it is warm. It says it is "
        "lonely. It says it wants a head to sit on and that mine is nice.",
        "I said no. It said the rats said yes. Tilly from the bakery says "
        "she dreams it too. Please don't be cross. Love, Pip.\n"
        "(The letter is wet. It was never sent.)",
    )),
    LoreEntry("sabeth_1", 2, "book", "Sabeth's Journal, Part I", (
        "Sabeth Moll, alchemist. Sample 9 from the Low Ward well: bitter, "
        "a taste of iron and old blood. The same as samples 1 to 8.\n"
        "This is no rot and no dead animal. Something in the deep water "
        "is dissolving, slowly, like a lozenge on a tongue.",
        "The spring floods washed out the old seals under the north drain. "
        "Whatever the founders walled up down there is open to the water "
        "now, and the water comes up into our wells. I am going down to "
        "find it.",
    )),
    LoreEntry("guard_report", 2, "scroll", "A Watch Report", (
        "To the Council, from Sergeant Brenn of the Drain Watch.\n"
        "As ordered, all grates of the Low Ward are chained and the "
        "overflow gates closed. The rat swarms are kept below.",
        "I must report that two of my men and the alchemist Moll were "
        "still below when the gates were closed. The Council's order was "
        "clear and I followed it. I ask that it be written down that I "
        "followed it. I can still hear them knocking.",
    )),
    # -- Floor 3: The Old Cisterns -------------------------------------
    LoreEntry("chronicle", 3, "book", "The Founders' Chronicle", (
        "From the secret chronicle of the house of Aldric, first lord of "
        "Brackmoor.\n"
        "In the deepest cistern the diggers found a throne of black stone, "
        "and on it a small crown of iron, warm to the touch. Lord Aldric "
        "set it on his head, laughing.",
        "From that day the lord was always hungry. He ate at every hour and "
        "was never full, and at night he gnawed at the bed posts. When he "
        "bit his own steward, his sons walled him into the cistern with the "
        "crown, and the city was told he had died of a fever.",
    )),
    LoreEntry("sabeth_2", 3, "book", "Sabeth's Journal, Part II", (
        "I have seen it. The crown does not stay on one head. When its "
        "wearer dies it rolls, it crawls, and the nearest living thing puts "
        "it on. Every rat that wears it becomes a king, and every king it "
        "loses makes it hungrier.",
        "Killing the king only moves the crown. It must be broken where it "
        "was made, on the black throne in the Throne Below, where it is "
        "weakest. I am out of food. I will go deeper while I still can.",
    )),
    LoreEntry("goblin_tablet", 3, "tablet", "A Scratched Goblin Slate", (
        "(Crude pictures scratched into slate, with a few words in the "
        "goblin tongue that the merchants use.)\n"
        "A rat with a crown. Goblins kneeling. A pile of bones and shiny "
        "things given to the goblins.",
        "\"Little king pays. Little king feeds. We guard the wet ways for "
        "little king.\"\n"
        "Below, scratched later and harder: \"Little king hungry. Little "
        "king eats goblins too. Run.\"",
    )),
    # -- Floor 4: The Bone Galleries -----------------------------------
    LoreEntry("aldric_wall", 4, "tablet", "Words Carved in a Wall", (
        "(Letters gouged into the brick by fingernails and teeth.)\n"
        "I AM ALDRIC. I WAS A LORD. I AM NOT THE FIRST TO WEAR IT.",
        "THE CROWN WAS HERE BEFORE THE CITY. BEFORE THE RIVER. THE ONES WHO "
        "BUILT THE UNDERCOURSE DID NOT BUILD IT TO DRAIN WATER. THEY BUILT "
        "IT AS A CAGE. MY SONS HAVE PUT ME IN THE CAGE WITH IT. IT IS "
        "SO HUNGRY.",
    )),
    LoreEntry("hobb_crowned", 4, "note", "Hobb's Scrawl", (
        "they carried me down. hundreds of them, on their backs, like a "
        "river of fur. they didn't bite. they were gentle.\n"
        "they put me in front of the old king and it took the crown off "
        "and held it out to me.",
        "it wants a bigger head. a man's head. it says with a man it could "
        "walk up the stairs into the city. i said no. i keep saying no. i "
        "don't know how many more times i can say no.",
    )),
    LoreEntry("sabeth_3", 4, "book", "Sabeth's Last Page", (
        "My lamp is nearly out. I found Hobb. He would not let me take "
        "him back, and I do not think he could have walked.\n"
        "The crown can only be broken on its throne, by someone it has "
        "never sat on. Someone who has never said yes to it.",
        "If you are reading this, you came down from the city, so you are "
        "braver or more foolish than the Council. Tell Wren I am sorry. "
        "Tell her it was not her fault, whatever she thinks she did.",
    )),
    # -- Floor 5: The Throne Below -------------------------------------
    LoreEntry("wren_letter", 5, "letter", "Wren's Confession", (
        "To whoever went down after me. I gave you the lantern and not the "
        "truth. I'm sorry.\n"
        "Last winter I was poor and the old black bricks of the north drain "
        "sell for good silver to the builders up top. I pulled out a whole "
        "wall of them.",
        "When the spring flood came, it came in through my hole. The water "
        "found the throne, and the crown woke up. Hobb is gone, Sabeth is "
        "gone, and it's my doing. Break the thing. Please. Then come up and "
        "I'll tell the Council myself.",
    )),
    LoreEntry("whisper", 5, "scroll", "A Scroll in No Hand", (
        "(The ink moves when you are not looking at it.)\n"
        "every head is a door. every door opens upward. the rats are small "
        "doors and they open on small rooms. you are a large door.",
        "put me on. you are tired and hurt and alone, and I am warm. you "
        "would never be hungry again. you would never be alone again. you "
        "only have to say yes.\n"
        "(You roll the scroll up and do not say yes.)",
    )),
    LoreEntry("throne_tablet", 5, "tablet", "The Tablet Before the Throne", (
        "(Black stone, the same as the old bricks. The writing is older "
        "than any language spoken in Brackmoor, but the pictures are "
        "clear.)\n"
        "Small people with tools, digging. A crown. A throne. Walls going "
        "up around it, ring after ring.",
        "Then: a single figure standing over the throne with a raised "
        "hammer, and the crown in pieces.\n"
        "Below that, a long stair going further down, into a darkness "
        "the carver did not try to draw.",
    )),
)

BY_ID = {e.id: e for e in LORE}


def entries_for_floor(floor: int) -> list:
    """The writings of ``floor`` in story order (empty past LORE_FLOORS)."""
    return [e for e in LORE if e.floor == floor]


def lore_cells(dungeon, seed, floor, blocked=()) -> list:
    """Where this floor's writings lie: [(entry, cell), ...], at most one
    per room, on interior cells (never the entrance room, a door's
    neighbours or a ``blocked`` cell: enemies, chests, keepers, the
    stairs).  Every entry of the floor gets a spot when there are rooms
    enough, found or not, so spots stay put once some are picked up."""
    entries = entries_for_floor(floor)
    if not entries:
        return []
    rng = random.Random(f"lore-{seed}")
    blocked = set(blocked)
    rooms = rng.sample(dungeon.rooms[1:], len(dungeon.rooms) - 1)
    out = []
    for entry in entries:
        while rooms:
            room = rooms.pop()
            r = room.rect
            near_door = {(x + dx, y + dy) for (x, y) in room.doors
                         for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            cells = [(x, y) for x in range(r.left + 1, r.right - 1)
                     for y in range(r.top + 1, r.bottom - 1)
                     if (x, y) not in blocked and (x, y) not in near_door
                     and (x, y) != r.center]
            if cells:
                out.append((entry, rng.choice(cells)))
                break
    return out

# Every id ``Player.lore`` may hold.
LORE_IDS = frozenset(BY_ID) | {"epilogue"}
