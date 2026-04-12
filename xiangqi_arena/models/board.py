from dataclasses import dataclass, field

from core.constants import BOARD_HEIGHT, BOARD_WIDTH
from core.utils import Position, is_in_bounds


@dataclass(slots=True)
class Board:
    width: int = BOARD_WIDTH
    height: int = BOARD_HEIGHT
    occupancy: dict[Position, str] = field(default_factory=dict)

    def is_occupied(self, position: Position) -> bool:
        return position in self.occupancy

    def get_piece_at(self, position: Position) -> str | None:
        return self.occupancy.get(position)

    def place_piece(self, piece_id: str, position: Position) -> None:
        if not is_in_bounds(position):
            raise ValueError(f"Position out of bounds: {position}")
        if position in self.occupancy:
            raise ValueError(f"Position already occupied: {position}")
        self.occupancy[position] = piece_id

    def move_piece(self, old: Position, new: Position) -> None:
        piece_id = self.occupancy.pop(old, None)
        if piece_id is None:
            raise ValueError(f"No piece at {old}")
        if new in self.occupancy:
            raise ValueError(f"Position already occupied: {new}")
        self.occupancy[new] = piece_id

    def clear_position(self, position: Position) -> None:
        self.occupancy.pop(position, None)
