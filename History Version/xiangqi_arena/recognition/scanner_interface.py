"""
Recognition system interface — integration contract between the vision
pipeline and the game-logic layer.

Overview
--------
The recognition system (``Fiducial Marker Recognition/``) operates as a
separate process that reads camera frames, detects ArUco markers, and
publishes events.  This module defines the *expected data formats* and the
*entry-point functions* that the game-logic layer will call once the two
systems are connected.

Two interaction points are needed:

1. **Deployment scan** (game start)
   The camera scans the physical board after players have placed their pieces.
   The scanner reports each piece's starting position.

2. **Move scan** (each RECOGNITION phase)
   After a player physically moves one piece, the camera reports the updated
   board state.  The interface validates the change and feeds it into the
   game engine.

--------------------------------------------------------------------
Deployment scan format
--------------------------------------------------------------------
The deployment scanner must produce a ``dict[str, tuple[int, int]]`` mapping
each free-deploy piece name to its ``(col, row)`` grid position::

    scanned_deployment = {
        "red_rook":    (0, 0),
        "red_horse":   (2, 0),
        "red_cannon":  (6, 0),
        "black_rook":  (8, 9),
        "black_horse": (6, 9),
        "black_cannon": (2, 9),
    }

Keys for General and Pawns may be included but are silently ignored — those
positions are fixed by the rulebook.

To build a GameState from this dict call::

    from xiangqi_arena.state.game_state import build_from_scanned_deployment
    from xiangqi_arena.flow.turn import start_turn

    state = build_from_scanned_deployment(scanned_deployment)
    start_turn(state)

--------------------------------------------------------------------
Move scan format
--------------------------------------------------------------------
After each RECOGNITION phase the scanner reports which piece moved and where.
The expected dict format matches the JSONL records already written by
``stable_board_view.append_moves_jsonl``::

    scanned_move = {
        "piece": "red_rook",          # piece name as in PIECE_ARUCO_IDS
        "from":  [col_old, row_old],  # previous grid position
        "to":    [col_new, row_new],  # new grid position
    }

The integration layer must translate ``piece`` → ``piece_id`` (e.g.
``"red_rook"`` → ``"red_rook"`` — names already match) and ``[col, row]`` →
``(col, row)`` tuple, then call::

    from xiangqi_arena.rules.illegal_rules import validate_recognised_move
    from xiangqi_arena.modification.move import apply_move

    piece   = state.pieces[piece_id]
    report  = validate_recognised_move(piece, new_pos, state)
    if report is None:
        apply_move(piece_id, new_pos, state)
    else:
        # prompt player to correct the illegal move and retry the scan
        ...

--------------------------------------------------------------------
Stub signatures (to be implemented during recognition–logic integration)
--------------------------------------------------------------------
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xiangqi_arena.state.game_state import GameState


Pos = tuple[int, int]


def scan_deployment() -> dict[str, Pos]:
    """
    Trigger a one-shot scan of the physical board and return piece positions.

    Returns
    -------
    dict[str, tuple[int, int]]
        Mapping of piece name → (col, row) for all detected pieces.
        See module docstring for the expected key format.

    Raises
    ------
    RuntimeError
        If the camera is unavailable or fewer than the required board-corner
        markers are detected.

    Note
    ----
    Not yet implemented.  Will be connected to ``detect_marker.py`` during
    the recognition–logic integration milestone.
    """
    raise NotImplementedError(
        "scan_deployment() is a stub.  Connect to the ArUco detection "
        "pipeline (Fiducial Marker Recognition/detect_marker.py) during "
        "the recognition–logic integration milestone."
    )


def scan_move() -> dict | None:
    """
    Poll the recognition system for the most recent confirmed piece move.

    Returns
    -------
    dict or None
        A move record with keys ``"piece"``, ``"from"``, ``"to"`` if a stable
        move has been detected since the last call, or ``None`` if the board
        has not changed.

    Note
    ----
    Not yet implemented.  Will read from the JSONL written by
    ``stable_board_view.append_moves_jsonl`` or from a shared queue during
    the recognition–logic integration milestone.
    """
    raise NotImplementedError(
        "scan_move() is a stub.  Connect to the JSONL move log or a shared "
        "queue during the recognition–logic integration milestone."
    )
