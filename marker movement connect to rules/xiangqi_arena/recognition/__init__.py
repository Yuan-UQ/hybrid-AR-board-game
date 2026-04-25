"""
Recognition integration.

Converts physical-board recognition results into normalized logical coordinates and
piece identities consumable by the game logic. This layer should not implement
gameplay legality rules.
"""

from xiangqi_arena.recognition.marker_parser import (
    ARUCO_TO_VISION_NAME,
    REQUIRED_ARUCO_IDS,
    VISION_NAME_TO_ARENA_ID,
    build_game_state_from_snapshot,
    marker_info_from_aruco,
    normalize_piece_cells,
)
from xiangqi_arena.recognition.recognition_validator import (
    RecognitionValidation,
    validate_piece_cells,
)
from xiangqi_arena.recognition.scanner_interface import (
    ScannerMoveEvent,
    ScannerSnapshot,
    VisionScanner,
)

__all__ = [
    "ARUCO_TO_VISION_NAME",
    "REQUIRED_ARUCO_IDS",
    "VISION_NAME_TO_ARENA_ID",
    "build_game_state_from_snapshot",
    "marker_info_from_aruco",
    "normalize_piece_cells",
    "RecognitionValidation",
    "validate_piece_cells",
    "ScannerMoveEvent",
    "ScannerSnapshot",
    "VisionScanner",
]

