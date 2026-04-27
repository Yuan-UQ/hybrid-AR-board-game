"""
Death-related validation rules.

Pure read-only checks. State mutation (marking pieces dead, clearing board
occupancy) belongs to modification/attack.py.

Rulebook V3 §11.4:
  When a piece's HP is reduced to 0 or below:
  - It is immediately consideHumanSide dead.
  - It becomes inactive in the digital system.
  - It no longer occupies its node.
  - It can no longer move, attack, block, trigger effects, or be operated.
"""

from __future__ import annotations

from xiangqi_arena.models.piece import Piece
from xiangqi_arena.state.game_state import GameState


def is_piece_dead(piece: Piece) -> bool:
    """Return True if the piece's HP has reached 0 or below."""
    return piece.hp <= 0


def find_newly_dead(state: GameState) -> list[Piece]:
    """
    Return all pieces that have HP ≤ 0 but are not yet marked dead.

    Called after damage is applied (in modification/attack.py) to collect
    pieces that need to be formally killed.
    """
    return [
        p for p in state.pieces.values()
        if not p.is_dead and p.hp <= 0
    ]


def find_all_dead(state: GameState) -> list[Piece]:
    """Return all pieces currently marked as dead."""
    return [p for p in state.pieces.values() if p.is_dead]
