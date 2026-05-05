import cv2
import numpy as np

# =========================
# 1. ArUco 配置
# =========================
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

# =========================
# 2. 摄像头
# =========================
cap = cv2.VideoCapture(0)   # 外接摄像头不对就改 1 或 2

if not cap.isOpened():
    print("无法打开摄像头")
    exit()

# =========================
# 3. 参数
# =========================
WARP_WIDTH = 900
WARP_HEIGHT = 1000
INNER_OFFSET = 0
# 透视前对四边形做等比扩展，>0 会看到更多棋盘边缘
QUAD_EXPAND_RATIO = 0.08
AUTO_SNAP_TO_LINES = True
SNAP_SEARCH_RADIUS = 22

# =========================
# 4. 生成中国象棋 10x9 交叉点
# =========================
def generate_grid_points(width, height, margin=0):
    points = []
    for row in range(10):
        row_points = []
        y = margin + row * (height - 2 * margin - 1) / 9
        for col in range(9):
            x = margin + col * (width - 2 * margin - 1) / 8
            row_points.append((int(x), int(y)))
        points.append(row_points)
    return points


def expand_quad(quad, ratio):
    center = np.mean(quad, axis=0, keepdims=True)
    return center + (quad - center) * (1.0 + ratio)


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
        local = scores[left:right + 1]
        best = int(np.argmax(local)) + left
        refined.append(best)
    return refined


def snap_grid_to_board_lines(warped, grid_points, search_radius):
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
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

    expected_x = [grid_points[0][col][0] for col in range(9)]
    expected_y = [grid_points[row][0][1] for row in range(10)]

    refined_x = refine_axis_positions(col_scores, expected_x, search_radius)
    refined_y = refine_axis_positions(row_scores, expected_y, search_radius)

    refined_points = []
    for row in range(10):
        row_points = []
        for col in range(9):
            row_points.append((int(refined_x[col]), int(refined_y[row])))
        refined_points.append(row_points)
    return refined_points

while True:
    ret, frame = cap.read()
    if not ret:
        print("无法读取摄像头画面")
        break

    display = frame.copy()
    corners, ids, rejected = detector.detectMarkers(frame)

    marker_corners = {}

    if ids is not None:
        cv2.aruco.drawDetectedMarkers(display, corners, ids)

        for i in range(len(ids)):
            marker_id = int(ids[i][0])
            pts = corners[i][0]
            marker_corners[marker_id] = pts

            center_x = int(np.mean(pts[:, 0]))
            center_y = int(np.mean(pts[:, 1]))

            cv2.circle(display, (center_x, center_y), 5, (0, 0, 255), -1)
            cv2.putText(display, f"ID:{marker_id}", (center_x - 20, center_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    required_ids = [0, 1, 2, 3]

    if all(mid in marker_corners for mid in required_ids):
        # 用每个 marker 靠近棋盘的内侧角
        board_tl = marker_corners[0][2] + np.array([INNER_OFFSET, INNER_OFFSET], dtype=np.float32)
        board_tr = marker_corners[1][3] + np.array([-INNER_OFFSET, INNER_OFFSET], dtype=np.float32)
        board_br = marker_corners[2][0] + np.array([-INNER_OFFSET, -INNER_OFFSET], dtype=np.float32)
        board_bl = marker_corners[3][1] + np.array([INNER_OFFSET, -INNER_OFFSET], dtype=np.float32)

        src_pts = np.array([board_tl, board_tr, board_br, board_bl], dtype=np.float32)
        src_pts = expand_quad(src_pts, QUAD_EXPAND_RATIO).astype(np.float32)

        for pt in src_pts:
            cv2.circle(display, tuple(pt.astype(int)), 8, (255, 0, 0), -1)

        cv2.polylines(display, [src_pts.astype(int)], isClosed=True, color=(255, 0, 255), thickness=2)

        dst_pts = np.array([
            [0, 0],
            [WARP_WIDTH - 1, 0],
            [WARP_WIDTH - 1, WARP_HEIGHT - 1],
            [0, WARP_HEIGHT - 1]
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(frame, M, (WARP_WIDTH, WARP_HEIGHT))

        # 生成交叉点（先等分，再可选吸附到真实棋盘线）
        grid_points = generate_grid_points(WARP_WIDTH, WARP_HEIGHT, margin=0)
        if AUTO_SNAP_TO_LINES:
            grid_points = snap_grid_to_board_lines(warped, grid_points, SNAP_SEARCH_RADIUS)

        # 空数字棋盘
        board_state = [[None for _ in range(9)] for _ in range(10)]

        # 画交叉点
        for row in range(10):
            for col in range(9):
                x, y = grid_points[row][col]
                cv2.circle(warped, (x, y), 5, (0, 0, 255), -1)
                cv2.putText(
                    warped,
                    f"{row},{col}",
                    (x + 5, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (255, 0, 0),
                    1
                )

        cv2.imshow("Warped Xiangqi Board", warped)

    cv2.putText(
        display,
        f"INNER_OFFSET:{INNER_OFFSET}  EXPAND:{QUAD_EXPAND_RATIO:.2f}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2
    )
    cv2.putText(
        display,
        f"SNAP:{AUTO_SNAP_TO_LINES}  RADIUS:{SNAP_SEARCH_RADIUS}",
        (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2
    )

    cv2.imshow("Original View", display)

    key = cv2.waitKey(1)
    if key == ord('['):
        INNER_OFFSET -= 1
    elif key == ord(']'):
        INNER_OFFSET += 1
    elif key == ord('-'):
        QUAD_EXPAND_RATIO = max(0.0, QUAD_EXPAND_RATIO - 0.01)
    elif key == ord('='):
        QUAD_EXPAND_RATIO += 0.01
    elif key == ord('s'):
        AUTO_SNAP_TO_LINES = not AUTO_SNAP_TO_LINES
    elif key == ord(','):
        SNAP_SEARCH_RADIUS = max(5, SNAP_SEARCH_RADIUS - 1)
    elif key == ord('.'):
        SNAP_SEARCH_RADIUS += 1
    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()

# s：开/关自动吸附（对比效果）
# , / .：减小 / 增大吸附搜索半径 SNAP_SEARCH_RADIUS
# [ / ]：调 INNER_OFFSET
# - / =：调 QUAD_EXPAND_RATIO
# Esc：退出