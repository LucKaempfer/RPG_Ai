"""What the game runs on: desktop or Android, and where it may write.

Everything platform-specific asks this module instead of checking for
itself, so the rest of the game stays one codebase for both builds:

* :data:`IS_ANDROID`: running inside the APK (python-for-android sets
  ``ANDROID_ARGUMENT`` / ``ANDROID_PRIVATE``).
* :data:`TOUCH`: show the on-screen D-pad and buttons
  (``gui/touch.py``).  On by default on Android; ``RPG_TOUCH=1`` turns
  it on on a desktop to try the controls with the mouse.
* :func:`data_dir`: the folder saves live under.  The working directory
  on a desktop (so ``saves/`` stays where it always was), the app's
  private storage on Android (the APK's own files are not a safe place
  to keep saves across updates).  ``RPG_DATA_DIR`` overrides both.
* :func:`show_keyboard` / :func:`hide_keyboard`: the on-screen keyboard
  for typing a hero name (a no-op on a desktop, where text input is
  always on).
"""

import os
from pathlib import Path

import pygame

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ
TOUCH = IS_ANDROID or os.environ.get("RPG_TOUCH") == "1"


def data_dir() -> Path:
    override = os.environ.get("RPG_DATA_DIR")
    if override:
        return Path(override)
    if IS_ANDROID:
        return Path(os.environ.get("ANDROID_PRIVATE", "."))
    return Path(".")


def show_keyboard(rect=None):
    if not IS_ANDROID:
        return
    if rect is not None:
        pygame.key.set_text_input_rect(rect)
    pygame.key.start_text_input()


def hide_keyboard():
    if IS_ANDROID:
        pygame.key.stop_text_input()
