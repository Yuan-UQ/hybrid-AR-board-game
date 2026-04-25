"""
Map normalized recognition coordinates into arena board positions.

The current marker pipeline already reports logical board nodes as `(col, row)`,
so this module mainly centralizes type-normalization and intent.
"""

from __future__ import annotations

from collections.abc import Mapping

Pos = tuple[int, int]


def vision_pos_to_arena_pos(pos: tuple[int, int] | list[int]) -> Pos:
    """Normalize a vision-space board node into the arena `(x, y)` tuple shape."""
    return int(pos[0]), int(pos[1])


def map_piece_cells(piece_cells: Mapping[int, Pos]) -> dict[int, Pos]:
    """Normalize all vision-reported piece coordinates into arena positions."""
    return {
        int(aruco_id): vision_pos_to_arena_pos(pos)
        for aruco_id, pos in piece_cells.items()
    }

