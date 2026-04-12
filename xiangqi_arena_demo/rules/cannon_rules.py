from core.constants import CANNON_ATTACK_DISTANCE, CANNON_MOVE_MAX_DISTANCE
from rules.common_rules import get_piece_if_any, is_enemy


def _get_orthogonal_directions() -> list[tuple[int, int]]:
    return [(0, 1), (0, -1), (-1, 0), (1, 0)]


def _get_straight_path_cells(x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
    """
    Return cells strictly between start and end on a straight line.
    Used for cannon movement blocking check.
    """
    path = []

    if x1 == x2:
        step = 1 if y2 > y1 else -1
        for y in range(y1 + step, y2, step):
            path.append((x1, y))
    elif y1 == y2:
        step = 1 if x2 > x1 else -1
        for x in range(x1 + step, x2, step):
            path.append((x, y1))

    return path


def get_cannon_move_positions(board, cannon) -> list[tuple[int, int]]:
    """
    Cannon movement:
    - orthogonal only
    - distance <= 2
    - target empty
    - path must be clear
    """
    if not cannon.alive:
        return []

    x, y = cannon.get_position()
    moves = []

    for dx, dy in _get_orthogonal_directions():
        for step in range(1, CANNON_MOVE_MAX_DISTANCE + 1):
            nx = x + dx * step
            ny = y + dy * step

            if not board.is_within_bounds(nx, ny):
                break

            if not board.is_empty(nx, ny):
                break

            path = _get_straight_path_cells(x, y, nx, ny)
            blocked = any(board.has_piece(px, py) for px, py in path)
            if blocked:
                break

            moves.append((nx, ny))

    return moves


def get_cannon_attack_centers(board, cannon) -> list[tuple[int, int]]:
    """
    Return legal center positions for cannon attack.
    A legal center must:
    - be exactly 3 cells away in an orthogonal direction
    - be within board
    - contain an enemy piece
    - ignore path blocking
    """
    if not cannon.alive:
        return []

    x, y = cannon.get_position()
    centers = []

    for dx, dy in _get_orthogonal_directions():
        cx = x + dx * CANNON_ATTACK_DISTANCE
        cy = y + dy * CANNON_ATTACK_DISTANCE

        if not board.is_within_bounds(cx, cy):
            continue

        center_piece = get_piece_if_any(board, cx, cy)
        if center_piece is not None and is_enemy(cannon, center_piece):
            centers.append((cx, cy))

    return centers


def get_cannon_attack_area(board, center_x: int, center_y: int) -> list[tuple[int, int]]:
    """
    Cross-shaped area of 5 cells.
    """
    area = []
    for dx, dy in [(0, 0), (0, 1), (0, -1), (-1, 0), (1, 0)]:
        nx, ny = center_x + dx, center_y + dy
        if board.is_within_bounds(nx, ny):
            area.append((nx, ny))
    return area


def get_cannon_attack_targets(board, cannon, center_x: int, center_y: int) -> list:
    """
    Return enemy pieces actually hit by this cannon attack.
    Friendly pieces are ignored.
    """
    if not cannon.alive:
        return []

    if (center_x, center_y) not in get_cannon_attack_centers(board, cannon):
        return []

    targets = []
    for x, y in get_cannon_attack_area(board, center_x, center_y):
        piece = get_piece_if_any(board, x, y)
        if piece is not None and is_enemy(cannon, piece):
            targets.append(piece)

    return targets


def is_valid_cannon_move(board, cannon, target_x: int, target_y: int) -> bool:
    return (target_x, target_y) in get_cannon_move_positions(board, cannon)


def is_valid_cannon_attack_center(board, cannon, center_x: int, center_y: int) -> bool:
    return (center_x, center_y) in get_cannon_attack_centers(board, cannon)