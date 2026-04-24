"""
General reusable game rules that are not limited to one specific piece type.
"""

from rules.common_rules import get_piece_if_any, is_enemy, is_teammate


def is_valid_board_position(board, x: int, y: int) -> bool:
    """
    Check whether a coordinate is inside the board.
    """
    return board.is_within_bounds(x, y)


def can_land_on_position(board, piece, x: int, y: int) -> bool:
    """
    For movement:
    - target must be inside board
    - target must be empty
    """
    if piece is None or not piece.alive:
        return False

    if not board.is_within_bounds(x, y):
        return False

    return board.is_empty(x, y)


def can_attack_position(board, attacker, x: int, y: int) -> bool:
    """
    For ordinary attack:
    - target must be inside board
    - target must exist
    - target must be enemy
    """
    if attacker is None or not attacker.alive:
        return False

    if not board.is_within_bounds(x, y):
        return False

    target = get_piece_if_any(board, x, y)
    if target is None:
        return False

    return is_enemy(attacker, target)


def piece_blocks_path(board, x: int, y: int) -> bool:
    """
    Whether there is a piece at a coordinate.
    """
    return board.has_piece(x, y)


def is_alive_piece(piece) -> bool:
    return piece is not None and piece.alive


def is_current_player_piece(game_state, piece) -> bool:
    """
    Whether this piece belongs to current player and is alive.
    """
    return piece is not None and piece.alive and piece.camp == game_state.current_player


def get_enemy_pieces(board, camp: str) -> list:
    """
    Return all alive enemy pieces.
    """
    return [piece for piece in board.get_all_pieces() if piece.camp != camp and piece.alive]


def get_friendly_pieces(board, camp: str) -> list:
    """
    Return all alive friendly pieces.
    """
    return [piece for piece in board.get_all_pieces() if piece.camp == camp and piece.alive]


def is_same_camp(piece_a, piece_b) -> bool:
    if piece_a is None or piece_b is None:
        return False
    return is_teammate(piece_a, piece_b)


def is_enemy_camp(piece_a, piece_b) -> bool:
    if piece_a is None or piece_b is None:
        return False
    return is_enemy(piece_a, piece_b)