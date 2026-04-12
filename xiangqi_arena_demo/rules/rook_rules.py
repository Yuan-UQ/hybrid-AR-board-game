from core.constants import ROOK_MAX_DISTANCE
from rules.common_rules import get_piece_if_any, is_enemy


def _scan_rook_direction(board, rook, dx: int, dy: int) -> list[tuple[int, int]]:
    """
    Scan one direction for rook movement.
    Stop when meeting first piece or reaching max distance.
    Movement only includes empty cells.
    """
    x, y = rook.get_position()
    result = []

    for step in range(1, ROOK_MAX_DISTANCE + 1):
        nx = x + dx * step
        ny = y + dy * step

        if not board.is_within_bounds(nx, ny):
            break

        if board.is_empty(nx, ny):
            result.append((nx, ny))
        else:
            # blocked by any piece
            break

    return result


def get_rook_move_positions(board, rook) -> list[tuple[int, int]]:
    if not rook.alive:
        return []

    moves = []
    for dx, dy in ((0, 1), (0, -1), (-1, 0), (1, 0)):
        moves.extend(_scan_rook_direction(board, rook, dx, dy))
    return moves


def _scan_rook_attack_direction(board, rook, dx: int, dy: int):
    """
    Find the nearest attackable enemy in one direction within max distance.
    Rules:
    - path blocked by any piece
    - only nearest enemy can be attacked
    - if nearest piece is friendly, no attack in this direction
    """
    x, y = rook.get_position()

    for step in range(1, ROOK_MAX_DISTANCE + 1):
        nx = x + dx * step
        ny = y + dy * step

        if not board.is_within_bounds(nx, ny):
            return None

        target = get_piece_if_any(board, nx, ny)
        if target is None:
            continue

        if is_enemy(rook, target):
            return (nx, ny)

        # friendly piece blocks path
        return None

    return None


def get_rook_attack_positions(board, rook) -> list[tuple[int, int]]:
    if not rook.alive:
        return []

    attacks = []
    for dx, dy in ((0, 1), (0, -1), (-1, 0), (1, 0)):
        target_pos = _scan_rook_attack_direction(board, rook, dx, dy)
        if target_pos is not None:
            attacks.append(target_pos)
    return attacks


def is_valid_rook_move(board, rook, target_x: int, target_y: int) -> bool:
    return (target_x, target_y) in get_rook_move_positions(board, rook)


def is_valid_rook_attack(board, rook, target_x: int, target_y: int) -> bool:
    return (target_x, target_y) in get_rook_attack_positions(board, rook)