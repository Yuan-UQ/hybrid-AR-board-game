"""
Illegal operation filtering and interception (MVP).

Rulebook V3 §13: if the system detects an illegal movement result during the
RECOGNITION phase, it prompts the player to adjust the piece position and
retry the scan.

MVP scope: detect whether a recognised board state contains an illegal
movement (compared to the pre-movement state) and report which piece caused
the violation.  More advanced fault tolerance can be added in later iterations.

This module does NOT implement gameplay legality (that is rules/movement_rules
and rules/attack_rules).  Its job is specifically to gate *recognition results*
before they enter the formal gameplay pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from xiangqi_arena.core.enums import Faction
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.rules.movement_rules import get_legal_moves
from xiangqi_arena.state.game_state import GameState

Pos = tuple[int, int]


@dataclass
class IllegalMoveReport:
    """Describes a detected illegal movement."""
    piece: Piece
    from_pos: Pos
    to_pos: Pos
    reason: str


def validate_recognised_move(
    piece: Piece,
    new_pos: Pos,
    state: GameState,
) -> IllegalMoveReport | None:
    """
    Check whether moving *piece* to *new_pos* is a legal move in *state*.

    Returns an IllegalMoveReport if the move is illegal, or None if it is
    valid (or if the piece has not actually moved).

    Used during the RECOGNITION phase to intercept bad physical movements
    before they are committed to GameState.
    """
    if piece.pos == new_pos:
        return None     # piece has not moved — no violation

    legal_moves = get_legal_moves(piece, state)
    if new_pos not in legal_moves:
        return IllegalMoveReport(
            piece=piece,
            from_pos=piece.pos,
            to_pos=new_pos,
            reason=(
                f"{piece.id} cannot move from {piece.pos} to {new_pos}. "
                f"Legal destinations: {legal_moves}"
            ),
        )
    return None


def validate_no_extra_moves(
    scanned_positions: dict[str, Pos],
    state: GameState,
    active_faction: Faction,
) -> list[IllegalMoveReport]:
    """
    Ensure at most ONE piece of the active faction has changed position.
    Rulebook V3 §12.3 Phase 2: at most 1 friendly piece may move per turn.

    Parameters
    ----------
    scanned_positions : dict mapping piece_id -> new (x, y) from the scan.
    state             : current GameState (positions are pre-movement).
    active_faction    : the player whose turn it is.

    Returns a list of reports for every additional moved piece beyond the
    first, or an empty list if the scan is consistent.
    """
    moved: list[tuple[Piece, Pos]] = []
    for pid, new_pos in scanned_positions.items():
        piece = state.pieces.get(pid)
        if piece is None or piece.faction is not active_faction:
            continue
        if piece.is_dead:
            continue
        if piece.pos != new_pos:
            moved.append((piece, new_pos))

    if len(moved) <= 1:
        return []

    # More than one piece moved — every piece beyond the first is a violation
    reports: list[IllegalMoveReport] = []
    for piece, new_pos in moved[1:]:
        reports.append(IllegalMoveReport(
            piece=piece,
            from_pos=piece.pos,
            to_pos=new_pos,
            reason=(
                f"Multiple pieces moved this turn. "
                f"{piece.id} moved from {piece.pos} to {new_pos} "
                f"but only one piece may be operated per turn."
            ),
        ))
    return reports
