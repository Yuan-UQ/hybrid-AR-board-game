import cv2
import numpy as np
import time
import argparse

# =========================
# 1. 配置区
# =========================

# 棋盘定位 marker ID
BOARD_MARKER_IDS = {
    "BLACK_LEFT": 0,
    "RED_RIGHT": 1,
    "RED_LEFT": 2,
    "BLACK_RIGHT": 3,
    "RIVER_LEFT": 4,
    "RIVER_RIGHT": 5,
}

# 逻辑棋盘坐标中的控制点
# 棋盘大小：9列 x 10行，坐标 x=0~8, y=0~9
MARKER_BOARD_COORDS = {
    "BLACK_LEFT":  (0.0, 9.0),   # 顶部黑方
    "BLACK_RIGHT": (8.0, 9.0),
    "RED_LEFT":    (0.0, 0.0),   # 底部红方
    "RED_RIGHT":   (8.0, 0.0),
    "RIVER_LEFT":  (0.0, 4.5),   # 河界在 y=4 和 y=5 之间
    "RIVER_RIGHT": (8.0, 4.5),
}

ARUCO_DICT = cv2.aruco.DICT_4X4_50

BOARD_COLS = 9
BOARD_ROWS = 10

ID_TO_NAME = {v: k for k, v in BOARD_MARKER_IDS.items()}

# =========================
# 2. 几何工具函数
# =========================

def fit_quadratic_mapping(logic_points, image_points):
    """
    拟合:
        x = a0 + a1*u + a2*v + a3*u*v + a4*u^2 + a5*v^2
        y = b0 + b1*u + b2*v + b3*u*v + b4*u^2 + b5*v^2
    """
    A = []
    bx = []
    by = []

    for (u, v), (x, y) in zip(logic_points, image_points):
        A.append([1, u, v, u * v, u * u, v * v])
        bx.append(x)
        by.append(y)

    A = np.array(A, dtype=np.float32)
    bx = np.array(bx, dtype=np.float32)
    by = np.array(by, dtype=np.float32)

    coef_x, _, _, _ = np.linalg.lstsq(A, bx, rcond=None)
    coef_y, _, _, _ = np.linalg.lstsq(A, by, rcond=None)

    return coef_x, coef_y


def map_logic_to_image(u, v, coef_x, coef_y):
    feat = np.array([1, u, v, u * v, u * u, v * v], dtype=np.float32)
    x = float(np.dot(coef_x, feat))
    y = float(np.dot(coef_y, feat))
    return (int(round(x)), int(round(y)))


def compute_board_grid_from_multi_markers(detected_markers):
    logic_points = []
    image_points = []

    for name, marker_id in BOARD_MARKER_IDS.items():
        if marker_id in detected_markers:
            logic_points.append(MARKER_BOARD_COORDS[name])
            image_points.append(detected_markers[marker_id]["board_point"])

    # 6个参数，至少6个点才稳定
    if len(logic_points) < 6:
        return None

    coef_x, coef_y = fit_quadratic_mapping(logic_points, image_points)

    grid = []
    for y in range(BOARD_ROWS):
        row = []
        for x in range(BOARD_COLS):
            row.append(map_logic_to_image(float(x), float(y), coef_x, coef_y))
        grid.append(row)

    return grid


def draw_polyline_by_board_coords(frame, grid, coords, color, thickness=2):
    pts = np.array([grid[y][x] for (x, y) in coords], dtype=np.int32)
    cv2.polylines(frame, [pts], isClosed=False, color=color, thickness=thickness)


def draw_closed_polygon_by_board_coords(frame, grid, coords, color, thickness=2):
    pts = np.array([grid[y][x] for (x, y) in coords], dtype=np.int32)
    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=thickness)


# =========================
# 3. 绘制数字棋盘
# =========================

def draw_board_overlay(frame, grid):
    # 横线
    for y in range(BOARD_ROWS):
        pts = np.array(grid[y], dtype=np.int32)
        cv2.polylines(frame, [pts], isClosed=False, color=(255, 255, 255), thickness=1)

    # 竖线
    for x in range(BOARD_COLS):
        col_pts = np.array([grid[y][x] for y in range(BOARD_ROWS)], dtype=np.int32)
        cv2.polylines(frame, [col_pts], isClosed=False, color=(255, 255, 255), thickness=1)

    # 交叉点 + 坐标
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

    # 河界线：y=4 和 y=5 中间
    river_pts = []
    for x in range(BOARD_COLS):
        p4 = np.array(grid[4][x], dtype=np.float32)
        p5 = np.array(grid[5][x], dtype=np.float32)
        mid = ((p4 + p5) / 2).astype(int)
        river_pts.append(tuple(mid))

    river_line = np.array(river_pts, dtype=np.int32)
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

    canvas = np.zeros((h, w + panel_w, 3), dtype=np.uint8)
    canvas[:, :w] = frame
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
                pts = corners[i][0]
                center = np.mean(pts, axis=0).astype(int)
                cx, cy = int(center[0]), int(center[1])

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

                if marker_id in ID_TO_NAME:
                    label = ID_TO_NAME[marker_id]
                    board_point = (cx, cy)   # 多点拟合阶段统一用中心点
                else:
                    label = f"ID:{marker_id}"
                    board_point = (cx, cy)

                detected_markers[marker_id] = {
                    "center": (cx, cy),
                    "pts": pts,
                    "board_point": board_point,
                    "label": label,
                }

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

        grid = compute_board_grid_from_multi_markers(detected_markers)

        if grid is not None:
            draw_board_overlay(frame, grid)
            cv2.putText(
                frame,
                "Board detected (6-point fit)",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )
        else:
            cv2.putText(
                frame,
                "Need 6 board markers (0,1,2,3,4,5)",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 100, 255),
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
            if grid is not None:
                print("Board grid fitted with 6 markers.")
            last_print_time = current_time

        cv2.imshow("Xiangqi Arena - Digital Board", canvas)

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            break

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