"""
Spatial rule effects applied to GameState.

This module is specifically for special effects whose *application* depends on
spatial context — that is, where the piece IS on the board matters to whether
the effect fires, not just to its numerical value.

Current spatial effects (Rulebook V3):

1. Leader / Marshal palace damage reduction (§9.1, §11.2)
   - Computed inside rules/damage_rules.compute_damage().
   - Applied via piece.apply_damage() in modification/attack.py.
   - No separate state mutation is needed here; the reduction is already
     baked into the final damage number that attack.py applies.

2. Soldier nearby-ally attack bonus (§9.5)
   - Computed inside rules/damage_rules.compute_damage() per-attack.
   - Applied via piece.apply_damage() in modification/attack.py.
   - The bonus is temporary and per-attack, so it never needs to be stored
     on the Piece; no separate mutation is needed.

Why this module exists
----------------------
For the MVP, both spatial effects are handled entirely within the
compute_damage → apply_damage pipeline and require no additional state
mutations.  This module therefore provides:

  - `get_palace_reduction(piece)` — convenience accessor for UI / debug use.
  - `get_soldier_bonus(piece, state)` — convenience accessor for UI / debug use.
  - `describe_spatial_context(piece, state)` — human-readable summary used by
    the UI layer (others.py) to show active spatial modifiers.

If future rules add spatial effects that DO require separate state mutations
(e.g., a persistent zone buff written to the piece), implement them here.
"""

from __future__ import annotations

from xiangqi_arena.core.enums import PieceType
from xiangqi_arena.core.utils import is_in_palace, neighborhood_3x3
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.state.game_state import GameState


def get_palace_reduction(piece: Piece) -> int:
    """
    Return the palace damage reduction for *piece* given its current position.

    Only applies to the Leader / Marshal inside its own palace (+1 reduction).
    Returns 0 for all other pieces or when the Leader is outside its palace.
    """
    if piece.piece_type is not PieceType.LEADER:
        return 0
    return 1 if is_in_palace(*piece.pos, piece.faction) else 0


def get_soldier_bonus(soldier: Piece, state: GameState) -> int:
    """
    Return the temporary attack bonus for *soldier* before it attacks.

    Returns 1 if any live friendly piece is within soldier's 3×3 neighbourhood,
    0 otherwise.  Only meaningful when soldier.piece_type is PieceType.SOLDIER.
    """
    if soldier.piece_type is not PieceType.SOLDIER:
        return 0
    for pos in neighborhood_3x3(*soldier.pos):
        pid = state.board.get_piece_id_at(*pos)
        if pid is None:
            continue
        neighbour = state.pieces[pid]
        if neighbour.faction is soldier.faction and neighbour.is_alive():
            return 1
    return 0


def describe_spatial_context(piece: Piece, state: GameState) -> list[str]:
    """
    Return a list of active spatial modifier descriptions for *piece*.

    Used by ui/others.py to display status hints to the player.
    Examples: ["Palace: -1 incoming damage", "Soldier bonus: +1 ATK this attack"]
    """
    notes: list[str] = []

    if piece.piece_type is PieceType.LEADER and get_palace_reduction(piece):
        notes.append("In palace: −1 incoming damage")

    if piece.piece_type is PieceType.SOLDIER and get_soldier_bonus(piece, state):
        notes.append("Ally nearby: +1 ATK this attack")

    return notes
