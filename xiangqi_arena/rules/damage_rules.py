"""
Combat numerical calculations.

All functions return computed values only. No state mutation happens here.

Damage resolution order (Rulebook V3 §11):
  1. Base damage = attacker.atk  (includes permanent ammo buffs already)
  2. Pawn nearby-ally bonus: if attacker is Pawn and a friendly piece is
     within its 3×3 neighbourhood, add +1 for this attack only (§9.5).
  3. Palace damage reduction: if the TARGET is a General/Marshal inside its
     own palace, subtract 1 (minimum 0) (§11.2).

HP change rules:
  - Healing (medical event point): HP + 1, clamped to max_hp (§6.2, §10.2).
  - Trap (event point): HP − 1, clamped to 0.
  - Any damage result < 0 is treated as 0 (§6.2).
"""

from __future__ import annotations

from xiangqi_arena.core.enums import PieceType
from xiangqi_arena.core.utils import is_in_palace, neighborhood_3x3
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.state.game_state import GameState


def compute_damage(
    attacker: Piece,
    target: Piece,
    state: GameState,
) -> int:
    """
    Return the final damage the *target* will receive from *attacker*.

    The result is already clamped to ≥ 0 and accounts for:
    - Pawn nearby-ally bonus (+1 if applicable).
    - General/Marshal palace damage reduction (−1 if applicable).
    """
    dmg = attacker.atk

    # Pawn nearby-ally bonus (Rulebook V3 §9.5)
    if attacker.piece_type is PieceType.PAWN:
        dmg += _pawn_ally_bonus(attacker, state)

    # Palace damage reduction for the General/Marshal (§11.2)
    if target.piece_type is PieceType.GENERAL:
        dmg -= _palace_reduction(target)

    return max(0, dmg)


def compute_healing() -> int:
    """
    Return the HP gained from a Medical event point (+1, Rulebook V3 §10.2).
    Callers must clamp the result against the piece's max_hp.
    """
    return 1


def compute_trap_damage() -> int:
    """
    Return the HP lost from a Trap event point (1, Rulebook V3 §10.2).
    Callers must clamp to ≥ 0.
    """
    return 1


def clamp_hp(new_hp: int, max_hp: int) -> int:
    """Clamp HP into [0, max_hp]."""
    return max(0, min(new_hp, max_hp))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pawn_ally_bonus(pawn: Piece, state: GameState) -> int:
    """
    Return 1 if there is at least one living friendly piece within the 3×3
    neighbourhood of the *pawn*, 0 otherwise (Rulebook V3 §9.5).
    """
    neighbours = neighborhood_3x3(*pawn.pos)
    for pos in neighbours:
        pid = state.board.get_piece_id_at(*pos)
        if pid is None:
            continue
        neighbour = state.pieces[pid]
        if neighbour.faction is pawn.faction and neighbour.is_alive():
            return 1
    return 0


def _palace_reduction(general: Piece) -> int:
    """
    Return 1 if *general* is inside its own palace (damage is reduced by 1),
    0 otherwise.
    """
    return 1 if is_in_palace(*general.pos, general.faction) else 0
