from enum import Enum, auto


class Side(Enum):
    RED = auto()
    BLACK = auto()


class PieceType(Enum):
    GENERAL = auto()
    CHARIOT = auto()
    HORSE = auto()
    CANNON = auto()
    PAWN = auto()


class EventType(Enum):
    AMMO = auto()
    MEDICAL = auto()
    TRAP = auto()


class PhaseType(Enum):
    START = auto()
    MOVE = auto()


class VictoryStatus(Enum):
    ONGOING = auto()
    RED_WIN = auto()
    BLACK_WIN = auto()
    DRAW = auto()
