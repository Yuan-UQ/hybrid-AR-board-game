"""
Current project mainly uses string constants, but this file keeps structure complete.
"""

from enum import Enum


class CampEnum(str, Enum):
    RED = "red"
    BLACK = "black"


class PieceTypeEnum(str, Enum):
    KING = "king"
    ROOK = "rook"
    KNIGHT = "knight"
    CANNON = "cannon"
    PAWN = "pawn"


class EventTypeEnum(str, Enum):
    AMMO = "ammo"
    HEAL = "heal"
    TRAP = "trap"


class PhaseEnum(str, Enum):
    START = "start"
    MOVE = "move"
    UPDATE = "update"
    ATTACK = "attack"
    END = "end"