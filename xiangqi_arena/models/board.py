"""
Board domain model.

Rulebook V3 §4.1: the board uses intersection nodes, not square cells.
Size: 9 columns (x = 0..8) × 10 rows (y = 0..9).

Occupancy contract (Rulebook V3 §11.4):
- Only LIVE pieces occupy nodes.  When a piece dies it must be removed from
  the occupancy map immediately via `remove_piece()`.
- A dead piece that physically remains on the table is a visual artefact only;
  the rules system treats its former node as empty.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xiangqi_arena.core.constants import BOARD_COLS, BOARD_ROWS
from xiangqi_arena.core.utils import is_within_board

Pos = tuple[int, int]


@dataclass
class Board:
    """Tracks which node is occupied by which live piece."""

    cols: int = BOARD_COLS
    rows: int = BOARD_ROWS

    # Maps (x, y) -> piece_id for every live piece currently on the board.
    # Dead pieces must NOT appear here.
    _occupancy: dict[Pos, str] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Occupancy queries
    # ------------------------------------------------------------------

    def is_occupied(self, x: int, y: int) -> bool:
        """Return True if (x, y) is occupied by a live piece."""
        return (x, y) in self._occupancy

    def get_piece_id_at(self, x: int, y: int) -> str | None:
        """Return the piece ID at (x, y), or None if the node is empty."""
        return self._occupancy.get((x, y))

    def is_empty(self, x: int, y: int) -> bool:
        return not self.is_occupied(x, y)

    # ------------------------------------------------------------------
    # Occupancy mutations
    # Called by modification/ layer only — never directly from rules/.
    # ------------------------------------------------------------------

    def place_piece(self, piece_id: str, x: int, y: int) -> None:
        """Mark (x, y) as occupied by *piece_id*."""
        if not is_within_board(x, y):
            raise ValueError(f"Position ({x}, {y}) is outside the board.")
        if (x, y) in self._occupancy:
            raise ValueError(
                f"Cannot place '{piece_id}' at ({x}, {y}): "
                f"already occupied by '{self._occupancy[(x, y)]}'."
            )
        self._occupancy[(x, y)] = piece_id

    def remove_piece(self, x: int, y: int) -> str:
        """
        Clear occupancy at (x, y) and return the piece ID that was there.
        Raises KeyError if the node was already empty.
        """
        if (x, y) not in self._occupancy:
            raise KeyError(f"No piece at ({x}, {y}) to remove.")
        return self._occupancy.pop((x, y))

    def move_piece(self, from_pos: Pos, to_pos: Pos) -> None:
        """
        Relocate a piece from *from_pos* to *to_pos*.
        Verifies both nodes are within the board and the destination is empty.
        """
        fx, fy = from_pos
        tx, ty = to_pos
        if not is_within_board(tx, ty):
            raise ValueError(f"Destination ({tx}, {ty}) is outside the board.")
        if self.is_occupied(tx, ty):
            raise ValueError(f"Destination ({tx}, {ty}) is already occupied.")
        piece_id = self.remove_piece(fx, fy)
        self._occupancy[(tx, ty)] = piece_id

    # ------------------------------------------------------------------
    # Board-wide queries (used by event_rules, recognition, etc.)
    # ------------------------------------------------------------------

    def all_occupied_nodes(self) -> list[Pos]:
        """Return all nodes currently occupied by live pieces."""
        return list(self._occupancy.keys())

    def all_empty_nodes(self) -> list[Pos]:
        """Return all valid board nodes that are NOT occupied."""
        occupied = set(self._occupancy.keys())
        return [
            (x, y)
            for x in range(self.cols)
            for y in range(self.rows)
            if (x, y) not in occupied
        ]

    def snapshot(self) -> dict[Pos, str]:
        """Return a shallow copy of the occupancy map (for history recording)."""
        return dict(self._occupancy)

    def __repr__(self) -> str:
        return f"Board(occupied={len(self._occupancy)} nodes)"
