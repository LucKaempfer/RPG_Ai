"""Character save/load (JSON) + name index.

Replaces the V3 txt/pickled file layout (name.txt, name_hidden.txt,
name_inventory.pkl, name_equipment.pkl, saved_chars.txt) with one
JSON file per character plus a small index, all in ``saves/``.
"""
import json
import re
from pathlib import Path

from .config import SAVE_DIR
from .items import item_by_id
from .player import Player

SAVE_ROOT = Path(SAVE_DIR)
INDEX_FILE = SAVE_ROOT / "index.json"

_NAME_RE = re.compile(r"^[\w .-]{1,20}$")


def _safe_name(name: str) -> str:
    name = name.strip()
    if not name or not _NAME_RE.match(name):
        raise ValueError(f"invalid character name: {name!r}")
    return name


def _path_for(name: str) -> Path:
    return SAVE_ROOT / f"{_safe_name(name)}.json"


def _read_index() -> list:
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                # Prune names whose save file is gone (deleted by hand).
                return [n for n in data
                        if isinstance(n, str)
                        and (SAVE_ROOT / (n + ".json")).exists()]
    # Fall back to scanning the save folder.
    if SAVE_ROOT.exists():
        return sorted(p.stem for p in SAVE_ROOT.glob("*.json")
                      if p.name != "index.json")
    return []


def _write_index(names: list) -> None:
    SAVE_ROOT.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(set(names)), f, indent=2)


def save_player(player: Player) -> Path:
    """Write the character to disk and refresh the index."""
    SAVE_ROOT.mkdir(parents=True, exist_ok=True)
    path = _path_for(player.name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(player.to_dict(), f, indent=2)
    names = [n for n in _read_index() if n != player.name]
    names.append(player.name)
    _write_index(names)
    return path


def load_player(name: str) -> Player:
    """Load a character and resolve inventory/equipment ids to Items."""
    path = _path_for(name)
    if not path.exists():
        raise FileNotFoundError(f"no save for {name!r}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    player = Player.from_dict(data)
    player.inventory = [item_by_id(i) for i in data.get("inventory", [])]
    player.equipment = {
        slot: (item_by_id(i) if i is not None else None)
        for slot, i in data.get("equipment", {}).items()
    }
    return player


def list_players() -> list:
    """Names of all saved characters, sorted."""
    return sorted(_read_index())


def name_exists(name: str) -> bool:
    return name.strip() in _read_index()


def delete_player(name: str) -> bool:
    path = _path_for(name)
    if not path.exists():
        return False
    path.unlink()
    _write_index([n for n in _read_index() if n != name])
    return True
