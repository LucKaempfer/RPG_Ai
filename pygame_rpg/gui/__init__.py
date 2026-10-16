# pygame_rpg/gui/__init__.py
"""GUI screens + shared widgets (Phase 3 of Plan.md).

Screens never reference each other directly.  ``handle_event`` returns a
transition request (a screen name, a ``(name, kwargs)`` pair, or the
``QUIT`` sentinel) and the state machine in ``main.py`` performs the swap.
"""
