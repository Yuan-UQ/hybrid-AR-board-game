"""
Keyboard handler.

Maps pygame key events to abstract game actions so that main.py
doesn't need to import pygame.constants directly in its logic branches.

Enter confirms/skips in-phase actions; Space triggers turn undo when the
main loop has a stored snapshot (see main.py).
"""

from __future__ import annotations

from enum import Enum, auto

import pygame


class KeyAction(Enum):
    """Abstract actions triggered by keyboard input."""
    CONFIRM = auto()    # Enter → confirm / skip / advance
    UNDO    = auto()    # Space → undo last completed turn (when available)
    CANCEL  = auto()    # Escape → cancel selection (or quit on game-over)
    NONE    = auto()    # any other key


def classify_key(event: pygame.event.Event) -> KeyAction:
    """Return the abstract KeyAction for a KEYDOWN event."""
    if event.type != pygame.KEYDOWN:
        return KeyAction.NONE
    if event.key == pygame.K_SPACE:
        return KeyAction.UNDO
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return KeyAction.CONFIRM
    if event.key == pygame.K_ESCAPE:
        return KeyAction.CANCEL
    return KeyAction.NONE
