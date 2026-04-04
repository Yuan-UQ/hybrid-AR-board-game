"""
Shared spatial utilities for Xiangqi Arena.

All functions are pure (no side effects, no state mutation).
They operate only on coordinates and constants, so they can be imported
freely by any layer without creating circular dependencies.
"""

from xiangqi_arena.core.constants import (
    X_MIN, X_MAX, Y_MIN, Y_MAX,
    PALACE_BOUNDS,
    RED_CROSSED_RIVER_Y_MIN,
    BLACK_CROSSED_RIVER_Y_MAX,
)
from collections.abc import Callable

from xiangqi_arena.core.enums import Faction

# Type alias for a board coordinate
Pos = tuple[int, int]


# ---------------------------------------------------------------------------
# Boundary checks
# ---------------------------------------------------------------------------

def is_within_board(x: int, y: int) -> bool:
    """Return True if (x, y) is a legal board node (0..8, 0..9)."""
    return X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX


# ---------------------------------------------------------------------------
# Palace checks
# Rulebook V3 §4.4: General/Marshal can only move within its own palace.
# ---------------------------------------------------------------------------

def is_in_palace(x: int, y: int, faction: Faction) -> bool:
    """Return True if (x, y) is inside *faction*'s palace."""
    bounds = PALACE_BOUNDS[faction]
    x_min, x_max = bounds["x"]
    y_min, y_max = bounds["y"]
    return x_min <= x <= x_max and y_min <= y <= y_max


# ---------------------------------------------------------------------------
# River checks
# Rulebook V3 §4.3
# ---------------------------------------------------------------------------

def has_crossed_river(x: int, y: int, faction: Faction) -> bool:
    """
    Return True if the piece at (x, y) is on the opponent's side of the river.

    Red crosses when y >= 5; Black crosses when y <= 4.
    """
    if faction is Faction.RED:
        return y >= RED_CROSSED_RIVER_Y_MIN
    else:
        return y <= BLACK_CROSSED_RIVER_Y_MAX


def is_on_own_side(x: int, y: int, faction: Faction) -> bool:
    """Return True if (x, y) is on *faction*'s own half of the board."""
    return not has_crossed_river(x, y, faction)


# ---------------------------------------------------------------------------
# Adjacency helpers
# Rulebook V3 §4.5
# ---------------------------------------------------------------------------

def orthogonal_neighbors(x: int, y: int) -> list[Pos]:
    """
    Return the up-to-4 orthogonally adjacent nodes of (x, y) that are within
    the board.  Order: up, down, left, right.
    """
    candidates = [(x, y + 1), (x, y - 1), (x - 1, y), (x + 1, y)]
    return [(cx, cy) for cx, cy in candidates if is_within_board(cx, cy)]


def neighborhood_3x3(x: int, y: int) -> list[Pos]:
    """
    Return the up-to-8 nodes in the 3×3 area centred on (x, y), excluding
    the centre itself, restricted to nodes within the board.

    Used for Pawn nearby-ally bonus (Rulebook V3 §9.5).
    """
    neighbors = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if is_within_board(nx, ny):
                neighbors.append((nx, ny))
    return neighbors


def is_orthogonally_adjacent(pos_a: Pos, pos_b: Pos) -> bool:
    """Return True if pos_a and pos_b are exactly 1 step apart orthogonally."""
    ax, ay = pos_a
    bx, by = pos_b
    return (abs(ax - bx) + abs(ay - by)) == 1


# ---------------------------------------------------------------------------
# Direction helpers (used by Chariot / Cannon path building)
# ---------------------------------------------------------------------------

# The four orthogonal unit vectors: up, down, left, right
ORTHOGONAL_DIRECTIONS: list[Pos] = [(0, 1), (0, -1), (-1, 0), (1, 0)]


def nodes_in_direction(x: int, y: int, dx: int, dy: int) -> list[Pos]:
    """
    Return all board nodes reachable from (x, y) by repeatedly applying
    the unit vector (dx, dy), stopping at the board boundary (exclusive of
    the starting node).
    """
    result: list[Pos] = []
    cx, cy = x + dx, y + dy
    while is_within_board(cx, cy):
        result.append((cx, cy))
        cx += dx
        cy += dy
    return result


# ---------------------------------------------------------------------------
# Horse move helpers
# Rulebook V3 §9.3: standard Chinese chess horse (L-shape with blocking).
# The blocking node is the orthogonal step taken before the diagonal step.
# ---------------------------------------------------------------------------

# Each entry: (blocking_dx, blocking_dy, final_dx, final_dy)
_HORSE_MOVES: list[tuple[int, int, int, int]] = [
    ( 0,  1,  1,  2), ( 0,  1, -1,  2),   # step up, then diagonal
    ( 0, -1,  1, -2), ( 0, -1, -1, -2),   # step down, then diagonal
    ( 1,  0,  2,  1), ( 1,  0,  2, -1),   # step right, then diagonal
    (-1,  0, -2,  1), (-1,  0, -2, -1),   # step left, then diagonal
]


def horse_reachable(x: int, y: int, is_occupied: Callable[[int, int], bool]) -> list[Pos]:
    """
    Return all positions reachable by a Horse at (x, y).

    *is_occupied* should be a callable(x, y) -> bool that returns True when a
    node is occupied by any live piece (blocking the leg).
    """
    result: list[Pos] = []
    for bx, by, fx, fy in _HORSE_MOVES:
        block_x, block_y = x + bx, y + by
        if not is_within_board(block_x, block_y):
            continue
        if is_occupied(block_x, block_y):
            continue               # leg is blocked
        dest_x, dest_y = x + fx, y + fy
        if is_within_board(dest_x, dest_y):
            result.append((dest_x, dest_y))
    return result


# ---------------------------------------------------------------------------
# Round parity helper
# ---------------------------------------------------------------------------

def is_event_point_round(round_number: int) -> bool:
    """Return True when an event point should spawn (odd-numbered rounds)."""
    return round_number % 2 == 1
