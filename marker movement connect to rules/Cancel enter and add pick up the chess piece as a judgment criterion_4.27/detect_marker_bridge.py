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

from xiangqi_arena.debug_log import debug_log
from xiangqi_arena.recognition.attack_gesture import AttackGestureTracker
from xiangqi_arena.recognition.marker_parser import (
    aruco_id_from_piece_id,
    marker_info_from_aruco,
)
from xiangqi_arena.recognition.position_mapper import map_piece_cells
from xiangqi_arena.recognition.recognition_validator import validate_piece_cells
from xiangqi_arena.recognition.scanner_interface import (
    ScannerAttackEvent,
    ScannerMoveEvent,
    ScannerSelectionEvent,
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
        self._pending_selection_events: list[ScannerSelectionEvent] = []
        self._pending_events: list[ScannerMoveEvent] = []
        self._pending_attack_events: list[ScannerAttackEvent] = []
        self._last_snapshot: ScannerSnapshot | None = None
        self._board_missing_streak = 0
        self._board_visibility_grace_frames = 12
        self._display_piece_cells: dict[int, tuple[int, int]] = {}
        self._display_candidate_cells: dict[int, tuple[int, int]] | None = None
        self._display_candidate_started_at: float | None = None
        self._display_stable_seconds = 0.4
        self._armed_selection_aruco_ids: set[int] = set()
        self._selection_confirm_seconds = 2.0
        self._selection_missing_since: dict[int, float] = {}
        self._armed_attack_piece_id: str | None = None
        self._attack_tracker = AttackGestureTracker(
            contact_confirm_frames=max(2, self._dm.PIECE_CELL_STABLE_FRAMES // 2),
            return_confirm_frames=max(2, self._dm.PIECE_CELL_STABLE_FRAMES // 2),
            max_gesture_frames=max(12, self._dm.PIECE_CELL_STABLE_FRAMES * 6),
        )

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
        visible_piece_cells, visible_piece_ids = self._build_visible_piece_cells(corners, ids, grid)
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
        self._update_display_piece_cells(timestamp)
        self._collect_selection_events(visible_piece_cells, visible_piece_ids, timestamp)
        self._collect_move_events(previous_cells, timestamp)
        self._collect_attack_events(previous_cells, visible_piece_cells, visible_piece_ids, timestamp)
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

    def poll_selection_events(self) -> list[ScannerSelectionEvent]:
        events = list(self._pending_selection_events)
        self._pending_selection_events.clear()
        return events

    def poll_attack_events(self) -> list[ScannerAttackEvent]:
        events = list(self._pending_attack_events)
        self._pending_attack_events.clear()
        return events

    def arm_selection_tracking(self, piece_ids: list[str]) -> None:
        armed_ids = {aruco_id_from_piece_id(piece_id) for piece_id in piece_ids}
        if armed_ids == self._armed_selection_aruco_ids:
            return
        self._armed_selection_aruco_ids = set(armed_ids)
        self._selection_missing_since.clear()
        self._pending_selection_events.clear()

    def clear_selection_tracking(self) -> None:
        self._armed_selection_aruco_ids.clear()
        self._selection_missing_since.clear()
        self._pending_selection_events.clear()

    def arm_attack_tracking(self, piece_id: str, origin_pos: tuple[int, int]) -> None:
        aruco_id = aruco_id_from_piece_id(piece_id)
        if self._armed_attack_piece_id == piece_id:
            return
        self._armed_attack_piece_id = piece_id
        self._attack_tracker.arm(aruco_id, origin_pos)
        self._pending_attack_events.clear()
        # region agent log
        debug_log(
            location="xiangqi_arena/recognition/detect_marker_bridge.py:188",
            message="attack_tracking_armed",
            data={
                "pieceId": piece_id,
                "arucoId": aruco_id,
                "originPos": list(origin_pos),
            },
            hypothesis_id="H2",
        )
        # endregion

    def clear_attack_tracking(self) -> None:
        self._armed_attack_piece_id = None
        self._pending_attack_events.clear()
        self._attack_tracker.clear()

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

    def _update_display_piece_cells(self, timestamp: float) -> None:
        raw_cells = dict(self._piece_last_cell)
        if raw_cells == self._display_piece_cells:
            self._display_candidate_cells = None
            self._display_candidate_started_at = None
            return
        if self._display_candidate_cells != raw_cells:
            self._display_candidate_cells = raw_cells
            self._display_candidate_started_at = timestamp
            return
        if (
            self._display_candidate_started_at is not None
            and (timestamp - self._display_candidate_started_at) >= self._display_stable_seconds
        ):
            self._display_piece_cells = dict(raw_cells)
            self._display_candidate_cells = None
            self._display_candidate_started_at = None

    @staticmethod
    def _missing_armed_selection_ids(
        armed_selection_aruco_ids: set[int],
        visible_piece_ids: set[int],
    ) -> list[int]:
        return [
            aruco_id
            for aruco_id in sorted(armed_selection_aruco_ids)
            if aruco_id not in visible_piece_ids
        ]

    def _collect_selection_events(
        self,
        visible_piece_cells: dict[int, tuple[int, int]],
        visible_piece_ids: set[int],
        timestamp: float,
    ) -> None:
        if not self._armed_selection_aruco_ids:
            return

        missing_ids = self._missing_armed_selection_ids(
            self._armed_selection_aruco_ids,
            visible_piece_ids,
        )

        missing_set = set(missing_ids)
        for aruco_id in self._armed_selection_aruco_ids:
            if aruco_id in missing_set:
                self._selection_missing_since.setdefault(aruco_id, timestamp)
            else:
                self._selection_missing_since.pop(aruco_id, None)

        missing_duration_ms = {
            str(aruco_id): int((timestamp - started_at) * 1000)
            for aruco_id, started_at in sorted(self._selection_missing_since.items())
        }

        # region agent log
        debug_log(
            location="xiangqi_arena/recognition/detect_marker_bridge.py:320",
            message="selection_tracking_progress",
            data={
                "armedSelectionIds": sorted(self._armed_selection_aruco_ids),
                "visibleIds": sorted(visible_piece_ids),
                "missingIds": missing_ids,
                "selectionMissingMs": missing_duration_ms,
                "displayPieceCount": len(self._display_piece_cells),
            },
            hypothesis_id="H9",
        )
        # endregion

        ready_ids = [
            aruco_id
            for aruco_id, started_at in self._selection_missing_since.items()
            if (timestamp - started_at) >= self._selection_confirm_seconds
        ]
        if not ready_ids:
            return

        aruco_id = min(
            ready_ids,
            key=lambda candidate_id: (
                self._selection_missing_since[candidate_id],
                candidate_id,
            ),
        )
        info = marker_info_from_aruco(aruco_id)
        origin_pos = self._piece_last_cell.get(aruco_id)
        if origin_pos is None:
            self._selection_missing_since.pop(aruco_id, None)
            return
        self._pending_selection_events.append(
            ScannerSelectionEvent(
                aruco_id=aruco_id,
                vision_name=info.vision_name,
                piece_id=info.piece_id,
                origin_pos=origin_pos,
                timestamp=timestamp,
            )
        )
        # region agent log
        debug_log(
            location="xiangqi_arena/recognition/detect_marker_bridge.py:346",
            message="selection_event_enqueued",
            data={
                "pieceId": info.piece_id,
                "arucoId": aruco_id,
                "originPos": list(origin_pos),
            },
            hypothesis_id="H9",
        )
        # endregion
        self._armed_selection_aruco_ids.clear()
        self._selection_missing_since.clear()

    def _collect_attack_events(
        self,
        stable_cells: dict[int, tuple[int, int]],
        visible_piece_cells: dict[int, tuple[int, int]],
        visible_piece_ids: set[int],
        timestamp: float,
    ) -> None:
        if self._armed_attack_piece_id is None:
            return
        matches = self._attack_tracker.step(
            stable_cells=stable_cells,
            visible_cells=visible_piece_cells,
            visible_ids=visible_piece_ids,
            timestamp=timestamp,
        )
        for match in matches:
            attacker_info = marker_info_from_aruco(match.attacker_aruco_id)
            covered_piece_id = None
            if match.covered_aruco_id is not None:
                covered_piece_id = marker_info_from_aruco(match.covered_aruco_id).piece_id
            # region agent log
            debug_log(
                location="xiangqi_arena/recognition/detect_marker_bridge.py:291",
                message="bridge_attack_event_enqueued",
                data={
                    "pieceId": attacker_info.piece_id,
                    "originPos": list(match.origin_pos),
                    "contactPos": list(match.contact_pos),
                    "coveredPieceId": covered_piece_id,
                },
                hypothesis_id="H2",
            )
            # endregion
            self._pending_attack_events.append(
                ScannerAttackEvent(
                    aruco_id=match.attacker_aruco_id,
                    vision_name=attacker_info.vision_name,
                    piece_id=attacker_info.piece_id,
                    origin_pos=match.origin_pos,
                    contact_pos=match.contact_pos,
                    covered_aruco_id=match.covered_aruco_id,
                    covered_piece_id=covered_piece_id,
                    timestamp=timestamp,
                )
            )

    def _build_visible_piece_cells(self, corners, ids, grid) -> tuple[dict[int, tuple[int, int]], set[int]]:
        visible_piece_cells: dict[int, tuple[int, int]] = {}
        visible_piece_ids: set[int] = set()
        if grid is None or ids is None or len(ids) == 0:
            return visible_piece_cells, visible_piece_ids

        for i, marker_id in enumerate(ids.flatten()):
            marker_id = int(marker_id)
            if marker_id not in self._dm.PIECE_ARUCO_ID_SET:
                continue
            visible_piece_ids.add(marker_id)
            pts = corners[i][0]
            fx, fy = self._dm.piece_foot_xy(pts, self._piece_off_fwd, self._piece_off_side)
            cell = self._dm.nearest_board_cell(fx, fy, grid, self._piece_cell_mult)
            if cell is not None:
                visible_piece_cells[marker_id] = cell

        return visible_piece_cells, visible_piece_ids

    def _build_snapshot(
        self,
        board_visible: bool,
        timestamp: float,
    ) -> ScannerSnapshot:
        aruco_cells = map_piece_cells(self._display_piece_cells)
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
