"""
Runtime buff helpers.

This module centralizes positional temporary buffs so combat, UI, and FX read
the same rules.
"""

from __future__ import annotations

from xiangqi_arena.core.constants import PIECE_STATS
from xiangqi_arena.core.enums import PieceType
from xiangqi_arena.core.utils import is_in_palace, neighborhood_3x3
from xiangqi_arena.models.piece import Piece
from xiangqi_arena.state.game_state import GameState


def get_base_attack(piece: Piece) -> int:
    return int(PIECE_STATS[piece.piece_type]["atk"])


def get_permanent_attack_bonus(piece: Piece) -> int:
    return max(0, piece.atk - get_base_attack(piece))


def get_attack_bonus(piece: Piece, state: GameState) -> int:
    """
    Soldier nearby-ally bonus (+1):
    only Soldier can receive this bonus, and only when at least one living
    friendly piece is within its 3x3 neighborhood.
    """
    if piece.piece_type is not PieceType.SOLDIER:
        return 0

    for pos in neighborhood_3x3(*piece.pos):
        pid = state.board.get_piece_id_at(*pos)
        if pid is None:
            continue
        neighbor = state.pieces[pid]
        if neighbor.is_alive() and neighbor.faction is piece.faction:
            return 1
    return 0


def get_soldier_attack_effect_bonus(piece: Piece, state: GameState) -> int:
    """
    Visual/animation attack-buff bonus for Soldier:
    includes temporary nearby-ally bonus and permanent ammo bonus.
    """
    if piece.piece_type is not PieceType.SOLDIER:
        return 0
    return get_attack_bonus(piece, state) + get_permanent_attack_bonus(piece)


def get_attack_effect_bonus(piece: Piece, state: GameState) -> int:
    """
    Visual-only attack effect bonus:
    - Soldier: nearby-ally temporary bonus + permanent ammo bonus
    - Non-Soldier: permanent ammo bonus only
    """
    if piece.piece_type is PieceType.SOLDIER:
        return get_soldier_attack_effect_bonus(piece, state)
    return get_permanent_attack_bonus(piece)


def get_defence_bonus(piece: Piece) -> int:
    """
    General palace defence (+1):
    the Leader receives +1 defence while inside own palace.
    """
    if piece.piece_type is PieceType.LEADER and is_in_palace(*piece.pos, piece.faction):
        return 1
    return 0

