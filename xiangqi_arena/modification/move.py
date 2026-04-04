"""
Apply confirmed movement changes to GameState.

This module is the only place that writes piece positions and board occupancy
after a movement is validated.  Callers must ensure legality via
rules/piece_rules.legal_moves() before invoking these functions.

Responsibilities (Guide v2 §4.7 / Rulebook V3 §12.3 Phase 2):
- Update piece.pos to the new coordinates.
- Clear the old board node; claim the new one.
- Mark ActionContext.move_completed = True.
- Append a history entry for replay / debugging.
"""

from __future__ import annotations

from xiangqi_arena.models.piece import Piece
from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]


def apply_move(piece_id: str, to_pos: Pos, state: GameState) -> None:
    """
    Commit the movement of *piece_id* to *to_pos*.

    Preconditions (caller is responsible for checking):
    - The move has been validated as legal by rules/piece_rules.legal_moves().
    - The destination node is empty on the board.
    - The game is currently in the MOVEMENT phase.

    Side effects:
    - piece.pos updated.
    - Board occupancy updated (old node freed, new node claimed).
    - state.action.move_completed = True.
    - History entry appended.
    """
    piece: Piece = state.pieces[piece_id]
    from_pos: Pos = piece.pos

    # Update board occupancy
    state.board.move_piece(from_pos, to_pos)

    # Update piece position
    piece.pos = to_pos

    # Mark the turn-level context
    state.action.selected_piece_id = piece_id
    state.action.move_completed = True

    # History record
    state.history.append({
        "type": "move",
        "round": state.round_number,
        "faction": piece.faction.value,
        "piece_id": piece_id,
        "from": from_pos,
        "to": to_pos,
    })


def apply_skip_move(state: GameState) -> None:
    """
    Record that the active player chose to skip movement this turn.

    Does not modify board or piece state.
    """
    state.action.move_skipped = True

    state.history.append({
        "type": "skip_move",
        "round": state.round_number,
        "faction": state.active_faction.value,
    })
