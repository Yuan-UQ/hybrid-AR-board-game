from dataclasses import dataclass, field

from core.constants import PIECE_STATS
from core.enums import PieceType, Side
from core.utils import Position


@dataclass(slots=True)
class Piece:
    piece_id: str
    piece_type: PieceType
    side: Side
    position: Position
    hp: int
    max_hp: int
    atk: int
    is_dead: bool = False
    permanent_buffs: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, piece_id: str, piece_type: PieceType, side: Side, position: Position) -> "Piece":
        stats = PIECE_STATS[piece_type]
        return cls(
            piece_id=piece_id,
            piece_type=piece_type,
            side=side,
            position=position,
            hp=stats["hp"],
            max_hp=stats["hp"],
            atk=stats["atk"],
        )
