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

from xiangqi_arena.core.utils import Pos
from xiangqi_arena.ui.display_config import BOARD_LEFT, BOARD_TOP, CELL, NODE_SNAP


# ---------------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------------

def node_to_pixel(x: int, y: int) -> tuple[int, int]:
    """Board node → screen pixel (same formula as board_renderer)."""
    return BOARD_LEFT + x * CELL, BOARD_TOP + (9 - y) * CELL


def pixel_to_node(px: int, py: int) -> Pos | None:
    """Screen pixel → nearest board node within NODE_SNAP, or None."""
    for bx in range(9):
        for by in range(10):
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
