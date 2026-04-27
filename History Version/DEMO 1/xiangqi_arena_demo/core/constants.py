"""
This file stores fixed board settings, camps, piece types, initial stats,
special event types, and spatial definitions.
"""

# Board settings
BOARD_COLS = 9
BOARD_ROWS = 10

MIN_X = 0
MAX_X = 8
MIN_Y = 0
MAX_Y = 9

# Camps
RED = "red"
BLACK = "black"
CAMPS = {RED, BLACK}

# Piece types
KING = "king"
ROOK = "rook"
KNIGHT = "knight"
CANNON = "cannon"
PAWN = "pawn"

PIECE_TYPES = {KING, ROOK, KNIGHT, CANNON, PAWN}

# Event types
AMMO = "ammo"
HEAL = "heal"
TRAP = "trap"

EVENT_TYPES = {AMMO, HEAL, TRAP}

# Turn phases
PHASE_START = "start"
PHASE_MOVE = "move"
PHASE_UPDATE = "update"
PHASE_ATTACK = "attack"
PHASE_END = "end"

PHASES = {
    PHASE_START,
    PHASE_MOVE,
    PHASE_UPDATE,
    PHASE_ATTACK,
    PHASE_END,
}

# Piece base stats
PIECE_BASE_STATS = {
    KING: {"initial_hp": 10, "max_hp": 10, "atk": 1},
    ROOK: {"initial_hp": 5, "max_hp": 5, "atk": 2},
    KNIGHT: {"initial_hp": 4, "max_hp": 4, "atk": 3},
    CANNON: {"initial_hp": 5, "max_hp": 5, "atk": 1},
    PAWN: {"initial_hp": 3, "max_hp": 3, "atk": 1},
}

# Palace definition
RED_PALACE_X = {3, 4, 5}
RED_PALACE_Y = {7, 8, 9}

BLACK_PALACE_X = {3, 4, 5}
BLACK_PALACE_Y = {0, 1, 2}

# River / crossing definition
RED_CROSSED_RIVER_Y = 4
BLACK_CROSSED_RIVER_Y = 5

# Forward direction
FORWARD_DY = {
    RED: -1,
    BLACK: 1,
}

# Fixed initial positions (kept for completeness)
INITIAL_KING_POSITIONS = {
    RED: (4, 9),
    BLACK: (4, 0),
}

INITIAL_PAWN_POSITIONS = {
    RED: [(2, 6), (4, 6), (6, 6)],
    BLACK: [(2, 3), (4, 3), (6, 3)],
}

BACK_ROW_Y = {
    RED: 9,
    BLACK: 0,
}

# Piece movement / attack constants
CANNON_ATTACK_DISTANCE = 3
ROOK_MAX_DISTANCE = 3
CANNON_MOVE_MAX_DISTANCE = 2

# Event refresh rule
EVENT_REFRESH_ON_ODD_ROUNDS = True

# Damage / event effects
KING_PALACE_DAMAGE_REDUCTION = 1

AMMO_ATK_BONUS = 1
HEAL_HP_RECOVER = 1
TRAP_HP_DAMAGE = 1

PAWN_SUPPORT_ATK_BONUS = 1

# Directions
ORTHOGONAL_DIRS = [
    (0, 1),
    (0, -1),
    (-1, 0),
    (1, 0),
]

DIAGONAL_DIRS = [
    (-1, -1),
    (-1, 1),
    (1, -1),
    (1, 1),
]

ALL_NEIGHBOR_DIRS = ORTHOGONAL_DIRS + DIAGONAL_DIRS

KNIGHT_OFFSETS = [
    (-2, -1), (-2, 1),
    (-1, -2), (-1, 2),
    (1, -2), (1, 2),
    (2, -1), (2, 1),
]