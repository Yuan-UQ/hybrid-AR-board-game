"""
The board manages piece placement, lookup, movement, and removal.
"""

from core.constants import BOARD_COLS, BOARD_ROWS


class Board:
    def __init__(self):
        self._grid = {}

    def is_within_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < BOARD_COLS and 0 <= y < BOARD_ROWS

    def is_empty(self, x: int, y: int) -> bool:
        if not self.is_within_bounds(x, y):
            return False
        return (x, y) not in self._grid

    def has_piece(self, x: int, y: int) -> bool:
        if not self.is_within_bounds(x, y):
            return False
        return (x, y) in self._grid

    def get_piece_at(self, x: int, y: int):
        return self._grid.get((x, y))

    def add_piece(self, piece) -> None:
        """
        Add a piece to the board.
        """
        x, y = piece.get_position()
        if not self.is_within_bounds(x, y):
            raise ValueError(f"Position out of bounds: {(x, y)}")
        if self.has_piece(x, y):
            raise ValueError(f"Position already occupied: {(x, y)}")

        self._grid[(x, y)] = piece

    def move_piece(self, piece, new_x: int, new_y: int) -> None:
        """
        Move a piece to a new empty position.
        """
        old_x, old_y = piece.get_position()

        if not self.is_within_bounds(new_x, new_y):
            raise ValueError(f"Target out of bounds: {(new_x, new_y)}")

        if not self.has_piece(old_x, old_y):
            raise ValueError(f"Piece not found on board at: {(old_x, old_y)}")

        if not self.is_empty(new_x, new_y):
            raise ValueError(f"Target is occupied: {(new_x, new_y)}")

        del self._grid[(old_x, old_y)]
        piece.set_position(new_x, new_y)
        self._grid[(new_x, new_y)] = piece

    def remove_piece(self, piece) -> None:
        """
        Remove a piece from board state.
        """
        pos = piece.get_position()
        if pos in self._grid:
            del self._grid[pos]

    def get_all_pieces(self) -> list:
        return list(self._grid.values())

    def get_pieces_by_camp(self, camp: str) -> list:
        return [piece for piece in self._grid.values() if piece.camp == camp]

    def get_alive_pieces(self) -> list:
        return [piece for piece in self._grid.values() if piece.alive]

    def get_alive_pieces_by_camp(self, camp: str) -> list:
        return [
            piece for piece in self._grid.values()
            if piece.alive and piece.camp == camp
        ]

    def clear_dead_pieces(self) -> None:
        """
        Remove dead pieces or pieces pending removal from the board.
        """
        to_remove = []
        for pos, piece in self._grid.items():
            if (not piece.alive) or piece.pending_removal:
                to_remove.append(pos)

        for pos in to_remove:
            del self._grid[pos]

    def get_positions(self) -> list[tuple[int, int]]:
        return list(self._grid.keys())

    def __repr__(self) -> str:
        return f"Board(num_pieces={len(self._grid)})"