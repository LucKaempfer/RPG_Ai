# Android build of the game (buildozer + python-for-android).
#
# The APK runs the same code as the desktop game: main.py in this folder
# starts pygame_rpg, and pygame_rpg/device.py switches on the touch
# controls and app storage.  GitHub Actions builds it on every push
# (.github/workflows/android.yml); to build by hand on Linux / WSL:
#     pip install buildozer "cython<3.2" && buildozer android debug
# The APK lands in bin/.

[app]
title = Dungeon Crawler
package.name = dungeoncrawler
package.domain = io.github.luckaempfer
version = 0.1

source.dir = .
source.include_exts = py,png,txt,ttf
source.include_patterns = RPG_V3/tutorial.txt
source.exclude_dirs = tests, bin, venv, saves, android, docs, .github, .buildozer, __pycache__
source.exclude_patterns = RPG_V3/*.py, RPG_V3/saved_chars.txt, requirements.txt

# pygame-ce comes from the local recipe in android/p4a-recipes.
requirements = python3,pygame-ce
p4a.local_recipes = ./android/p4a-recipes
p4a.bootstrap = sdl2
p4a.branch = master

orientation = landscape
fullscreen = 1

android.api = 35
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True
# Saves live in the app's private storage: no storage permission needed.
android.permissions =

[buildozer]
log_level = 2
warn_on_root = 0
