import cv2
import numpy as np
import time
import argparse

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
    "RED_LEFT": (55, -40),
    "RED_RIGHT": (-55, -40),
    "BLACK_LEFT": (55, 40),
    "BLACK_RIGHT": (-55, 40),
}

# =========================
# 2. 几何工具函数
# =========================

def get_board_points_from_semantic_corners(detected_markers):
    """
    按游戏规则固定数字棋盘方向：
    y = 0 在红方一侧
    y = 9 在黑方一侧

    所以：
    TL = RED_LEFT
    TR = RED_RIGHT
    BR = BLACK_RIGHT
    BL = BLACK_LEFT

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

    red_left = apply_offset(red_left_raw, BOARD_CORNER_OFFSETS["RED_LEFT"])
    red_right = apply_offset(red_right_raw, BOARD_CORNER_OFFSETS["RED_RIGHT"])
    black_left = apply_offset(black_left_raw, BOARD_CORNER_OFFSETS["BLACK_LEFT"])
    black_right = apply_offset(black_right_raw, BOARD_CORNER_OFFSETS["BLACK_RIGHT"])

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
# 4. 右侧状态面板
# =========================

def draw_status_panel(frame, current_player="RED", round_num=1, phase="MOVE"):
    h, w = frame.shape[:2]
    panel_w = 260

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
    put("ENTER: next phase", (180, 180, 180), 0.55, 25)
    put("ESC: quit", (180, 180, 180), 0.55, 25)

    return canvas


# =========================
# 5. 主程序
# =========================

def main():
    parser = argparse.ArgumentParser(description="Detect ArUco markers and draw Xiangqi digital board.")
    parser.add_argument("--source", default="1", help="Camera index or stream URL")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()

    source = int(args.source) if str(args.source).isdigit() else args.source

    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        print(f"Error: cannot open video source: {args.source}")
        return

    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    last_print_time = 0
    print_interval = 0.5

    current_player = "RED"
    round_num = 1
    phase_list = ["START", "MOVE", "SCAN", "ATTACK", "END"]
    phase_index = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: failed to read frame")
            break

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

                # 高亮用于棋盘映射的实际点
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

        # 四角齐全 -> 生成数字棋盘
        # 四角齐全 -> 生成数字棋盘
        # 根据棋盘语义角，生成逻辑棋盘四角
        board_points = get_board_points_from_semantic_corners(detected_markers)

        # 四角齐全 -> 生成数字棋盘
        if board_points is not None:
            draw_final_board_corners(frame, board_points)  # 先显示最终四角
            grid = compute_board_grid(board_points)
            draw_board_overlay(frame, grid)
            cv2.putText(
                frame,
                "Board detected",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )


        cv2.putText(frame, f"Detected: {detected_count}", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.putText(frame, f"Rejected: {rejected_count}", (20, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        phase = phase_list[phase_index]
        canvas = draw_status_panel(frame, current_player=current_player, round_num=round_num, phase=phase)

        current_time = time.time()
        if current_time - last_print_time >= print_interval:
            print("=" * 50)
            print(f"Detected count: {detected_count}")
            print(f"Rejected count: {rejected_count}")
            if board_points is not None:
                print("Board corners:", board_points)
            last_print_time = current_time

        cv2.imshow("Xiangqi Arena - Digital Board", canvas)

        key = cv2.waitKey(1) & 0xFF

        # ESC 退出
        if key == 27:
            break

        # Enter 切阶段，模拟你们说明书里的阶段式流程
        if key == 13:
            phase_index += 1
            if phase_index >= len(phase_list):
                phase_index = 0
                if current_player == "RED":
                    current_player = "BLACK"
                else:
                    current_player = "RED"
                    round_num += 1

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()