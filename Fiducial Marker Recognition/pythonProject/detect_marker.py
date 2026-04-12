import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

_DM_DIR = Path(__file__).resolve().parent
if str(_DM_DIR) not in sys.path:
    sys.path.insert(0, str(_DM_DIR))

import stable_board_view as sbv

# =========================
# 1. 配置区
# =========================

# 你实际贴在四角的 marker ID
BOARD_MARKER_IDS = {
    "RED_LEFT": 2,
    "BLACK_RIGHT": 3,
    "BLACK_LEFT": 0,
    "RED_RIGHT": 1,
}

# 你现在实际使用的 ArUco 字典
ARUCO_DICT = cv2.aruco.DICT_4X4_50

# 棋盘节点数：9列 x 10行
BOARD_COLS = 9   # x = 0~8
BOARD_ROWS = 10  # y = 0~9
# marker 参考点 到 棋盘真实四角 的像素偏移 (dx, dy)
# 这是第一版建议值，后面可以继续微调
BOARD_CORNER_OFFSETS = {
    "RED_LEFT": (23, 36),
    "RED_RIGHT": (33, -23),
    "BLACK_LEFT": (-39, 28),
    "BLACK_RIGHT": (-23, -38),
}

# 运行时微调顺序（与 Tab 切换一致）
OFFSET_EDIT_ORDER = ["RED_LEFT", "RED_RIGHT", "BLACK_LEFT", "BLACK_RIGHT"]

# 棋盘四角 ArUco ID（勿用作棋子）
BOARD_ARUCO_IDS = frozenset(BOARD_MARKER_IDS.values())

# 14 枚棋子：ID 与 generate_marker/generate_markers.py、markers/*.png 英文名一致（ASCII，便于 putText）
PIECE_ARUCO_IDS = {
    10: "red_general",
    11: "red_chariot",
    12: "red_horse",
    13: "red_cannon",
    14: "red_pawn_1",
    15: "red_pawn_2",
    16: "red_pawn_3",
    17: "black_general",
    18: "black_chariot",
    19: "black_horse",
    20: "black_cannon",
    21: "black_pawn_1",
    22: "black_pawn_2",
    23: "black_pawn_3",
}
PIECE_ARUCO_ID_SET = frozenset(PIECE_ARUCO_IDS.keys())

# 棋子落在某一格需连续稳定帧数后才确认（防抖）
PIECE_CELL_STABLE_FRAMES = 4

# 默认：格子匹配半径 = cell_step * 此系数（偏心贴 marker 时可调大到 ~0.9~1.0）
DEFAULT_PIECE_CELL_RADIUS_MULT = 0.88

# waitKeyEx 常见方向键码（Windows/Linux Qt 后端多为下列值）
_KEY_LEFT = 65361
_KEY_UP = 65362
_KEY_RIGHT = 65363
_KEY_DOWN = 65364

# =========================
# 2. 几何工具函数
# =========================

def get_board_points_from_semantic_corners(detected_markers, corner_offsets):
    """
    按游戏规则固定数字棋盘方向：
    y = 0 在红方一侧
    y = 9 在黑方一侧

    所以：
    TL = BLACK_LEFT
    TR = BLACK_RIGHT
    BR = RED_RIGHT
    BL = RED_LEFT

    但 marker 贴在棋盘外侧安全位置，所以这里用
    marker参考点 + offset = 棋盘真实角点
    """
    required_ids = [
        BOARD_MARKER_IDS["RED_LEFT"],
        BOARD_MARKER_IDS["RED_RIGHT"],
        BOARD_MARKER_IDS["BLACK_LEFT"],
        BOARD_MARKER_IDS["BLACK_RIGHT"],
    ]

    for rid in required_ids:
        if rid not in detected_markers:
            return None

    red_left_raw = detected_markers[BOARD_MARKER_IDS["RED_LEFT"]]["board_point"]
    red_right_raw = detected_markers[BOARD_MARKER_IDS["RED_RIGHT"]]["board_point"]
    black_left_raw = detected_markers[BOARD_MARKER_IDS["BLACK_LEFT"]]["board_point"]
    black_right_raw = detected_markers[BOARD_MARKER_IDS["BLACK_RIGHT"]]["board_point"]

    red_left = apply_offset(red_left_raw, corner_offsets["RED_LEFT"])
    red_right = apply_offset(red_right_raw, corner_offsets["RED_RIGHT"])
    black_left = apply_offset(black_left_raw, corner_offsets["BLACK_LEFT"])
    black_right = apply_offset(black_right_raw, corner_offsets["BLACK_RIGHT"])

    return {
        "TL": red_left,
        "TR": red_right,
        "BR": black_right,
        "BL": black_left,
    }
def apply_offset(point, offset):
    x, y = point
    dx, dy = offset
    return (int(x + dx), int(y + dy))

