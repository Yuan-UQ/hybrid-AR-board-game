"""
Bridge `detect_marker_4.7.py` into the arena recognition interface.

This adapter reuses the existing ArUco / board-grid / stable-move logic without
pulling the original UI loop into the pygame application.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import cv2

from xiangqi_arena.recognition.marker_parser import marker_info_from_aruco
from xiangqi_arena.recognition.position_mapper import map_piece_cells
from xiangqi_arena.recognition.recognition_validator import validate_piece_cells
from xiangqi_arena.recognition.scanner_interface import (
    ScannerMoveEvent,
    ScannerSnapshot,
    VisionScanner,
)

_DETECT_MODULE = None


def _load_detect_module():
    global _DETECT_MODULE
    if _DETECT_MODULE is not None:
        return _DETECT_MODULE

    project_root = Path(__file__).resolve().parents[2]
    module_path = project_root / "detect_marker_4.7.py"
    spec = importlib.util.spec_from_file_location("detect_marker_4_7_bridge", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load vision module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("detect_marker_4_7_bridge", module)
    spec.loader.exec_module(module)
    _DETECT_MODULE = module
    return module


class DetectMarkerScanner(VisionScanner):
    """Camera-backed scanner that emits stable movement events."""

    def __init__(
        self,
        *,
        source: str | int = 1,
        width: int = 1280,
        height: int = 720,
        line_snap: bool = True,
        snap_radius: int = 22,
        warp_width: int = 900,
        warp_height: int = 1000,
        warp_quad_expand: float = 0.0,
        piece_off_fwd: float = 0.0,
        piece_off_side: float = 0.0,
        piece_cell_mult: float | None = None,
        aruco_strict: bool = False,
    ) -> None:
        self._dm = _load_detect_module()
        if piece_cell_mult is None:
            piece_cell_mult = self._dm.DEFAULT_PIECE_CELL_RADIUS_MULT

        source_value = int(source) if str(source).isdigit() else source
        self._cap = cv2.VideoCapture(source_value)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open vision source: {source}")

        aruco_dict = cv2.aruco.getPredefinedDictionary(self._dm.ARUCO_DICT)
        params = (
            cv2.aruco.DetectorParameters()
            if aruco_strict
            else self._dm.make_piece_friendly_aruco_params()
        )
        self._detector = cv2.aruco.ArucoDetector(aruco_dict, params)

        self._line_snap = bool(line_snap)
        self._snap_radius = int(snap_radius)
        self._warp_width = int(warp_width)
        self._warp_height = int(warp_height)
        self._warp_quad_expand = float(warp_quad_expand)
        self._piece_off_fwd = float(piece_off_fwd)
        self._piece_off_side = float(piece_off_side)
        self._piece_cell_mult = float(piece_cell_mult)

        self._corner_state = {
            key: [self._dm.BOARD_CORNER_OFFSETS[key][0], self._dm.BOARD_CORNER_OFFSETS[key][1]]
            for key in self._dm.OFFSET_EDIT_ORDER
        }
        self._piece_last_cell: dict[int, tuple[int, int]] = {}
        self._piece_streak: dict[int, tuple[tuple[int, int] | None, int]] = {}
        self._move_log: list[str] = []
        self._pending_events: list[ScannerMoveEvent] = []
        self._last_snapshot: ScannerSnapshot | None = None
        self._board_missing_streak = 0
        self._board_visibility_grace_frames = 12

    def poll_snapshot(self) -> ScannerSnapshot | None:
        """Grab one frame, update tracking state, and return the latest snapshot."""
        ret, frame = self._cap.read()
        if not ret:
            return self._last_snapshot

        corners, ids, _rejected = self._detector.detectMarkers(frame)
        detected_markers = self._build_detected_markers(corners, ids)

        board_points = self._dm.get_board_points_from_semantic_corners(
            detected_markers,
            self._dm._offsets_as_tuples(self._corner_state),
        )

        if board_points is not None:
            self._board_missing_streak = 0
        else:
            self._board_missing_streak += 1

        grid = None
        if board_points is not None:
            if self._line_snap:
                grid = self._dm.compute_grid_snapped_to_image(
                    frame,
                    board_points,
                    self._warp_width,
                    self._warp_height,
                    self._snap_radius,
                    self._warp_quad_expand,
                    enable_snap=True,
                )
            else:
                grid = self._dm.compute_board_grid(board_points)

        previous_cells = dict(self._piece_last_cell)
        if grid is not None and ids is not None and len(ids) > 0:
            self._dm.update_piece_tracking(
                corners,
                ids,
                grid,
                self._piece_last_cell,
                self._piece_streak,
                self._move_log,
                self._dm.PIECE_CELL_STABLE_FRAMES,
                self._piece_off_fwd,
                self._piece_off_side,
                self._piece_cell_mult,
            )

        timestamp = time.time()
        self._collect_move_events(previous_cells, timestamp)
        board_visible = (
            board_points is not None
            or self._board_missing_streak <= self._board_visibility_grace_frames
        )
        self._last_snapshot = self._build_snapshot(board_visible, timestamp)
        return self._last_snapshot

    def poll_move_events(self) -> list[ScannerMoveEvent]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()

    def _build_detected_markers(self, corners, ids) -> dict[int, dict]:
        markers: dict[int, dict] = {}
        if ids is None or len(ids) == 0:
            return markers

        for i, marker_id in enumerate(ids.flatten()):
            marker_id = int(marker_id)
            pts = corners[i][0]
            center = pts.mean(axis=0).astype(int)
            cx, cy = int(center[0]), int(center[1])

            if marker_id in self._dm.PIECE_ARUCO_ID_SET:
                markers[marker_id] = {
                    "center": (cx, cy),
                    "pts": pts,
                    "board_point": (cx, cy),
                    "label": self._dm.PIECE_ARUCO_IDS[marker_id],
                }
                continue

            if marker_id == self._dm.BOARD_MARKER_IDS["BLACK_LEFT"]:
                board_point = tuple(pts[0].astype(int))
                label = "BLACK_LEFT"
            elif marker_id == self._dm.BOARD_MARKER_IDS["BLACK_RIGHT"]:
                board_point = tuple(pts[1].astype(int))
                label = "BLACK_RIGHT"
            elif marker_id == self._dm.BOARD_MARKER_IDS["RED_RIGHT"]:
                board_point = tuple(pts[2].astype(int))
                label = "RED_RIGHT"
            elif marker_id == self._dm.BOARD_MARKER_IDS["RED_LEFT"]:
                board_point = tuple(pts[3].astype(int))
                label = "RED_LEFT"
            else:
                board_point = (cx, cy)
                label = f"ID:{marker_id}"

            markers[marker_id] = {
                "center": (cx, cy),
                "pts": pts,
                "board_point": board_point,
                "label": label,
            }

        return markers

    def _collect_move_events(self, previous_cells: dict[int, tuple[int, int]], timestamp: float) -> None:
        for aruco_id, to_pos in self._piece_last_cell.items():
            from_pos = previous_cells.get(aruco_id)
            if from_pos is None or from_pos == to_pos:
                continue
            info = marker_info_from_aruco(aruco_id)
            self._pending_events.append(
                ScannerMoveEvent(
                    aruco_id=aruco_id,
                    vision_name=info.vision_name,
                    piece_id=info.piece_id,
                    from_pos=from_pos,
                    to_pos=to_pos,
                    timestamp=timestamp,
                )
            )

    def _build_snapshot(self, board_visible: bool, timestamp: float) -> ScannerSnapshot:
        aruco_cells = map_piece_cells(self._piece_last_cell)
        validation = validate_piece_cells(aruco_cells)
        return ScannerSnapshot(
            timestamp=timestamp,
            board_visible=board_visible,
            complete=validation.ok,
            aruco_cells=dict(aruco_cells),
            piece_cells=dict(validation.normalized_piece_cells),
            missing_aruco_ids=validation.missing_aruco_ids,
            diagnostics=validation.errors,
        )
