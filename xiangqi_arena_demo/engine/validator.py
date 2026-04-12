"""
This module dispatches validation logic based on piece type.
"""

from core.constants import KING, ROOK, KNIGHT, CANNON, PAWN

from rules.king_rules import (
    get_king_move_positions,
    get_king_attack_positions,
    is_valid_king_move,
    is_valid_king_attack,
)
from rules.rook_rules import (
    get_rook_move_positions,
    get_rook_attack_positions,
    is_valid_rook_move,
    is_valid_rook_attack,
)
from rules.knight_rules import (
    get_knight_move_positions,
    get_knight_attack_positions,
    is_valid_knight_move,
    is_valid_knight_attack,
)
from rules.cannon_rules import (
    get_cannon_move_positions,
    get_cannon_attack_centers,
    is_valid_cannon_move,
    is_valid_cannon_attack_center,
)
from rules.pawn_rules import (
    get_pawn_move_positions,
    get_pawn_attack_positions,
    is_valid_pawn_move,
    is_valid_pawn_attack,
)


def get_piece_move_positions(board, piece) -> list[tuple[int, int]]:
    if piece is None or not piece.alive:
        return []

    if piece.piece_type == KING:
        return get_king_move_positions(board, piece)
    if piece.piece_type == ROOK:
        return get_rook_move_positions(board, piece)
    if piece.piece_type == KNIGHT:
        return get_knight_move_positions(board, piece)
    if piece.piece_type == CANNON:
        return get_cannon_move_positions(board, piece)
    if piece.piece_type == PAWN:
        return get_pawn_move_positions(board, piece)

    return []


def get_piece_attack_positions(board, piece) -> list[tuple[int, int]]:
    if piece is None or not piece.alive:
        return []

    if piece.piece_type == KING:
        return get_king_attack_positions(board, piece)
    if piece.piece_type == ROOK:
        return get_rook_attack_positions(board, piece)
    if piece.piece_type == KNIGHT:
        return get_knight_attack_positions(board, piece)
    if piece.piece_type == CANNON:
        return get_cannon_attack_centers(board, piece)
    if piece.piece_type == PAWN:
        return get_pawn_attack_positions(board, piece)

    return []


def is_valid_move(board, piece, target_x: int, target_y: int) -> bool:
    if piece is None or not piece.alive:
        return False

    if piece.piece_type == KING:
        return is_valid_king_move(board, piece, target_x, target_y)
    if piece.piece_type == ROOK:
        return is_valid_rook_move(board, piece, target_x, target_y)
    if piece.piece_type == KNIGHT:
        return is_valid_knight_move(board, piece, target_x, target_y)
    if piece.piece_type == CANNON:
        return is_valid_cannon_move(board, piece, target_x, target_y)
    if piece.piece_type == PAWN:
        return is_valid_pawn_move(board, piece, target_x, target_y)

    return False


def is_valid_attack(board, piece, target_x: int, target_y: int) -> bool:
    if piece is None or not piece.alive:
        return False

    if piece.piece_type == KING:
        return is_valid_king_attack(board, piece, target_x, target_y)
    if piece.piece_type == ROOK:
        return is_valid_rook_attack(board, piece, target_x, target_y)
    if piece.piece_type == KNIGHT:
        return is_valid_knight_attack(board, piece, target_x, target_y)
    if piece.piece_type == CANNON:
        return is_valid_cannon_attack_center(board, piece, target_x, target_y)
    if piece.piece_type == PAWN:
        return is_valid_pawn_attack(board, piece, target_x, target_y)

    return False


def can_select_piece(game_state, piece) -> bool:
    return game_state.is_current_players_piece(piece)


def can_move_selected_piece(game_state, target_x: int, target_y: int) -> bool:
    piece = game_state.selected_piece
    if piece is None:
        return False
    return is_valid_move(game_state.board, piece, target_x, target_y)


def can_attack_with_selected_piece(game_state, target_x: int, target_y: int) -> bool:
    piece = game_state.selected_piece
    if piece is None:
        return False
    return is_valid_attack(game_state.board, piece, target_x, target_y)