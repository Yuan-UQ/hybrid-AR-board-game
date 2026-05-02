"""
Camera-backed ArUco tracker for feeding physical piece positions into the UI.

The existing calibration and board-detection logic lives in detect_marker_4.7.py.
That filename is not importable as a normal Python module, so this wrapper loads
it by path and exposes a small game-facing API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, FrozenSet

from xiangqi_arena.core.utils import is_within_board


_DETECT_MODULE: ModuleType | None = None

# ArUco ID printed on the back of every physical piece (river_left.png).
# When a piece is flipped face-down, this marker becomes visible at the cell
# previously occupied by the piece's front-side marker — the game treats this
# as "the player has selected the piece in that cell".
SELECT_MARKER_ID: int = 4


MARKER_LABEL_TO_PIECE_ID: dict[str, str] = {
    "red_general": "GeneralHuman",
    "red_chariot": "ArcherHuman",
    "red_horse": "LancerHuman",
    "red_cannon": "WizardHuman",
    "red_pawn_1": "Soldier1Human",
    "red_pawn_2": "Soldier2Human",
    "red_pawn_3": "Soldier3Human",
    "black_general": "GeneralOrc",
    "black_chariot": "ArcherSkeleton",
    "black_horse": "RiderOrc",
    "black_cannon": "Slime Orc",
    "black_pawn_1": "Soldier1Orc",
    "black_pawn_2": "Soldier2Skeleton",
    "black_pawn_3": "Soldier3Skeleton",
}


@dataclass(frozen=True)
class VisionFrame:
    """Stable game-board positions from one camera frame."""

    positions: dict[str, tuple[int, int]]
    board_ok: bool
    detected_markers: int
    tracked_pieces: int
    conflicts: list[str] = field(default_factory=list)
    # Game-space cells where the back-side SELECT_MARKER_ID was detected.
    # Empty when no piece is currently flipped face-down.
    selection_cells: tuple[tuple[int, int], ...] = ()
    # Piece IDs whose *front* ArUco marker was actually seen in this frame.
    # ``positions`` may still list pieces from last-frame tracking cache; flip
    # detection must use this set instead of ``positions.keys()`` to know
    # whether the face-up marker is absent (face-down / SELECT flow).
    front_piece_ids_this_frame: FrozenSet[str] = frozenset()
    # Per-piece game cells from ``piece_last_cell`` *without* overlap pruning.
    # When two markers briefly map to the same cell, ``positions`` drops one
    # or both entries; the vision commit pipeline can still read the camera
    # cell for the selected piece here.
    raw_piece_positions: tuple[tuple[str, int, int], ...] = ()


def _load_detect_module() -> ModuleType:
    global _DETECT_MODULE
    if _DETECT_MODULE is not None:
        return _DETECT_MODULE

    detect_path = Path(__file__).resolve().parents[2] / "detect_marker_4.7.py"
    spec = importlib.util.spec_from_file_location("detect_marker_4_7_runtime", detect_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load vision module from {detect_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _DETECT_MODULE = module
    return module


def physical_cell_to_game_pos(
    cell: tuple[int, int],
    *,
    flip_y: bool = False,
) -> tuple[int, int] | None:
    """
    Convert physical Xiangqi grid coordinates to Xiangqi Arena coordinates.

    detect_marker_4.7.py reports a 9 x 10 board as (col, row). The game logic
    uses a 10 x 9 board as (x, y), so the physical row becomes game x and the
    physical column becomes game y.
    """
    col, row = cell
    game_x = int(row)
    game_y = 8 - int(col) if flip_y else int(col)
    pos = (game_x, game_y)
    return pos if is_within_board(*pos) else None


class VisionTracker:
    """Read stable physical piece positions from the camera."""

    def __init__(
        self,
        *,
        source: str | int = "0",
        width: int = 1280,
        height: int = 720,
        use_line_snap: bool = True,
        snap_radius: int = 22,
        warp_width: int = 900,
        warp_height: int = 1000,
        warp_quad_expand: float = 0.0,
        piece_off_fwd: float = 0.0,
        piece_off_side: float = 0.0,
        piece_cell_mult: float | None = None,
        stable_frames: int | None = None,
        aruco_strict: bool = False,
        board_cache_grace_frames: int = 100,
        flip_y: bool = False,
        debug: bool = False,
    ) -> None:
        self.dm = _load_detect_module()
        self.cv2 = self.dm.cv2
        self.np = self.dm.np
        self.debug = bool(debug)
        self.use_line_snap = bool(use_line_snap)
        self.snap_radius = int(snap_radius)
        self.warp_width = int(warp_width)
        self.warp_height = int(warp_height)
        self.warp_quad_expand = float(warp_quad_expand)
        self.piece_off_fwd = float(piece_off_fwd)
        self.piece_off_side = float(piece_off_side)
        self.piece_cell_mult = (
            float(piece_cell_mult)
            if piece_cell_mult is not None
            else float(self.dm.DEFAULT_PIECE_CELL_RADIUS_MULT)
        )
        self.stable_frames = (
            int(stable_frames)
            if stable_frames is not None
            else int(self.dm.PIECE_CELL_STABLE_FRAMES)
        )
        self.board_cache_grace_frames = int(board_cache_grace_frames)
        self.flip_y = bool(flip_y)

        camera_source: str | int = int(source) if str(source).isdigit() else source
        self.cap = self.cv2.VideoCapture(camera_source)
        self.cap.set(self.cv2.CAP_PROP_FRAME_WIDTH, int(width))
        self.cap.set(self.cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {source}")

        aruco_dict = self.cv2.aruco.getPredefinedDictionary(self.dm.ARUCO_DICT)
        parameters = (
            self.cv2.aruco.DetectorParameters()
            if aruco_strict
            else self.dm.make_piece_friendly_aruco_params()
        )
        self.detector = self.cv2.aruco.ArucoDetector(aruco_dict, parameters)

        self.piece_last_cell: dict[int, tuple[int, int]] = {}
        self.piece_streak: dict[int, tuple[tuple[int, int] | None, int]] = {}
        self.move_log: list[str] = []
        self.last_valid_board_points: dict[str, tuple[int, int]] | None = None
        self.board_points_missing_streak = 0
        self.last_positions: dict[str, tuple[int, int]] = {}

    def _front_piece_ids_from_ids(self, ids: Any) -> frozenset[str]:
        """Map current-frame ArUco ids to logical piece ids (face-up markers only)."""
        if ids is None or len(ids) == 0:
            return frozenset()
        out: set[str] = set()
        for mid in ids.flatten():
            mid = int(mid)
            if mid == SELECT_MARKER_ID:
                continue
            if mid not in self.dm.PIECE_ARUCO_ID_SET:
                continue
            label = self.dm.PIECE_ARUCO_IDS.get(mid)
            if label is None:
                continue
            pid = MARKER_LABEL_TO_PIECE_ID.get(label)
            if pid is not None:
                out.add(pid)
        return frozenset(out)

    def close(self) -> None:
        self.cap.release()
        if self.debug:
            self.cv2.destroyWindow("Xiangqi Arena Vision")

    def read_positions(self) -> VisionFrame:
        ret, frame = self.cap.read()
        if not ret:
            return VisionFrame(
                positions=dict(self.last_positions),
                board_ok=False,
                detected_markers=0,
                tracked_pieces=len(self.last_positions),
                conflicts=["failed to read camera frame"],
                front_piece_ids_this_frame=frozenset(),
                raw_piece_positions=(),
            )

        grid, corners, ids, detected_count, board_ok, select_centers = self._detect_grid(frame)
        front_piece_ids = self._front_piece_ids_from_ids(ids)
        if board_ok and ids is not None:
            self.dm.update_piece_tracking(
                corners,
                ids,
                grid,
                self.piece_last_cell,
                self.piece_streak,
                self.move_log,
                self.stable_frames,
                self.piece_off_fwd,
                self.piece_off_side,
                self.piece_cell_mult,
            )

        positions, conflicts = self._stable_cells_to_game_positions()
        if positions:
            self.last_positions = positions

        raw_map = self._raw_piece_cells_to_game_positions()
        raw_piece_positions = tuple(
            sorted((pid, int(xy[0]), int(xy[1])) for pid, xy in raw_map.items())
        )

        selection_cells = self._select_centers_to_game_positions(grid, select_centers, board_ok)

        if self.debug:
            self._draw_debug(frame, grid, corners, ids, board_ok, select_centers)

        return VisionFrame(
            positions=dict(self.last_positions),
            board_ok=board_ok,
            detected_markers=detected_count,
            tracked_pieces=len(self.last_positions),
            conflicts=conflicts,
            selection_cells=selection_cells,
            front_piece_ids_this_frame=front_piece_ids,
            raw_piece_positions=raw_piece_positions,
        )

    def _detect_grid(
        self,
        frame: Any,
    ) -> tuple[Any | None, Any | None, Any | None, int, bool, list[tuple[int, int]]]:
        corners, ids, _rejected = self.detector.detectMarkers(frame)
        detected_count = 0 if ids is None else len(ids)
        detected_markers: dict[int, dict[str, Any]] = {}
        select_centers: list[tuple[int, int]] = []

        if ids is not None and len(ids) > 0:
            for i, marker_id in enumerate(ids.flatten()):
                marker_id = int(marker_id)
                pts = corners[i][0]
                center = self.np.mean(pts, axis=0).astype(int)
                cx, cy = int(center[0]), int(center[1])

                if marker_id == SELECT_MARKER_ID:
                    select_centers.append((cx, cy))
                    continue

                if marker_id in self.dm.PIECE_ARUCO_ID_SET:
                    detected_markers[marker_id] = {
                        "center": (cx, cy),
                        "pts": pts,
                        "board_point": (cx, cy),
                        "label": self.dm.PIECE_ARUCO_IDS[marker_id],
                    }
                    continue

                if marker_id == self.dm.BOARD_MARKER_IDS["BLACK_LEFT"]:
                    board_point = tuple(pts[0].astype(int))
                    label = "BLACK_LEFT"
                elif marker_id == self.dm.BOARD_MARKER_IDS["BLACK_RIGHT"]:
                    board_point = tuple(pts[1].astype(int))
                    label = "BLACK_RIGHT"
                elif marker_id == self.dm.BOARD_MARKER_IDS["RED_RIGHT"]:
                    board_point = tuple(pts[2].astype(int))
                    label = "RED_RIGHT"
                elif marker_id == self.dm.BOARD_MARKER_IDS["RED_LEFT"]:
                    board_point = tuple(pts[3].astype(int))
                    label = "RED_LEFT"
                else:
                    board_point = (cx, cy)
                    label = f"ID:{marker_id}"

                detected_markers[marker_id] = {
                    "center": (cx, cy),
                    "pts": pts,
                    "board_point": board_point,
                    "label": label,
                }

        observed = self.dm.get_board_points_from_semantic_corners(
            detected_markers,
            self.dm._offsets_as_tuples(self.dm.BOARD_CORNER_OFFSETS),
        )
        if observed is not None:
            board_points = dict(observed)
            self.last_valid_board_points = dict(observed)
            self.board_points_missing_streak = 0
        else:
            self.board_points_missing_streak += 1
            if (
                self.last_valid_board_points is not None
                and self.board_points_missing_streak <= self.board_cache_grace_frames
            ):
                board_points = dict(self.last_valid_board_points)
            else:
                board_points = None

        if board_points is None:
            return None, corners, ids, detected_count, False, select_centers

        if self.use_line_snap:
            grid = self.dm.compute_grid_snapped_to_image(
                frame,
                board_points,
                self.warp_width,
                self.warp_height,
                self.snap_radius,
                self.warp_quad_expand,
                enable_snap=True,
            )
        else:
            grid = self.dm.compute_board_grid(board_points)

        return grid, corners, ids, detected_count, True, select_centers

    def _select_centers_to_game_positions(
        self,
        grid: Any,
        select_centers: list[tuple[int, int]],
        board_ok: bool,
    ) -> tuple[tuple[int, int], ...]:
        if not select_centers or not board_ok or grid is None:
            return ()

        cells: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for cx, cy in select_centers:
            cell = self.dm.nearest_board_cell(cx, cy, grid, self.piece_cell_mult)
            if cell is None:
                continue
            game_pos = physical_cell_to_game_pos(cell, flip_y=self.flip_y)
            if game_pos is None or game_pos in seen:
                continue
            seen.add(game_pos)
            cells.append(game_pos)
        return tuple(cells)

    def _stable_cells_to_game_positions(self) -> tuple[dict[str, tuple[int, int]], list[str]]:
        positions: dict[str, tuple[int, int]] = {}
        conflicts: list[str] = []
        occupied: dict[tuple[int, int], str] = {}

        for marker_id, cell in self.piece_last_cell.items():
            label = self.dm.PIECE_ARUCO_IDS.get(marker_id)
            piece_id = MARKER_LABEL_TO_PIECE_ID.get(label)
            if piece_id is None:
                continue

            game_pos = physical_cell_to_game_pos(cell, flip_y=self.flip_y)
            if game_pos is None:
                conflicts.append(f"{piece_id}: physical cell {cell} is outside game board")
                continue

            other = occupied.get(game_pos)
            if other is not None:
                conflicts.append(f"{piece_id} overlaps {other} at {game_pos}")
                positions.pop(other, None)
                continue

            occupied[game_pos] = piece_id
            positions[piece_id] = game_pos

        return positions, conflicts

    def _raw_piece_cells_to_game_positions(self) -> dict[str, tuple[int, int]]:
        """
        Map each tracked front marker to a game cell without overlap pruning.

        Unlike ``_stable_cells_to_game_positions``, this never removes a piece
        when two markers snap to the same node — both stay in the dict so the
        UI can still read a moving piece that temporarily disappeared from
        ``positions`` due to conflict resolution.
        """
        out: dict[str, tuple[int, int]] = {}
        for marker_id, cell in self.piece_last_cell.items():
            label = self.dm.PIECE_ARUCO_IDS.get(marker_id)
            piece_id = MARKER_LABEL_TO_PIECE_ID.get(label)
            if piece_id is None:
                continue
            game_pos = physical_cell_to_game_pos(cell, flip_y=self.flip_y)
            if game_pos is None:
                continue
            out[piece_id] = game_pos
        return out

    def _draw_debug(
        self,
        frame: Any,
        grid: Any,
        corners: Any,
        ids: Any,
        board_ok: bool,
        select_centers: list[tuple[int, int]] | None = None,
    ) -> None:
        if ids is not None and len(ids) > 0:
            self.cv2.aruco.drawDetectedMarkers(frame, corners, ids)
        if board_ok and grid is not None:
            self.dm.draw_board_overlay(frame, grid)
            self.dm.draw_piece_labels(
                frame,
                grid,
                corners,
                ids,
                self.piece_off_fwd,
                self.piece_off_side,
                self.piece_cell_mult,
            )

        if select_centers:
            for cx, cy in select_centers:
                self.cv2.circle(frame, (int(cx), int(cy)), 18, (0, 255, 255), 3)
                self.cv2.putText(
                    frame,
                    "SELECT",
                    (int(cx) + 22, int(cy) - 10),
                    self.cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 255),
                    2,
                )
        self.cv2.imshow("Xiangqi Arena Vision", frame)
        self.cv2.waitKey(1)
