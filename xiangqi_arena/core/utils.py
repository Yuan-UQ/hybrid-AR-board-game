from core.constants import (
    BLACK_PALACE_X,
    BLACK_PALACE_Y,
    BOARD_HEIGHT,
    BOARD_WIDTH,
    RED_PALACE_X,
    RED_PALACE_Y,
    RIVER_BOUNDARY,
    SIDE_FORWARD_STEP,
)
from core.enums import Side

Position = tuple[int, int]


def is_in_bounds(position: Position) -> bool:
    x, y = position
    return 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT


def is_in_palace(position: Position, side: Side) -> bool:
    x, y = position
    if side is Side.RED:
        return x in RED_PALACE_X and y in RED_PALACE_Y
    return x in BLACK_PALACE_X and y in BLACK_PALACE_Y


def has_crossed_river(position: Position, side: Side) -> bool:
    _, y = position
    if side is Side.RED:
        return y >= RIVER_BOUNDARY + 1
    return y <= RIVER_BOUNDARY


def forward_step(side: Side) -> int:
    return SIDE_FORWARD_STEP[side]


def orthogonal_neighbors(position: Position) -> list[Position]:
    x, y = position
    candidates = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
    return [candidate for candidate in candidates if is_in_bounds(candidate)]


def diagonal_neighbors(position: Position) -> list[Position]:
    x, y = position
    candidates = ((x + 1, y + 1), (x + 1, y - 1), (x - 1, y + 1), (x - 1, y - 1))
    return [candidate for candidate in candidates if is_in_bounds(candidate)]


def local_neighbors(position: Position) -> list[Position]:
    x, y = position
    result: list[Position] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            candidate = (x + dx, y + dy)
            if is_in_bounds(candidate):
                result.append(candidate)
    return result


def orthogonal_line(position: Position, direction: Position, steps: int) -> list[Position]:
    x, y = position
    dx, dy = direction
    result: list[Position] = []
    for step in range(1, steps + 1):
        candidate = (x + dx * step, y + dy * step)
        if not is_in_bounds(candidate):
            break
        result.append(candidate)
    return result


def add_position(position: Position, delta: Position) -> Position:
    return position[0] + delta[0], position[1] + delta[1]
