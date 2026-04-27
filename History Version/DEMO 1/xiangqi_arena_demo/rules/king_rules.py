from rules.common_rules import (
    is_in_own_palace,
    is_orthogonally_adjacent,
    is_diagonally_adjacent,
    get_piece_if_any,
    is_enemy,
)


def get_king_move_positions(board, king) -> list[tuple[int, int]]:
    """
    Return legal move positions for king.
    Must be:
    - inside board
    - inside own palace
    - target empty
    - 1-step orthogonal or diagonal
    """
    if not king.alive:
        return []

    x, y = king.get_position()
    legal_moves = []

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue

            nx, ny = x + dx, y + dy

            if not board.is_within_bounds(nx, ny):
                continue

            if not is_in_own_palace(king, nx, ny):
                continue

            # King can move orthogonally or diagonally by 1
            if not (
                is_orthogonally_adjacent(x, y, nx, ny)
                or is_diagonally_adjacent(x, y, nx, ny)
            ):
                continue

            if board.is_empty(nx, ny):
                legal_moves.append((nx, ny))

    return legal_moves


def get_king_attack_positions(board, king) -> list[tuple[int, int]]:
    """
    Attack positions are the same pattern as move positions,
    but target must contain an enemy piece.
    """
    if not king.alive:
        return []

    x, y = king.get_position()
    legal_attacks = []

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue

            nx, ny = x + dx, y + dy

            if not board.is_within_bounds(nx, ny):
                continue

            if not is_in_own_palace(king, nx, ny):
                continue

            if not (
                is_orthogonally_adjacent(x, y, nx, ny)
                or is_diagonally_adjacent(x, y, nx, ny)
            ):
                continue

            target = get_piece_if_any(board, nx, ny)
            if target is not None and is_enemy(king, target):
                legal_attacks.append((nx, ny))

    return legal_attacks


def is_valid_king_move(board, king, target_x: int, target_y: int) -> bool:
    return (target_x, target_y) in get_king_move_positions(board, king)


def is_valid_king_attack(board, king, target_x: int, target_y: int) -> bool:
    return (target_x, target_y) in get_king_attack_positions(board, king)