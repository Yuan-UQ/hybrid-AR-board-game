from core.enums import EventType, PieceType, Side

BOARD_WIDTH = 9
BOARD_HEIGHT = 10
RIVER_BOUNDARY = 4
RED_PALACE_X = range(3, 6)
RED_PALACE_Y = range(0, 3)
BLACK_PALACE_X = range(3, 6)
BLACK_PALACE_Y = range(7, 10)

PIECE_STATS: dict[PieceType, dict[str, int]] = {
    PieceType.GENERAL: {"hp": 10, "atk": 1},
    PieceType.CHARIOT: {"hp": 5, "atk": 2},
    PieceType.HORSE: {"hp": 4, "atk": 3},
    PieceType.CANNON: {"hp": 5, "atk": 1},
    PieceType.PAWN: {"hp": 3, "atk": 1},
}

SIDE_FORWARD_STEP = {
    Side.RED: 1,
    Side.BLACK: -1,
}

DEFAULT_EVENT_ROTATION = (
    EventType.AMMO,
    EventType.MEDICAL,
    EventType.TRAP,
)

DEFAULT_OPENING_LAYOUT = {
    Side.RED: {
        "general": (4, 0),
        "chariot": (0, 0),
        "horse": (1, 0),
        "cannon": (7, 0),
        "pawns": ((2, 3), (4, 3), (6, 3)),
    },
    Side.BLACK: {
        "general": (4, 9),
        "chariot": (0, 9),
        "horse": (1, 9),
        "cannon": (7, 9),
        "pawns": ((2, 6), (4, 6), (6, 6)),
    },
}