def lerp(p1, p2, t):
    """线性插值"""
    return (1 - t) * np.array(p1, dtype=np.float32) + t * np.array(p2, dtype=np.float32)


def compute_board_grid(board_corners):
    """
    根据四角点，生成 9x10 的交叉点坐标。
    board_corners:
        {
            "TL": (x, y),
            "TR": (x, y),
            "BR": (x, y),
            "BL": (x, y)
        }

    返回:
        grid[y][x] = (px, py)
    """
    TL = np.array(board_corners["TL"], dtype=np.float32)
    TR = np.array(board_corners["TR"], dtype=np.float32)
    BR = np.array(board_corners["BR"], dtype=np.float32)
    BL = np.array(board_corners["BL"], dtype=np.float32)

    grid = []
    for y in range(BOARD_ROWS):
        ty = y / (BOARD_ROWS - 1)

        # 左边界、右边界上的对应点
        left = lerp(TL, BL, ty)
        right = lerp(TR, BR, ty)

        row_points = []
        for x in range(BOARD_COLS):
            tx = x / (BOARD_COLS - 1)
            pt = lerp(left, right, tx)
            row_points.append((int(pt[0]), int(pt[1])))
        grid.append(row_points)

    return grid


def expand_quad_xy(quad_xy, ratio):
    """quad_xy: (4,2) 顺序 TL,TR,BR,BL"""
    quad_xy = np.asarray(quad_xy, dtype=np.float32)
    center = np.mean(quad_xy, axis=0, keepdims=True)
    return (center + (quad_xy - center) * (1.0 + float(ratio))).astype(np.float32)


def generate_grid_points_warp(warp_w, warp_h, margin=0):
    """鸟瞰图中的 10x9 均匀交叉点（与 compute_board_grid 拓扑一致）。"""
    points = []
    for row in range(BOARD_ROWS):
        row_points = []
        y = margin + row * (warp_h - 2 * margin - 1) / (BOARD_ROWS - 1)
        for col in range(BOARD_COLS):
            x = margin + col * (warp_w - 2 * margin - 1) / (BOARD_COLS - 1)
            row_points.append((int(round(x)), int(round(y))))
        points.append(row_points)
    return points


def refine_axis_positions(scores, expected_positions, search_radius):
    refined = []
    n = len(scores)
    for pos in expected_positions:
        c = int(round(pos))
        left = max(0, c - search_radius)
        right = min(n - 1, c + search_radius)
        if right <= left:
            refined.append(c)
            continue
        local = scores[left : right + 1]
        best = int(np.argmax(local)) + left
        refined.append(best)
    return refined


def snap_grid_to_board_lines(warped_bgr, grid_points, search_radius):
    """
    在鸟瞰图上用自适应阈值 + 形态学突出横竖线，再把理论网格线位置吸附到附近最强响应。
    """
    gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        7,
    )
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25))
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    col_scores = np.sum(vertical, axis=0).astype(np.float32)
    row_scores = np.sum(horizontal, axis=1).astype(np.float32)
    expected_x = [grid_points[0][col][0] for col in range(BOARD_COLS)]
    expected_y = [grid_points[row][0][1] for row in range(BOARD_ROWS)]
    refined_x = refine_axis_positions(col_scores, expected_x, search_radius)
    refined_y = refine_axis_positions(row_scores, expected_y, search_radius)
    refined_points = []
    for row in range(BOARD_ROWS):
        row_pts = []
        for col in range(BOARD_COLS):
            row_pts.append((int(refined_x[col]), int(refined_y[row])))
        refined_points.append(row_pts)
    return refined_points


