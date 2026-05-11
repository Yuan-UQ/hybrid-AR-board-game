"""
Recognition system interface — integration contract between the vision
pipeline and the game-logic layer (Frontend / animated UI build).

This repository currently keeps the camera/ArUco pipeline separate. During the
integration milestone, the vision process should provide:

1) Deployment scan (game start)
2) Move scan (each RECOGNITION phase)

--------------------------------------------------------------------
Deployment scan format
--------------------------------------------------------------------
The deployment scanner should produce a ``dict[str, tuple[int, int]]`` mapping
free-deploy piece IDs to their ``(x, y)`` grid positions (10×9 board):

    scanned_deployment = {
        "ArcherHuman": (5, 0),
        "LancerHuman": (9, 2),
        "WizardHuman": (9, 6),
        "ArcherSkeleton": (4, 8),
        "RiderOrc": (0, 6),
        "Slime Orc": (0, 2),
    }

Keys for Leader/Soldiers may be included but are ignored — those positions are
fixed by the rulebook.

To build a GameState from this dict:

    from xiangqi_arena.state.game_state import build_from_scanned_deployment
    from xiangqi_arena.flow.turn import start_turn

    state = build_from_scanned_deployment(scanned_deployment)
    start_turn(state)

--------------------------------------------------------------------
Move scan format
--------------------------------------------------------------------
After each RECOGNITION phase, the scanner reports the updated board state. The
minimal stable format is a single-move record:

    scanned_move = {
        "piece": "Soldier1Human",
        "from":  [x0, y0],
        "to":    [x1, y1],
    }

The integration layer should translate ``piece`` to a piece_id (already matches
GameState ids in this Frontend build) and apply it via ``apply_move`` after
validating legality using ``rules/illegal_rules``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]


def scan_deployment() -> dict[str, Pos]:
    """Stub. Connect to the vision pipeline during integration."""
    raise NotImplementedError("scan_deployment() is not implemented yet.")


def scan_move() -> dict | None:
    """Stub. Connect to the vision pipeline during integration."""
    raise NotImplementedError("scan_move() is not implemented yet.")
