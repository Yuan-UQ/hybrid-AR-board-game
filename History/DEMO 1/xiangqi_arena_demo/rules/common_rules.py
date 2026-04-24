"""
These functions are shared by king / rook / knight / cannon / pawn rules.
"""

from core.constants import (
    RED,
    BLACK,
    RED_CROSSED_RIVER_Y,
    BLACK_CROSSED_RIVER_Y,
    RED_PALACE_X,
    RED_PALACE_Y,
    BLACK_PALACE_X,
    BLACK_PALACE_Y,
    ALL_NEIGHBOR_DIRS,
    ORTHOGONAL_DIRS,
)


def is_same_position(pos1: tuple[int, int], pos2: tuple[int, int]) -> bool:
    return pos1 == pos2


def is_enemy(piece_a, piece_b) -> bool:
    return piece_a.camp != piece_b.camp


def is_teammate(piece_a, piece_b) -> bool:
    return piece_a.camp == piece_b.camp


def is_position_in_bounds(board, x: int, y: int) -> bool:
    return board.is_within_bounds(x, y)


def is_position_empty(board, x: int, y: int) -> bool:
    return board.is_empty(x, y)


def is_position_occupied(board, x: int, y: int) -> bool:
    return board.has_piece(x, y)


def get_piece_if_any(board, x: int, y: int):
    return board.get_piece_at(x, y)


def is_in_own_palace(piece, x: int, y: int) -> bool:
    """
    Check whether a given coordinate is inside the piece's own palace.
    """
    if piece.camp == RED:
        return x in RED_PALACE_X and y in RED_PALACE_Y
    if piece.camp == BLACK:
        return x in BLACK_PALACE_X and y in BLACK_PALACE_Y
    return False


def has_crossed_river(piece) -> bool:
    """
    Red starts from bottom and crosses river when y <= 4.
    Black starts from top and crosses river when y >= 5.
    """
    if piece.camp == RED:
        return piece.y <= RED_CROSSED_RIVER_Y
    if piece.camp == BLACK:
        return piece.y >= BLACK_CROSSED_RIVER_Y
    return False


def manhattan_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    return abs(x1 - x2) + abs(y1 - y2)


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    return max(abs(x1 - x2), abs(y1 - y2))


def is_orthogonally_adjacent(x1: int, y1: int, x2: int, y2: int) -> bool:
    return (abs(x1 - x2) == 1 and y1 == y2) or (abs(y1 - y2) == 1 and x1 == x2)


def is_diagonally_adjacent(x1: int, y1: int, x2: int, y2: int) -> bool:
    return abs(x1 - x2) == 1 and abs(y1 - y2) == 1


def get_orthogonal_neighbors(board, x: int, y: int) -> list[tuple[int, int]]:
    result = []
    for dx, dy in ORTHOGONAL_DIRS:
        nx, ny = x + dx, y + dy
        if board.is_within_bounds(nx, ny):
            result.append((nx, ny))
    return result


def get_all_neighbors(board, x: int, y: int) -> list[tuple[int, int]]:
    result = []
    for dx, dy in ALL_NEIGHBOR_DIRS:
        nx, ny = x + dx, y + dy
        if board.is_within_bounds(nx, ny):
            result.append((nx, ny))
    return result


def get_local_3x3_area(board, x: int, y: int) -> list[tuple[int, int]]:
    """
    Return the 8 surrounding coordinates within the 3x3 local area.
    Center point itself is excluded.
    """
    area = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if board.is_within_bounds(nx, ny):
                area.append((nx, ny))
    return area


def get_straight_line_path(x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
    """
    Return intermediate cells strictly between start and end if they are on
    the same row or same column.
    Excludes both endpoints.
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


def count_pieces_on_path(board, x1: int, y1: int, x2: int, y2: int) -> int:
    path = get_straight_line_path(x1, y1, x2, y2)
    count = 0
    for px, py in path:
        if board.has_piece(px, py):
            count += 1
    return count


def get_pieces_on_path(board, x1: int, y1: int, x2: int, y2: int) -> list:
    path = get_straight_line_path(x1, y1, x2, y2)
    pieces = []
    for px, py in path:
        piece = board.get_piece_at(px, py)
        if piece is not None:
            pieces.append(piece)
    return pieces