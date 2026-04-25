"""
Validate recognition results before entering game flow.

Typical checks:
- missing pieces, duplicates, overlaps
- illegal coordinates / out-of-bounds
- incompatible marker identities

This module must not judge gameplay legality.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from xiangqi_arena.core.utils import is_within_board
from xiangqi_arena.recognition.marker_parser import (
    REQUIRED_ARUCO_IDS,
    normalize_piece_cells,
)

Pos = tuple[int, int]


@dataclass(frozen=True)
class RecognitionValidation:
    ok: bool
    missing_aruco_ids: tuple[int, ...] = ()
    errors: tuple[str, ...] = ()
    normalized_piece_cells: dict[str, Pos] = field(default_factory=dict)


def validate_piece_cells(piece_cells_by_aruco: Mapping[int, Pos]) -> RecognitionValidation:
    """Validate a stable recognition snapshot before syncing it into the arena."""
    errors: list[str] = []
    missing = tuple(sorted(set(REQUIRED_ARUCO_IDS) - {int(pid) for pid in piece_cells_by_aruco}))

    for aruco_id, pos in piece_cells_by_aruco.items():
        x, y = int(pos[0]), int(pos[1])
        if not is_within_board(x, y):
            errors.append(f"aruco {aruco_id} out of bounds: {(x, y)}")

    try:
        normalized = normalize_piece_cells(piece_cells_by_aruco)
    except ValueError as exc:
        return RecognitionValidation(ok=False, missing_aruco_ids=missing, errors=(str(exc),))

    if len(normalized) != len(piece_cells_by_aruco):
        errors.append("duplicate arena piece ids after marker normalization")

    occupied: dict[Pos, str] = {}
    for piece_id, pos in normalized.items():
        if pos in occupied:
            errors.append(f"overlap at {pos}: {occupied[pos]} and {piece_id}")
        else:
            occupied[pos] = piece_id

    return RecognitionValidation(
        ok=not errors and not missing,
        missing_aruco_ids=missing,
        errors=tuple(errors),
        normalized_piece_cells=normalized,
    )

