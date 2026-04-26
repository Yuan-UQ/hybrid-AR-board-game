"""
Selection handler.

Converts raw mouse positions to board nodes and maintains UI selection state:
  - which piece is currently selected
  - what positions are valid moves / attack targets

This module is pure input-mapping and state-tracking; it does not mutate
GameState directly.  The main loop reads these values and calls the
appropriate modification functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xiangqi_arena.core.constants import BOARD_COLS, BOARD_ROWS
from xiangqi_arena.core.utils import Pos
from xiangqi_arena.ui.board_renderer import node_to_pixel
from xiangqi_arena.ui.display_config import NODE_SNAP


# ---------------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------------


def pixel_to_node(px: int, py: int) -> Pos | None:
    """Screen pixel → nearest board node within NODE_SNAP, or None."""
    for bx in range(BOARD_COLS):
        for by in range(BOARD_ROWS):
            nx, ny = node_to_pixel(bx, by)
            if abs(px - nx) <= NODE_SNAP and abs(py - ny) <= NODE_SNAP:
                return (bx, by)
    return None


# ---------------------------------------------------------------------------
# Selection state
# ---------------------------------------------------------------------------

@dataclass
class SelectionState:
    """Per-phase transient UI selection state."""

    selected_pid: str | None = None     # piece ID currently selected
    selected_pos: Pos | None = None     # pixel-convenience copy of its pos
    valid_moves: list[Pos]   = field(default_factory=list)
    valid_attacks: list[Pos] = field(default_factory=list)

    def select(self, pid: str, pos: Pos,
               moves: list[Pos], attacks: list[Pos]) -> None:
        self.selected_pid = pid
        self.selected_pos = pos
        self.valid_moves  = list(moves)
        self.valid_attacks = list(attacks)

    def deselect(self) -> None:
        self.selected_pid  = None
        self.selected_pos  = None
        self.valid_moves   = []
        self.valid_attacks = []

    def clear_highlights(self) -> None:
        """Keep selection but remove highlight lists (e.g. after a move)."""
        self.valid_moves   = []
        self.valid_attacks = []

    @property
    def has_selection(self) -> bool:
        return self.selected_pid is not None
