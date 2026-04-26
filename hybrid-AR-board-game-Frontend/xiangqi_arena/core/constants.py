"""
Global constants for Xiangqi Arena.

All values are derived from Rulebook V3.  Nothing in this module should change
during a game session; adjustable runtime settings belong in config.py instead.
"""

from xiangqi_arena.core.enums import Faction, PieceType

# ---------------------------------------------------------------------------
# Board dimensions
# ---------------------------------------------------------------------------

BOARD_COLS: int = 10  # x axis: 0 .. 9  (left to right)
BOARD_ROWS: int = 9   # y axis: 0 .. 8  (bottom to top)

# Valid coordinate ranges (inclusive)
X_MIN, X_MAX = 0, BOARD_COLS - 1   # 0 .. 9
Y_MIN, Y_MAX = 0, BOARD_ROWS - 1   # 0 .. 8

# ---------------------------------------------------------------------------
# River
# Rulebook V3 §4.3: river lies between x=4 and x=5.
# A HumanSide soldier has crossed when x <= 4; a OrcSide soldier when x >= 5.
# ---------------------------------------------------------------------------

RIVER_X_ORCSIDE_SIDE = 4  # last column on OrcSide's own half
RIVER_X_HUMANSIDE_SIDE   = 5  # first column on HumanSide's own half

# Crossing thresholds (inclusive)
HUMANSIDE_CROSSED_RIVER_X_MAX   = 4  # HumanSide soldier has crossed when pos.x <= this
ORCSIDE_CROSSED_RIVER_X_MIN = 5  # OrcSide soldier has crossed when pos.x >= this

# ---------------------------------------------------------------------------
# Palaces
# Rulebook V3 §4.4: Leader/Marshal is restricted to its own palace.
# OrcSide palace: x in [0,2], y in [3,5]
# HumanSide palace:   x in [7,9], y in [3,5]
# ---------------------------------------------------------------------------

ORCSIDE_PALACE_X = (0, 2)
ORCSIDE_PALACE_Y = (3, 5)

HUMANSIDE_PALACE_X   = (7, 9)
HUMANSIDE_PALACE_Y   = (3, 5)

PALACE_BOUNDS: dict[Faction, dict[str, tuple[int, int]]] = {
    Faction.HumanSide:   {"x": HUMANSIDE_PALACE_X,   "y": HUMANSIDE_PALACE_Y},
    Faction.OrcSide: {"x": ORCSIDE_PALACE_X, "y": ORCSIDE_PALACE_Y},
}

# ---------------------------------------------------------------------------
# Initial deployment (fixed positions)
# Rulebook V3 §7.1 and §7.2
# ---------------------------------------------------------------------------

ORCSIDE_LEADER_START: tuple[int, int] = (0, 4)
HUMANSIDE_LEADER_START:   tuple[int, int] = (9, 4)

ORCSIDE_SOLDIER_STARTS: list[tuple[int, int]] = [(3, 6), (3, 4), (3, 2)]
HUMANSIDE_SOLDIER_STARTS:   list[tuple[int, int]] = [(6, 6), (6, 4), (6, 2)]

# Rulebook V3 §7.3: Archer, Lancer, Wizard are placed freely on the back column
# before play begins (no overlap, no required order).
ORCSIDE_DEPLOY_X: int = 0
HUMANSIDE_DEPLOY_X:   int = 9

# Free-placement pieces (must be placed by players before game starts)
FREE_DEPLOY_PIECE_TYPES: tuple[PieceType, ...] = (
    PieceType.ARCHER,
    PieceType.LANCER,
    PieceType.WIZARD,
)

# ---------------------------------------------------------------------------
# Piece base stats
# Rulebook V3 §6.1: initial HP == max HP for all pieces.
# ---------------------------------------------------------------------------

PIECE_STATS: dict[PieceType, dict[str, int]] = {
    PieceType.LEADER: {"hp":  6, "atk": 1},   # 10→6: faster pacing
    PieceType.ARCHER:    {"hp":  5, "atk": 2},
    PieceType.LANCER:   {"hp":  4, "atk": 3},
    PieceType.WIZARD:  {"hp":  5, "atk": 2},   # 1→2: AOE more meaningful
    PieceType.SOLDIER:    {"hp":  3, "atk": 1},
}

# ---------------------------------------------------------------------------
# Movement limits (max nodes per move/attack, straight-line pieces)
# ---------------------------------------------------------------------------

ARCHER_MAX_RANGE: int = 3  # orthogonal, path-blocked
WIZARD_MOVE_MAX:   int = 2  # orthogonal, cannot land on occupied node
WIZARD_ATTACK_DIST: int = 3 # must be exactly 3 nodes away in one direction

# ---------------------------------------------------------------------------
# Event points
# Rulebook V3 §10.4: one event point spawns on odd-numbered rounds (1, 3, 5…).
# At most one event point exists on the board at any time.
# ---------------------------------------------------------------------------

EVENT_POINT_SPAWN_ON_ODD_ROUNDS: bool = True
MAX_EVENT_POINTS_ON_BOARD: int = 1
