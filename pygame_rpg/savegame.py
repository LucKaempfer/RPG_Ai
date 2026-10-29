"""Character save/load (JSON) + name index.

Replaces the V3 txt/pickled file layout (name.txt, name_hidden.txt,
name_inventory.pkl, name_equipment.pkl, saved_chars.txt) with one
JSON file per character plus a small index, all in ``saves/``.

A dungeon run in progress (M5) lives next to it in
``saves/runs/<name>.json``; ``gui/dungeon_screen.py`` decides what goes
in it.  Kept in a subfolder so the index fallback's ``*.json`` scan of
``saves/`` never mistakes it for a character.
"""
import json
import re
from pathlib import Path

from .config import SAVE_DIR
from .items import CATALOG, item_by_id
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


def _default_charges(item_id: str):
    item = CATALOG.get(item_id)
    return item.charges if item is not None else None


def _resolve(ref):
    """Saved item reference -> Item.  A ref is a catalog id, or
    {"id": ..., "charges": n} for a consumable with used charges."""
    if isinstance(ref, dict):
        item = item_by_id(ref["id"])
        if "charges" in ref:
            item.charges = int(ref["charges"])
        return item
    return item_by_id(ref)


def save_player(player: Player) -> Path:
    """Write the character to disk and refresh the index."""
    SAVE_ROOT.mkdir(parents=True, exist_ok=True)
    path = _path_for(player.name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(player.to_dict(_default_charges), f, indent=2)
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
    return Player.from_dict(data, _resolve)


def list_players() -> list:
    """Names of all saved characters, sorted."""
    return sorted(_read_index())


def name_exists(name: str) -> bool:
    return name.strip() in _read_index()


def _run_path(name: str) -> Path:
    return SAVE_ROOT / "runs" / f"{_safe_name(name)}.json"


def save_run(name: str, data: dict) -> Path:
    """Write the character's dungeon run in progress."""
    path = _run_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def load_run(name: str):
    """The saved run as a dict, or None if there is none (or it is
    unreadable: a broken run file just means starting a new run)."""
    path = _run_path(name)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def delete_run(name: str) -> None:
    _run_path(name).unlink(missing_ok=True)


def delete_player(name: str) -> bool:
    path = _path_for(name)
    if not path.exists():
        return False
    path.unlink()
    delete_run(name)
    _write_index([n for n in _read_index() if n != name])
    return True
