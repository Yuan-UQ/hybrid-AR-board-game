"""
固定拓扑数字棋盘窗口：摄像头仅在后台做 ArUco 检测与网格计算；
主窗口为预渲染的 9×10 棋盘画布，棋子位置按格子绘制，避免摄像头叠加带来的网格抖动/屏闪。
走子记录写入 JSONL（每行一条 JSON）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# 由 detect_marker / cursor_test 等通过 configure_host() 注入；未设置时回退 cursor_test
_HOST = None


def configure_host(module):
    """让稳定棋盘与宿主脚本共用同一套 BOARD_* / piece_* 实现（单摄像头、单份 move_log）。"""
    global _HOST
    _HOST = module


def host():
    if _HOST is not None:
        return _HOST
    import cursor_test as cursor_test_mod

    return cursor_test_mod


_MOVE_LINE_RE = re.compile(
    r"^([\w_]+) \((\d+),(\d+)\)->\((\d+),(\d+)\)$"
)


def _offsets_as_tuples(corner_state):
    return {k: (int(v[0]), int(v[1])) for k, v in corner_state.items()}


def build_detected_markers(corners, ids):
    """与 cursor_test 主循环一致的 marker 语义（四角 + 棋子）。"""
    detected_markers = {}
    if ids is None or len(ids) == 0:
        return detected_markers
    h = host()
    for i, marker_id in enumerate(ids.flatten()):
        marker_id = int(marker_id)
        pts = corners[i][0]
        center = np.mean(pts, axis=0).astype(int)
        cx, cy = int(center[0]), int(center[1])
        if marker_id in h.PIECE_ARUCO_ID_SET:
            detected_markers[marker_id] = {
                "center": (cx, cy),
                "pts": pts,
                "board_point": (cx, cy),
                "label": h.PIECE_ARUCO_IDS[marker_id],
            }
            continue

        if marker_id == h.BOARD_MARKER_IDS["BLACK_LEFT"]:
            board_point = tuple(pts[0].astype(int))
            label = "BLACK_LEFT"
        elif marker_id == h.BOARD_MARKER_IDS["BLACK_RIGHT"]:
            board_point = tuple(pts[1].astype(int))
            label = "BLACK_RIGHT"
        elif marker_id == h.BOARD_MARKER_IDS["RED_RIGHT"]:
            board_point = tuple(pts[2].astype(int))
            label = "RED_RIGHT"
        elif marker_id == h.BOARD_MARKER_IDS["RED_LEFT"]:
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
    return detected_markers


def make_static_board_raster(cell_px: int, margin: int, line_color, bg_color, footer_h: int = 120):
    """
    预渲染整张棋盘线（不含棋子），每帧 copy 后再画棋子，网格像素永不因摄像头而抖动。
    footer_h：底部留白给走子文字，避免压住网格。
    """
    hmod = host()
    w = margin * 2 + (hmod.BOARD_COLS - 1) * cell_px
    grid_h = margin * 2 + (hmod.BOARD_ROWS - 1) * cell_px
    h = grid_h + footer_h
    img = np.full((h, w, 3), bg_color, dtype=np.uint8)

    def node_xy(col, row):
        return (
            margin + col * cell_px,
            margin + row * cell_px,
        )

    for row in range(hmod.BOARD_ROWS):
        pts = np.array([node_xy(c, row) for c in range(hmod.BOARD_COLS)], dtype=np.int32)
        cv2.polylines(img, [pts], False, line_color, 1)
    for col in range(hmod.BOARD_COLS):
        pts = np.array([node_xy(col, r) for r in range(hmod.BOARD_ROWS)], dtype=np.int32)
        cv2.polylines(img, [pts], False, line_color, 1)

    river_y = []
    for x in range(hmod.BOARD_COLS):
        _, y4 = node_xy(x, 4)
        _, y5 = node_xy(x, 5)
        river_y.append((margin + x * cell_px, (y4 + y5) // 2))
    cv2.polylines(
        img,
        [np.array(river_y, dtype=np.int32)],
        False,
        (180, 80, 200),
        2,
    )

    def palace_poly(corners_board):
        arr = np.array([node_xy(c, r) for c, r in corners_board], dtype=np.int32)
        return arr

    cv2.polylines(
        img,
        [palace_poly([(3, 0), (5, 0), (5, 2), (3, 2)])],
        True,
        (60, 60, 255),
        2,
    )
    cv2.polylines(
        img,
        [palace_poly([(3, 7), (5, 7), (5, 9), (3, 9)])],
        True,
        (255, 80, 80),
        2,
    )

    rx, ry = node_xy(0, 0)
    cv2.putText(img, "RED y=0", (rx, max(ry - 8, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 100, 255), 1)
    bx, by = node_xy(0, 9)
    cv2.putText(
        img,
        "BLACK y=9",
        (bx, min(by + 22, grid_h - 6)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 120, 120),
        1,
    )

    return img, node_xy


def append_moves_jsonl(path: Path, move_log: list, start_index: int):
    """把 move_log[start_index:] 解析并追加写入 JSONL。"""
    if start_index >= len(move_log):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for line in move_log[start_index:]:
            m = _MOVE_LINE_RE.match(line.strip())
            if not m:
                continue
            name, c0, r0, c1, r1 = m.groups()
            rec = {
                "ts": time.time(),
                "piece": name,
                "from": [int(c0), int(r0)],
                "to": [int(c1), int(r1)],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def piece_cells_this_frame(corners, ids, grid, piece_off_fwd, piece_off_side, cell_radius_mult):
    """当前帧每枚棋子的 (col,row)，用于在固定棋盘上显示（未稳定也显示，避免「消失」）。"""
    out = {}
    if grid is None or ids is None:
        return out
    h = host()
    for i, mid in enumerate(ids.flatten()):
        mid = int(mid)
        if mid not in h.PIECE_ARUCO_ID_SET:
            continue
        pts = corners[i][0]
        fx, fy = h.piece_foot_xy(pts, piece_off_fwd, piece_off_side)
        cell = h.nearest_board_cell(fx, fy, grid, cell_radius_mult)
        if cell is not None:
            out[mid] = cell
    return out


def render_stable_board_frame(
    static_raster,
    node_xy_fn,
    *,
    board_ok,
    grid,
    corners,
    ids,
    piece_off_fwd,
    piece_off_side,
    piece_cell_mult,
    cell_px,
    move_log,
):
    """
    仅负责绘制稳定棋盘图（不修改 move_log、不做检测）。
    供 detect_marker 等与摄像头主循环联动时调用。
    """
    h = host()
    canvas = static_raster.copy()
    status = "Board: OK" if board_ok else "Board: lost (waiting for 4 corners)"
    cv2.putText(
        canvas,
        status,
        (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 140) if board_ok else (80, 80, 255),
        2,
    )

    if board_ok and ids is not None and grid is not None:
        live_cells = piece_cells_this_frame(
            corners, ids, grid, piece_off_fwd, piece_off_side, piece_cell_mult
        )
        for mid, cell in live_cells.items():
            col, row = cell
            name = h.PIECE_ARUCO_IDS[mid]
            x, y = node_xy_fn(col, row)
            color = (100, 200, 255) if name.startswith("red_") else (180, 180, 255)
            rpix = max(10, cell_px // 4)
            cv2.circle(canvas, (x, y), rpix, color, -1)
            cv2.circle(canvas, (x, y), rpix, (40, 40, 40), 1)
            short = name.replace("red_", "R").replace("black_", "B")[:10]
            cv2.putText(
                canvas,
                short,
                (x - 18, y - max(12, cell_px // 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (240, 240, 240),
                1,
            )

    h_canvas = static_raster.shape[0]
    cv2.putText(
        canvas,
        "Last moves:",
        (8, h_canvas - 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (160, 160, 160),
        1,
    )
    for i, line in enumerate(move_log[-5:]):
        cv2.putText(
            canvas,
            line[:56],
            (8, h_canvas - 90 + i * 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (200, 220, 200),
            1,
        )
    return canvas


def main():
    parser = argparse.ArgumentParser(
        description="Stable board window + background move log (uses cursor_test detection math)."
    )
    parser.add_argument("--source", default="1", help="Camera index or URL")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--no-line-snap", action="store_true")
    parser.add_argument("--snap-radius", type=int, default=22)
    parser.add_argument("--warp-width", type=int, default=900)
    parser.add_argument("--warp-height", type=int, default=1000)
    parser.add_argument("--warp-quad-expand", type=float, default=0.0)
    parser.add_argument("--piece-off-fwd", type=float, default=0.0)
    parser.add_argument("--piece-off-side", type=float, default=0.0)
    parser.add_argument("--piece-cell-mult", type=float, default=None)
    parser.add_argument("--aruco-strict", action="store_true")
    parser.add_argument("--cell-px", type=int, default=52, help="固定棋盘格间距（像素）")
    parser.add_argument("--margin", type=int, default=36)
    parser.add_argument(
        "--log-file",
        type=str,
        default="piece_moves.jsonl",
        help="走子 JSONL 路径（相对当前工作目录）",
    )
    parser.add_argument(
        "--show-camera",
        action="store_true",
        help="额外显示摄像头调试小窗（默认仅稳定棋盘）",
    )
    args = parser.parse_args()
    hm = host()
    if args.piece_cell_mult is None:
        args.piece_cell_mult = hm.DEFAULT_PIECE_CELL_RADIUS_MULT

    log_path = Path(args.log_file)

    source = int(args.source) if str(args.source).isdigit() else args.source
    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print(f"Error: cannot open video source: {args.source}")
        return

    aruco_dict = cv2.aruco.getPredefinedDictionary(hm.ARUCO_DICT)
    parameters = (
        cv2.aruco.DetectorParameters()
        if args.aruco_strict
        else hm.make_piece_friendly_aruco_params()
    )
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    corner_state = {
        k: [hm.BOARD_CORNER_OFFSETS[k][0], hm.BOARD_CORNER_OFFSETS[k][1]]
        for k in hm.OFFSET_EDIT_ORDER
    }
    line_snap_enabled = not args.no_line_snap
    piece_off_fwd = float(args.piece_off_fwd)
    piece_off_side = float(args.piece_off_side)
    piece_cell_mult = float(args.piece_cell_mult)

    piece_last_cell = {}
    piece_streak = {}
    move_log: list[str] = []
    log_flush_index = 0

    static_raster, node_xy = make_static_board_raster(
        args.cell_px, args.margin, (220, 220, 220), (28, 32, 38)
    )

    win_board = "Xiangqi — stable board"
    cv2.namedWindow(win_board, cv2.WINDOW_AUTOSIZE)
    if args.show_camera:
        win_cam = "Camera (debug)"
        cv2.namedWindow(win_cam, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win_cam, min(640, args.width), min(360, args.height))

    print(f"Move log -> {log_path.resolve()}")
    print("ESC on stable board window: quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: failed to read frame")
            break

        grid = None
        board_ok = False
        corners, ids, _ = detector.detectMarkers(frame)
        detected_markers = build_detected_markers(corners, ids)
        board_points = hm.get_board_points_from_semantic_corners(
            detected_markers, _offsets_as_tuples(corner_state)
        )

        if board_points is not None:
            board_ok = True
            if line_snap_enabled:
                grid = hm.compute_grid_snapped_to_image(
                    frame,
                    board_points,
                    args.warp_width,
                    args.warp_height,
                    args.snap_radius,
                    args.warp_quad_expand,
                    enable_snap=True,
                )
            else:
                grid = hm.compute_board_grid(board_points)

            if ids is not None:
                hm.update_piece_tracking(
                    corners,
                    ids,
                    grid,
                    piece_last_cell,
                    piece_streak,
                    move_log,
                    hm.PIECE_CELL_STABLE_FRAMES,
                    piece_off_fwd,
                    piece_off_side,
                    piece_cell_mult,
                )

        append_moves_jsonl(log_path, move_log, log_flush_index)
        log_flush_index = len(move_log)

        canvas = render_stable_board_frame(
            static_raster,
            node_xy,
            board_ok=board_ok,
            grid=grid,
            corners=corners,
            ids=ids,
            piece_off_fwd=piece_off_fwd,
            piece_off_side=piece_off_side,
            piece_cell_mult=piece_cell_mult,
            cell_px=args.cell_px,
            move_log=move_log,
        )

        cv2.imshow(win_board, canvas)
        if args.show_camera:
            small = cv2.resize(frame, (0, 0), fx=0.35, fy=0.35)
            cv2.imshow(win_cam, small)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    append_moves_jsonl(log_path, move_log, log_flush_index)


if __name__ == "__main__":
    main()
