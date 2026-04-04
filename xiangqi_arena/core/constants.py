"""
Global constants for Xiangqi Arena.

All values are derived from Rulebook V3.  Nothing in this module should change
during a game session; adjustable runtime settings belong in config.py instead.
"""

from xiangqi_arena.core.enums import Faction, PieceType

# ---------------------------------------------------------------------------
# Board dimensions
# ---------------------------------------------------------------------------

BOARD_COLS: int = 9   # x axis: 0 .. 8  (left to right)
BOARD_ROWS: int = 10  # y axis: 0 .. 9  (bottom to top)

# Valid coordinate ranges (inclusive)
X_MIN, X_MAX = 0, BOARD_COLS - 1   # 0 .. 8
Y_MIN, Y_MAX = 0, BOARD_ROWS - 1   # 0 .. 9

# ---------------------------------------------------------------------------
# River
# Rulebook V3 §4.3: river lies between y=4 and y=5.
# A Red pawn has crossed when y >= 5; a Black pawn when y <= 4.
# ---------------------------------------------------------------------------

RIVER_Y_RED_SIDE   = 4  # last row on Red's own half
RIVER_Y_BLACK_SIDE = 5  # first row on Black's own half

# Crossing thresholds (inclusive)
RED_CROSSED_RIVER_Y_MIN   = 5  # Red pawn has crossed when pos.y >= this
BLACK_CROSSED_RIVER_Y_MAX = 4  # Black pawn has crossed when pos.y <= this

# ---------------------------------------------------------------------------
# Palaces
# Rulebook V3 §4.4: General/Marshal is restricted to its own palace.
# Red palace:   x in [3,5], y in [0,2]
# Black palace: x in [3,5], y in [7,9]
# ---------------------------------------------------------------------------

RED_PALACE_X   = (3, 5)
RED_PALACE_Y   = (0, 2)

BLACK_PALACE_X = (3, 5)
BLACK_PALACE_Y = (7, 9)

PALACE_BOUNDS: dict[Faction, dict[str, tuple[int, int]]] = {
    Faction.RED:   {"x": RED_PALACE_X,   "y": RED_PALACE_Y},
    Faction.BLACK: {"x": BLACK_PALACE_X, "y": BLACK_PALACE_Y},
}

# ---------------------------------------------------------------------------
# Initial deployment (fixed positions)
# Rulebook V3 §7.1 and §7.2
# ---------------------------------------------------------------------------

RED_GENERAL_START:   tuple[int, int] = (4, 0)
BLACK_GENERAL_START: tuple[int, int] = (4, 9)

RED_PAWN_STARTS:   list[tuple[int, int]] = [(2, 3), (4, 3), (6, 3)]
BLACK_PAWN_STARTS: list[tuple[int, int]] = [(2, 6), (4, 6), (6, 6)]

# Rulebook V3 §7.3: Rook, Horse, Cannon are placed freely on the back row
# before play begins (no overlap, no required order).
RED_DEPLOY_ROW:   int = 0
BLACK_DEPLOY_ROW: int = 9

# Free-placement pieces (must be placed by players before game starts)
FREE_DEPLOY_PIECE_TYPES: tuple[PieceType, ...] = (
    PieceType.ROOK,
    PieceType.HORSE,
    PieceType.CANNON,
)

# ---------------------------------------------------------------------------
# Piece base stats
# Rulebook V3 §6.1: initial HP == max HP for all pieces.
# ---------------------------------------------------------------------------

PIECE_STATS: dict[PieceType, dict[str, int]] = {
    PieceType.GENERAL: {"hp":  6, "atk": 1},   # 10→6: faster pacing
    PieceType.ROOK:    {"hp":  5, "atk": 2},
    PieceType.HORSE:   {"hp":  4, "atk": 3},
    PieceType.CANNON:  {"hp":  5, "atk": 2},   # 1→2: AOE more meaningful
    PieceType.PAWN:    {"hp":  3, "atk": 1},
}

# ---------------------------------------------------------------------------
# Movement limits (max nodes per move/attack, straight-line pieces)
# ---------------------------------------------------------------------------

ROOK_MAX_RANGE: int = 3  # orthogonal, path-blocked
CANNON_MOVE_MAX:   int = 2  # orthogonal, cannot land on occupied node
CANNON_ATTACK_DIST: int = 3 # must be exactly 3 nodes away in one direction

# ---------------------------------------------------------------------------
# Event points
# Rulebook V3 §10.4: one event point spawns on odd-numbered rounds (1, 3, 5…).
# At most one event point exists on the board at any time.
# ---------------------------------------------------------------------------

EVENT_POINT_SPAWN_ON_ODD_ROUNDS: bool = True
MAX_EVENT_POINTS_ON_BOARD: int = 1