def compute_grid_snapped_to_image(
    bgr,
    board_points,
    warp_w,
    warp_h,
    snap_radius,
    quad_expand,
    enable_snap=True,
):
    """
    用四角透视到 warp 平面，在 warp 上吸附实体线，再透视回摄像头坐标。
    board_points: TL,TR,BR,BL 与 get_board_points_from_semantic_corners 一致。
    """
    keys = ("TL", "TR", "BR", "BL")
    src = np.array(
        [[float(board_points[k][0]), float(board_points[k][1])] for k in keys],
        dtype=np.float32,
    )
    if quad_expand > 0:
        src = expand_quad_xy(src, quad_expand)
    dst = np.array(
        [
            [0, 0],
            [warp_w - 1, 0],
            [warp_w - 1, warp_h - 1],
            [0, warp_h - 1],
        ],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(src, dst)
    Minv = cv2.getPerspectiveTransform(dst, src)
    warped = cv2.warpPerspective(bgr, M, (warp_w, warp_h))
    grid_w = generate_grid_points_warp(warp_w, warp_h, margin=0)
    if enable_snap:
        grid_w = snap_grid_to_board_lines(warped, grid_w, snap_radius)
    grid_img = []
    for row in range(BOARD_ROWS):
        row_pts = []
        for col in range(BOARD_COLS):
            wx, wy = grid_w[row][col]
            p = np.array([[[float(wx), float(wy)]]], dtype=np.float32)
            im = cv2.perspectiveTransform(p, Minv)[0, 0]
            row_pts.append((int(round(im[0])), int(round(im[1]))))
        grid_img.append(row_pts)
    return grid_img


def piece_foot_xy(pts, fwd_px, side_px):
    """
    marker 贴在棋子顶面偏心处时，用 ArUco 四角定义的局部轴估计「落点」：
    角点顺序 0-TL, 1-TR, 2-BR, 3-BL（与 OpenCV 一致）。
    u_down：从上边中点到下边中点；u_right：从左到中到右中。
    落点 = 几何中心 + fwd_px*u_down + side_px*u_right（像素）。
    """
    c = np.asarray(pts, dtype=np.float64)
    top_mid = (c[0] + c[1]) * 0.5
    bot_mid = (c[2] + c[3]) * 0.5
    right_mid = (c[1] + c[2]) * 0.5
    left_mid = (c[0] + c[3]) * 0.5
    v_down = bot_mid - top_mid
    v_right = right_mid - left_mid
    ld = float(np.linalg.norm(v_down))
    lr = float(np.linalg.norm(v_right))
    u_down = (v_down / ld) if ld > 1e-6 else np.array([0.0, 1.0], dtype=np.float64)
    u_right = (v_right / lr) if lr > 1e-6 else np.array([1.0, 0.0], dtype=np.float64)
    center = np.mean(c, axis=0)
    foot = center + float(fwd_px) * u_down + float(side_px) * u_right
    return float(foot[0]), float(foot[1])


def nearest_board_cell(px, py, grid, radius_mult=0.55):
    """将图像坐标映射到最近交叉点 (col,row)；过远返回 None。radius_mult 为相对格宽的倍数。"""
    if grid is None:
        return None
    best = None
    best_d = 1e18
    for row in range(BOARD_ROWS):
        for col in range(BOARD_COLS):
            gx, gy = grid[row][col]
            d = (float(gx) - px) ** 2 + (float(gy) - py) ** 2
            if d < best_d:
                best_d = d
                best = (col, row)
    g00 = np.array(grid[0][0], dtype=np.float32)
    g01 = np.array(grid[0][1], dtype=np.float32)
    cell_step = float(np.linalg.norm(g00 - g01))
    if cell_step < 1e-3:
        return best
    thresh = (cell_step * float(radius_mult)) ** 2
    if best_d > thresh:
        return None
    return best


def update_piece_tracking(
    corners,
    ids,
    grid,
    piece_last_cell,
    piece_streak,
    move_log,
    stable_need,
    piece_off_fwd,
    piece_off_side,
    cell_radius_mult,
):
    """更新每枚棋子的格子并记录走子；不改变棋盘几何。"""
    if grid is None or ids is None or len(ids) == 0:
        return

    seen_piece_ids = {int(ids[i][0]) for i in range(len(ids))} & PIECE_ARUCO_ID_SET

    for i, mid in enumerate(ids.flatten()):
        mid = int(mid)
        if mid not in PIECE_ARUCO_ID_SET:
            continue
        pts = corners[i][0]
        fx, fy = piece_foot_xy(pts, piece_off_fwd, piece_off_side)
        cell = nearest_board_cell(fx, fy, grid, cell_radius_mult)
        name = PIECE_ARUCO_IDS[mid]

        prev_streak_cell, cnt = piece_streak.get(mid, (None, 0))
        if cell is None:
            piece_streak[mid] = (None, 0)
            continue
        if prev_streak_cell == cell:
            cnt += 1
        else:
            cnt = 1
        piece_streak[mid] = (cell, cnt)

        if cnt < stable_need:
            continue

        old = piece_last_cell.get(mid)
        if old != cell:
            if old is not None:
                msg = f"{name} ({old[0]},{old[1]})->({cell[0]},{cell[1]})"
                move_log.append(msg)
                print(f"[MOVE] {msg}")
            piece_last_cell[mid] = cell

    for pid in PIECE_ARUCO_ID_SET:
        if pid not in seen_piece_ids and pid in piece_streak:
            piece_streak[pid] = (None, 0)


def draw_piece_labels(
    frame,
    grid,
    corners,
    ids,
    piece_off_fwd,
    piece_off_side,
    cell_radius_mult,
):
    """标注棋子名称与格子；圆圈画在估计落点（foot），小红点标 marker 几何中心。"""
    if grid is None or ids is None:
        return
    for i, mid in enumerate(ids.flatten()):
        mid = int(mid)
        if mid not in PIECE_ARUCO_ID_SET:
            continue
        pts = corners[i][0]
        mx = int(np.mean(pts[:, 0]))
        my = int(np.mean(pts[:, 1]))
        fx, fy = piece_foot_xy(pts, piece_off_fwd, piece_off_side)
        ix, iy = int(round(fx)), int(round(fy))
        name = PIECE_ARUCO_IDS[mid]
        cell = nearest_board_cell(fx, fy, grid, cell_radius_mult)
        sub = f" ({cell[0]},{cell[1]})" if cell else " ?"
        cv2.circle(frame, (mx, my), 4, (0, 165, 255), -1)
        cv2.circle(frame, (ix, iy), 14, (255, 0, 255), 2)
        cv2.putText(
            frame,
            name + sub,
            (ix + 12, iy - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 0, 255),
            2,
        )


def draw_polyline_by_board_coords(frame, grid, coords, color, thickness=2):
    """
    coords: [(x1,y1), (x2,y2), ...]
    """
    pts = np.array([grid[y][x] for (x, y) in coords], dtype=np.int32)
    cv2.polylines(frame, [pts], isClosed=False, color=color, thickness=thickness)


def draw_closed_polygon_by_board_coords(frame, grid, coords, color, thickness=2):
    pts = np.array([grid[y][x] for (x, y) in coords], dtype=np.int32)
    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=thickness)

