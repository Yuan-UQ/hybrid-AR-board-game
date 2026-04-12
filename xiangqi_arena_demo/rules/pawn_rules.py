from core.constants import FORWARD_DY
from rules.common_rules import has_crossed_river, get_piece_if_any, is_enemy


def _get_pawn_candidate_offsets(pawn) -> list[tuple[int, int]]:
    """
    Red starts at bottom and moves upward (y - 1).
    Black starts at top and moves downward (y + 1).

    Before crossing river:
    - only forward 1

    After crossing river:
    - forward / left / right 1

    Never backward.
    """
    forward_dy = FORWARD_DY[pawn.camp]

    crossed = has_crossed_river(pawn)

    if crossed:
        return [
            (0, forward_dy),   # forward
            (-1, 0),           # left
            (1, 0),            # right
        ]

    return [
        (0, forward_dy),       # only forward before river
    ]


def get_pawn_move_positions(board, pawn) -> list[tuple[int, int]]:
    if not pawn.alive:
        return []

    x, y = pawn.get_position()
    moves = []

    for dx, dy in _get_pawn_candidate_offsets(pawn):
        nx, ny = x + dx, y + dy

        if not board.is_within_bounds(nx, ny):
            continue

        if board.is_empty(nx, ny):
            moves.append((nx, ny))

    return moves


def get_pawn_attack_positions(board, pawn) -> list[tuple[int, int]]:
    if not pawn.alive:
        return []

    x, y = pawn.get_position()
    attacks = []

    for dx, dy in _get_pawn_candidate_offsets(pawn):
        nx, ny = x + dx, y + dy

        if not board.is_within_bounds(nx, ny):
            continue

        target = get_piece_if_any(board, nx, ny)
        if target is not None and is_enemy(pawn, target):
            attacks.append((nx, ny))

    return attacks


def is_valid_pawn_move(board, pawn, target_x: int, target_y: int) -> bool:
    return (target_x, target_y) in get_pawn_move_positions(board, pawn)


def is_valid_pawn_attack(board, pawn, target_x: int, target_y: int) -> bool:
    return (target_x, target_y) in get_pawn_attack_positions(board, pawn)


def pawn_has_local_support(board, pawn) -> bool:
    """
    Check the 3x3 local area around this pawn.
    If there is any friendly piece in the surrounding 8 cells,
    then pawn gets +1 ATK for current attack.
    """
    if not pawn.alive:
        return False

    x, y = pawn.get_position()

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue

            nx, ny = x + dx, y + dy
            if not board.is_within_bounds(nx, ny):
                continue

            piece = get_piece_if_any(board, nx, ny)
            if piece is None:
                continue

            if piece.camp == pawn.camp and piece.alive:
                return True

    return False