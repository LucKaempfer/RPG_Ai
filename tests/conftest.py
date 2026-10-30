"""pytest setup (M5): headless pygame, repo root on sys.path, and a
``saves`` fixture that points savegame at a temp folder.

Run from the repo root:  python -m pytest
"""
import os
import pathlib
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# Anything not using the ``saves`` fixture (settings, the audio cache)
# writes here instead of the repo's saves/.
os.environ.setdefault("RPG_DATA_DIR", tempfile.mkdtemp(prefix="rpg_tests_"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest

from pygame_rpg import savegame


@pytest.fixture
def saves(tmp_path, monkeypatch):
    """Save folder for one test; returns its path."""
    monkeypatch.setattr(savegame, "SAVE_ROOT", tmp_path)
    monkeypatch.setattr(savegame, "INDEX_FILE", tmp_path / "index.json")
    return tmp_path