def draw_final_board_corners(frame, board_points):
    for name, (x, y) in board_points.items():
        cv2.circle(frame, (x, y), 10, (0, 255, 0), -1)
        cv2.putText(
            frame,
            f"CORNER-{name}",
            (x + 10, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2
        )

# =========================
# 3. 绘制数字棋盘
# =========================

def draw_board_overlay(frame, grid):
    # 画所有横线
    for y in range(BOARD_ROWS):
        pts = np.array(grid[y], dtype=np.int32)
        cv2.polylines(frame, [pts], isClosed=False, color=(255, 255, 255), thickness=1)

    # 画所有竖线
    for x in range(BOARD_COLS):
        col_pts = np.array([grid[y][x] for y in range(BOARD_ROWS)], dtype=np.int32)
        cv2.polylines(frame, [col_pts], isClosed=False, color=(255, 255, 255), thickness=1)

    # 画交叉点 + 坐标文字
    for y in range(BOARD_ROWS):
        for x in range(BOARD_COLS):
            px, py = grid[y][x]
            cv2.circle(frame, (px, py), 4, (0, 255, 255), -1)
            cv2.putText(
                frame,
                f"({x},{y})",
                (px + 6, py - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 255, 255),
                1
            )

    # 河界：在 y=4 和 y=5 之间
    river_pts_top = []
    river_pts_bottom = []
    for x in range(BOARD_COLS):
        p4 = np.array(grid[4][x], dtype=np.float32)
        p5 = np.array(grid[5][x], dtype=np.float32)
        mid = ((p4 + p5) / 2).astype(int)
        river_pts_top.append(tuple(mid))
        river_pts_bottom.append(tuple(mid))

    river_line = np.array(river_pts_top, dtype=np.int32)
    cv2.polylines(frame, [river_line], isClosed=False, color=(255, 0, 255), thickness=2)

    # 红方九宫格：x=3~5, y=0~2
    draw_closed_polygon_by_board_coords(
        frame, grid,
        [(3, 0), (5, 0), (5, 2), (3, 2)],
        color=(0, 0, 255),
        thickness=2
    )
    draw_polyline_by_board_coords(frame, grid, [(3, 0), (5, 2)], color=(0, 0, 255), thickness=2)
    draw_polyline_by_board_coords(frame, grid, [(5, 0), (3, 2)], color=(0, 0, 255), thickness=2)

    # 黑方九宫格：x=3~5, y=7~9
    draw_closed_polygon_by_board_coords(
        frame, grid,
        [(3, 7), (5, 7), (5, 9), (3, 9)],
        color=(255, 0, 0),
        thickness=2
    )
    draw_polyline_by_board_coords(frame, grid, [(3, 7), (5, 9)], color=(255, 0, 0), thickness=2)
    draw_polyline_by_board_coords(frame, grid, [(5, 7), (3, 9)], color=(255, 0, 0), thickness=2)

    # 简单标签
    red_label_pos = grid[0][0]
    black_label_pos = grid[9][0]

    cv2.putText(frame, "RED SIDE", (red_label_pos[0], red_label_pos[1] - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.putText(frame, "BLACK SIDE", (black_label_pos[0], black_label_pos[1] + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)


# =========================
# 4. 左侧状态面板
# =========================

def draw_status_panel(
    frame,
    current_player="RED",
    round_num=1,
    phase="MOVE",
    move_log=None,
    tracked_piece_count=0,
):
    h, w = frame.shape[:2]
    panel_w = 320
    if move_log is None:
        move_log = []

    # 新建一个更宽的画布
    canvas = np.zeros((h, w + panel_w, 3), dtype=np.uint8)
    canvas[:, :w] = frame

    # 面板背景
    canvas[:, w:] = (30, 30, 30)

    x0 = w + 15
    y = 40

    def put(line, color=(255, 255, 255), scale=0.7, dy=35):
        nonlocal y
        cv2.putText(canvas, line, (x0, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2)
        y += dy

    put("Xiangqi Arena", (0, 255, 255), 0.8, 40)
    put(f"Round: {round_num}", (255, 255, 255))
    put(f"Turn: {current_player}", (0, 200, 255) if current_player == "RED" else (255, 100, 100))
    put(f"Phase: {phase}", (0, 255, 0))

    y += 20
    put("Board Rules:", (200, 200, 200), 0.65, 30)
    put("9 x 10 nodes", (180, 180, 180), 0.55, 25)
    put("River: y=4/5", (180, 180, 180), 0.55, 25)
    put("Red palace: x3-5 y0-2", (180, 180, 180), 0.55, 25)
    put("Black palace: x3-5 y7-9", (180, 180, 180), 0.55, 25)

    y += 20
    put("Keys:", (200, 200, 200), 0.65, 30)
    put("TAB: sel corner", (180, 180, 180), 0.55, 25)
    put("Arrows: nudge dx/dy", (180, 180, 180), 0.55, 25)
    put("WASD: same as arrows", (180, 180, 180), 0.55, 25)
    put("[ ]: step 1/5/10", (180, 180, 180), 0.55, 25)
    put("P: print offsets", (180, 180, 180), 0.55, 25)
    put("G: toggle line snap", (180, 180, 180), 0.55, 25)
    put(", / .: snap radius", (180, 180, 180), 0.55, 25)
    put("C: clear move log", (180, 180, 180), 0.55, 25)
    put("I/K J/L: piece foot  Z/X: cell", (180, 180, 180), 0.55, 25)
    put("ENTER: next phase", (180, 180, 180), 0.55, 25)
    put("ESC: quit", (180, 180, 180), 0.55, 25)

    y += 10
    put(f"Pieces tracked: {tracked_piece_count}/14", (200, 255, 200), 0.55, 26)
    put("Recent moves:", (200, 200, 200), 0.55, 24)
    for line in move_log[-8:]:
        cv2.putText(
            canvas,
            line[:42] + ("…" if len(line) > 42 else ""),
            (x0, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (180, 220, 255),
            1,
        )
        y += 20

    return canvas


def make_piece_friendly_aruco_params():
    """略放宽参数，利于棋子上较小、略倾斜的 marker 解码。"""
    p = cv2.aruco.DetectorParameters()
    p.minMarkerPerimeterRate = 0.015
    p.maxMarkerPerimeterRate = 4.0
    p.polygonalApproxAccuracyRate = 0.05
    p.minCornerDistanceRate = 0.03
    p.minDistanceToBorder = 1
    p.adaptiveThreshWinSizeMin = 3
    p.adaptiveThreshWinSizeMax = 23
    p.adaptiveThreshWinSizeStep = 10
    crm = getattr(cv2.aruco, "CORNER_REFINE_SUBPIX", None)
    if crm is not None:
        p.cornerRefinementMethod = crm
    return p


def draw_piece_calibration_hud(frame, fwd, side, cell_mult, step):
    y = 268
    for line in (
        f"PIECE FOOT: fwd={fwd} side={side}  step={step}",
        "  I/K: fwd  J/L: side  (marker局部下/右)",
        f"  Z/X: cell match x  (now {cell_mult:.2f} x cell)",
        "  T: print values to console",
    ):
        cv2.putText(
            frame,
            line,
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 200, 100),
            1,
        )
        y += 20


def draw_offset_hud(frame, corner_state, edit_index, step):
    """在画面上提示当前微调的是哪一角、步长多少。"""
    name = OFFSET_EDIT_ORDER[edit_index]
    dx, dy = corner_state[name]
    lines = [
        f"OFFSET EDIT: {name}  step={step}",
        f"  dx={dx}  dy={dy}  (arrow/WASD)",
        "  TAB=next corner  P=print dict",
    ]
    y = 148
    for line in lines:
        cv2.putText(
            frame,
            line,
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 220, 255),
            2,
        )
        y += 22
    for i, k in enumerate(OFFSET_EDIT_ORDER):
        dxi, dyi = corner_state[k]
        mark = ">" if i == edit_index else " "
        cv2.putText(
            frame,
            f"{mark} {k}: ({dxi}, {dyi})",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (180, 255, 180) if i == edit_index else (120, 120, 120),
            1,
        )
        y += 18


def _offsets_as_tuples(corner_state):
    return {k: (int(v[0]), int(v[1])) for k, v in corner_state.items()}


def apply_offset_nudge(corner_state, target_name, ddx, ddy):
    corner_state[target_name][0] += ddx
    corner_state[target_name][1] += ddy


def handle_offset_keys(key, key8, corner_state, edit_index, step):
    """
    返回 (new_edit_index, new_step, did_nudge)。
    方向键 / WASD：在图像坐标系中移动 offset（dx 右为正，dy 下为正）。
    """
    new_i = edit_index
    new_step = step
    did = False
    target = OFFSET_EDIT_ORDER[edit_index]

    if key8 == ord("\t"):
        new_i = (edit_index + 1) % len(OFFSET_EDIT_ORDER)
        return new_i, new_step, False

    if key8 == ord("["):
        opts = (1, 5, 10)
        idx = opts.index(step) if step in opts else 0
        new_step = opts[(idx - 1) % len(opts)]
        return new_i, new_step, False

    if key8 == ord("]"):
        opts = (1, 5, 10)
        idx = opts.index(step) if step in opts else 0
        new_step = opts[(idx + 1) % len(opts)]
        return new_i, new_step, False

    if key8 in (ord("p"), ord("P")):
        print("\n# 复制到 BOARD_CORNER_OFFSETS：")
        print("BOARD_CORNER_OFFSETS = {")
        for k in OFFSET_EDIT_ORDER:
            dx, dy = corner_state[k]
            print(f'    "{k}": ({int(dx)}, {int(dy)}),')
        print("}")
        return new_i, new_step, False

    def nudge(ddx, ddy):
        nonlocal did
        apply_offset_nudge(corner_state, target, ddx, ddy)
        did = True

    # 方向键（waitKeyEx）
    if key == _KEY_LEFT:
        nudge(-step, 0)
    elif key == _KEY_RIGHT:
        nudge(step, 0)
    elif key == _KEY_UP:
        nudge(0, -step)
    elif key == _KEY_DOWN:
        nudge(0, step)
    # WASD 备用（不依赖 waitKeyEx）
    elif key8 == ord("a"):
        nudge(-step, 0)
    elif key8 == ord("d"):
        nudge(step, 0)
    elif key8 == ord("w"):
        nudge(0, -step)
    elif key8 == ord("s"):
        nudge(0, step)

    return new_i, new_step, did


# =========================
# 5. 主程序
# =========================

def main():
    parser = argparse.ArgumentParser(description="Detect ArUco markers and draw Xiangqi digital board.")
    parser.add_argument("--source", default="1", help="Camera index or stream URL")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--no-line-snap",
        action="store_true",
        help="关闭「鸟瞰图上线条吸附」，仅用四角双线性插值网格",
    )
    parser.add_argument(
        "--snap-radius",
        type=int,
        default=22,
        help="吸附时在理论线位置附近搜索的像素半径（鸟瞰图坐标）",
    )
    parser.add_argument("--warp-width", type=int, default=900, help="鸟瞰图宽度（内部透视用）")
    parser.add_argument("--warp-height", type=int, default=1000, help="鸟瞰图高度")
    parser.add_argument(
        "--warp-quad-expand",
        type=float,
        default=0.0,
        help="透视前四边形相对中心外扩比例（略包住棋盘外沿时可试 0.05~0.1）",
    )
    parser.add_argument(
        "--no-piece-track",
        action="store_true",
        help="关闭 14 枚棋子识别与走子记录（仅棋盘）",
    )
    parser.add_argument(
        "--piece-off-fwd",
        type=float,
        default=0.0,
        help="棋子落点：沿 marker 局部「向下」轴偏移（像素），偏心贴码时用 I/K 微调",
    )
    parser.add_argument(
        "--piece-off-side",
        type=float,
        default=0.0,
        help="棋子落点：沿 marker 局部「向右」轴偏移（像素），J/L 微调",
    )
    parser.add_argument(
        "--piece-cell-mult",
        type=float,
        default=None,
        help=f"格子匹配半径 = 格宽×该系数（默认 {DEFAULT_PIECE_CELL_RADIUS_MULT}），偏大更易认格",
    )
    parser.add_argument(
        "--aruco-strict",
        action="store_true",
        help="使用 OpenCV 默认 ArUco 检测参数（关闭针对小棋子的放宽）",
    )
    parser.add_argument(
        "--no-stable-board",
        action="store_true",
        help="不显示 stable_board_view 固定棋盘窗口（默认与主界面同时显示）",
    )
    parser.add_argument(
        "--stable-log-file",
        type=str,
        default="piece_moves.jsonl",
        help="稳定棋盘联动时的走子 JSONL 路径",
    )
    parser.add_argument("--stable-cell-px", type=int, default=52)
    parser.add_argument("--stable-margin", type=int, default=36)
    args = parser.parse_args()
    if args.piece_cell_mult is None:
        args.piece_cell_mult = DEFAULT_PIECE_CELL_RADIUS_MULT

    source = int(args.source) if str(args.source).isdigit() else args.source

    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        print(f"Error: cannot open video source: {args.source}")
        return

    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    parameters = (
        cv2.aruco.DetectorParameters()
        if args.aruco_strict
        else make_piece_friendly_aruco_params()
    )
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    last_print_time = 0
    print_interval = 0.5

    current_player = "RED"
    round_num = 1
    phase_list = ["START", "MOVE", "SCAN", "ATTACK", "END"]
    phase_index = 0

    corner_state = {k: [BOARD_CORNER_OFFSETS[k][0], BOARD_CORNER_OFFSETS[k][1]] for k in OFFSET_EDIT_ORDER}
    offset_edit_index = 0
    nudge_step = 1

    board_points = None
    line_snap_enabled = not args.no_line_snap
    piece_track_enabled = not args.no_piece_track
    piece_last_cell = {}
    piece_streak = {}
    move_log = []
    piece_off_fwd = float(args.piece_off_fwd)
    piece_off_side = float(args.piece_off_side)
    piece_cell_mult = float(args.piece_cell_mult)

    stable_board_on = not args.no_stable_board
    stable_log_path = Path(args.stable_log_file)
    stable_log_flush_idx = 0
    static_raster = None
    node_xy_fn = None
    win_stable = None
    if stable_board_on:
        sbv.configure_host(sys.modules[__name__])
        static_raster, node_xy_fn = sbv.make_static_board_raster(
            args.stable_cell_px,
            args.stable_margin,
            (220, 220, 220),
            (28, 32, 38),
        )
        win_stable = "Xiangqi — stable board"
        cv2.namedWindow(win_stable, cv2.WINDOW_AUTOSIZE)
        print(f"Stable board: {win_stable} (关闭请加 --no-stable-board)")
        print(f"Stable move log -> {stable_log_path.resolve()}")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: failed to read frame")
            break

        grid = None
        corners, ids, rejected = detector.detectMarkers(frame)

        detected_count = 0 if ids is None else len(ids)
        rejected_count = 0 if rejected is None else len(rejected)

        detected_markers = {}

        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            for i, marker_id in enumerate(ids.flatten()):
                marker_id = int(marker_id)
                pts = corners[i][0]  # 4个角点
                center = np.mean(pts, axis=0).astype(int)
                cx, cy = int(center[0]), int(center[1])

                # 先默认显示ID
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                cv2.putText(
                    frame,
                    f"ID:{marker_id}",
                    (cx + 8, cy - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 0, 0),
                    2
                )

                # 棋子 marker：不参与棋盘四角，不画黄点（避免与角点混淆）
                if marker_id in PIECE_ARUCO_ID_SET:
                    detected_markers[marker_id] = {
                        "center": (cx, cy),
                        "pts": pts,
                        "board_point": (cx, cy),
                        "label": PIECE_ARUCO_IDS[marker_id],
                    }
                    continue

                # 根据 marker 的棋盘语义，取更合理的棋盘角点
                if marker_id == BOARD_MARKER_IDS["BLACK_LEFT"]:
                    # 逻辑左上角
                    board_point = tuple(pts[0].astype(int))  # marker左上角
                    label = "BLACK_LEFT"

                elif marker_id == BOARD_MARKER_IDS["BLACK_RIGHT"]:
                    # 逻辑右上角
                    board_point = tuple(pts[1].astype(int))  # marker右上角
                    label = "BLACK_RIGHT"

                elif marker_id == BOARD_MARKER_IDS["RED_RIGHT"]:
                    # 逻辑右下角
                    board_point = tuple(pts[2].astype(int))  # marker右下角
                    label = "RED_RIGHT"

                elif marker_id == BOARD_MARKER_IDS["RED_LEFT"]:
                    # 逻辑左下角
                    board_point = tuple(pts[3].astype(int))  # marker左下角
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

                # 仅棋盘四角画黄点
                if marker_id in BOARD_ARUCO_IDS:
                    bx, by = board_point
                    cv2.circle(frame, (bx, by), 9, (0, 255, 255), -1)
                    cv2.putText(
                        frame,
                        label,
                        (bx + 10, by + 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (0, 255, 255),
                        2
                    )

        board_points = get_board_points_from_semantic_corners(
            detected_markers, _offsets_as_tuples(corner_state)
        )

        if board_points is not None:
            draw_final_board_corners(frame, board_points)
            if line_snap_enabled:
                grid = compute_grid_snapped_to_image(
                    frame,
                    board_points,
                    args.warp_width,
                    args.warp_height,
                    args.snap_radius,
                    args.warp_quad_expand,
                    enable_snap=True,
                )
                board_title = "Board+line snap"
            else:
                grid = compute_board_grid(board_points)
                board_title = "Board (interp)"
            draw_board_overlay(frame, grid)
            cv2.putText(
                frame,
                board_title,
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

            if piece_track_enabled and ids is not None:
                update_piece_tracking(
                    corners,
                    ids,
                    grid,
                    piece_last_cell,
                    piece_streak,
                    move_log,
                    PIECE_CELL_STABLE_FRAMES,
                    piece_off_fwd,
                    piece_off_side,
                    piece_cell_mult,
                )
                draw_piece_labels(
                    frame,
                    grid,
                    corners,
                    ids,
                    piece_off_fwd,
                    piece_off_side,
                    piece_cell_mult,
                )

        cv2.putText(frame, f"Detected: {detected_count}", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.putText(frame, f"Rejected: {rejected_count}", (20, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        snap_txt = f"LINE SNAP: {'ON' if line_snap_enabled else 'OFF'} (G) r={args.snap_radius}"
        cv2.putText(
            frame,
            snap_txt,
            (20, 125),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (180, 255, 200),
            1,
        )

        draw_offset_hud(frame, corner_state, offset_edit_index, nudge_step)
        if piece_track_enabled:
            draw_piece_calibration_hud(
                frame, piece_off_fwd, piece_off_side, piece_cell_mult, nudge_step
            )

        phase = phase_list[phase_index]
        tracked_n = len(piece_last_cell) if piece_track_enabled else 0
        canvas = draw_status_panel(
            frame,
            current_player=current_player,
            round_num=round_num,
            phase=phase,
            move_log=move_log if piece_track_enabled else [],
            tracked_piece_count=tracked_n,
        )

        current_time = time.time()
        if current_time - last_print_time >= print_interval:
            print("=" * 50)
            print(f"Detected count: {detected_count}")
            print(f"Rejected count: {rejected_count}")
            if board_points is not None:
                print("Board corners:", board_points)
            last_print_time = current_time

        cv2.imshow("Xiangqi Arena - Digital Board", canvas)

        if stable_board_on:
            stable_img = sbv.render_stable_board_frame(
                static_raster,
                node_xy_fn,
                board_ok=board_points is not None,
                grid=grid,
                corners=corners,
                ids=ids,
                piece_off_fwd=piece_off_fwd,
                piece_off_side=piece_off_side,
                piece_cell_mult=piece_cell_mult,
                cell_px=args.stable_cell_px,
                move_log=move_log if piece_track_enabled else [],
            )
            sbv.append_moves_jsonl(stable_log_path, move_log, stable_log_flush_idx)
            stable_log_flush_idx = len(move_log)
            cv2.imshow(win_stable, stable_img)

        key = cv2.waitKeyEx(1) if hasattr(cv2, "waitKeyEx") else cv2.waitKey(1)
        if key == -1:
            key8 = -1
        else:
            key8 = key & 0xFF

        offset_edit_index, nudge_step, _ = handle_offset_keys(
            key, key8, corner_state, offset_edit_index, nudge_step
        )

        if key8 in (ord("g"), ord("G")):
            line_snap_enabled = not line_snap_enabled
        elif key8 == ord(",") and line_snap_enabled:
            args.snap_radius = max(5, args.snap_radius - 2)
        elif key8 == ord(".") and line_snap_enabled:
            args.snap_radius = min(80, args.snap_radius + 2)
        elif key8 in (ord("c"), ord("C")):
            move_log.clear()
            stable_log_flush_idx = 0
            print("[INFO] move log cleared")
        elif piece_track_enabled and key8 in (ord("i"), ord("I")):
            piece_off_fwd -= nudge_step
        elif piece_track_enabled and key8 in (ord("k"), ord("K")):
            piece_off_fwd += nudge_step
        elif piece_track_enabled and key8 in (ord("j"), ord("J")):
            piece_off_side -= nudge_step
        elif piece_track_enabled and key8 in (ord("l"), ord("L")):
            piece_off_side += nudge_step
        elif piece_track_enabled and key8 in (ord("z"), ord("Z")):
            piece_cell_mult = max(0.35, round(piece_cell_mult - 0.05, 2))
        elif piece_track_enabled and key8 in (ord("x"), ord("X")):
            piece_cell_mult = min(1.25, round(piece_cell_mult + 0.05, 2))
        elif piece_track_enabled and key8 in (ord("t"), ord("T")):
            print(
                "\n# 棋子落点校准（可写入启动参数）：\n"
                f"  --piece-off-fwd {piece_off_fwd} --piece-off-side {piece_off_side} "
                f"--piece-cell-mult {piece_cell_mult}\n"
            )

        # ESC 退出
        if key8 == 27 or key == 27:
            break

        # Enter 切阶段，模拟你们说明书里的阶段式流程
        if key8 == 13:
            phase_index += 1
            if phase_index >= len(phase_list):
                phase_index = 0
                if current_player == "RED":
                    current_player = "BLACK"
                else:
                    current_player = "RED"
                    round_num += 1

    if stable_board_on:
        sbv.append_moves_jsonl(stable_log_path, move_log, stable_log_flush_idx)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()