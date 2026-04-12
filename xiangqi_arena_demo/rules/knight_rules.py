from core.constants import KNIGHT_OFFSETS
from rules.common_rules import get_piece_if_any, is_enemy


def get_knight_move_positions(board, knight) -> list[tuple[int, int]]:
    """
    Legal move positions:
    - within board
    - target empty
    - offset is one of KNIGHT_OFFSETS
    """
    if not knight.alive:
        return []

    x, y = knight.get_position()
    moves = []

    for dx, dy in KNIGHT_OFFSETS:
        nx, ny = x + dx, y + dy

        if not board.is_within_bounds(nx, ny):
            continue

        if board.is_empty(nx, ny):
            moves.append((nx, ny))

    return moves


def get_knight_attack_positions(board, knight) -> list[tuple[int, int]]:
    """
    Attack positions are same pattern as move positions,
    but target must be an enemy piece.
    """
    if not knight.alive:
        return []

    x, y = knight.get_position()
    attacks = []

    for dx, dy in KNIGHT_OFFSETS:
        nx, ny = x + dx, y + dy

        if not board.is_within_bounds(nx, ny):
            continue

        target = get_piece_if_any(board, nx, ny)
        if target is not None and is_enemy(knight, target):
            attacks.append((nx, ny))

    return attacks


def is_valid_knight_move(board, knight, target_x: int, target_y: int) -> bool:
    return (target_x, target_y) in get_knight_move_positions(board, knight)


def is_valid_knight_attack(board, knight, target_x: int, target_y: int) -> bool:
    return (target_x, target_y) in get_knight_attack_positions(board, knight)