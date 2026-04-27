import cv2
import numpy as np

# =========================
# 1. ArUco 配置
# =========================
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

# =========================
# 2. 打开摄像头
# =========================
cap = cv2.VideoCapture(0)   # 外接摄像头不对就改 1 或 2

if not cap.isOpened():
    print("无法打开摄像头")
    exit()

# =========================
# 3. 透视后输出大小
# =========================
WARP_WIDTH = 900
WARP_HEIGHT = 1000

# =========================
# 4. 如果 marker 和棋盘之间还有一点距离，可微调这个值
# （先设为0，后面再调）
# =========================
INNER_OFFSET = 5

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
            pts = corners[i][0]   # 4个角点，顺序通常是: 左上, 右上, 右下, 左下

            marker_corners[marker_id] = pts

            # 画4个角点（调试用）
            for j, pt in enumerate(pts):
                x, y = int(pt[0]), int(pt[1])
                cv2.circle(display, (x, y), 4, (0, 255, 255), -1)
                cv2.putText(display, f"{j}", (x + 5, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            # 中心点
            center_x = int(np.mean(pts[:, 0]))
            center_y = int(np.mean(pts[:, 1]))

            cv2.circle(display, (center_x, center_y), 5, (0, 0, 255), -1)
            cv2.putText(
                display,
                f"ID:{marker_id}",
                (center_x - 20, center_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

    required_ids = [0, 1, 2, 3]

    if all(mid in marker_corners for mid in required_ids):
        # =========================
        # 5. 取每个 marker 最靠近棋盘的“内侧角”
        # OpenCV角点顺序一般是：
        # 0 = 左上, 1 = 右上, 2 = 右下, 3 = 左下
        # =========================

        # ID 0 在左上 -> 棋盘方向是它的右下角 (index=2)
        board_tl = marker_corners[0][2] + np.array([INNER_OFFSET, INNER_OFFSET], dtype=np.float32)

        # ID 1 在右上 -> 棋盘方向是它的左下角 (index=3)
        board_tr = marker_corners[1][3] + np.array([-INNER_OFFSET, INNER_OFFSET], dtype=np.float32)

        # ID 2 在右下 -> 棋盘方向是它的左上角 (index=0)
        board_br = marker_corners[2][0] + np.array([-INNER_OFFSET, -INNER_OFFSET], dtype=np.float32)

        # ID 3 在左下 -> 棋盘方向是它的右上角 (index=1)
        board_bl = marker_corners[3][1] + np.array([INNER_OFFSET, -INNER_OFFSET], dtype=np.float32)

        src_pts = np.array([board_tl, board_tr, board_br, board_bl], dtype=np.float32)

        # =========================
        # 6. 画估计出来的棋盘四角
        # =========================
        for pt in src_pts:
            cv2.circle(display, tuple(pt.astype(int)), 8, (255, 0, 0), -1)

        cv2.polylines(display, [src_pts.astype(int)], isClosed=True, color=(255, 0, 255), thickness=2)

        # =========================
        # 7. 目标平面四角
        # =========================
        dst_pts = np.array([
            [0, 0],
            [WARP_WIDTH - 1, 0],
            [WARP_WIDTH - 1, WARP_HEIGHT - 1],
            [0, WARP_HEIGHT - 1]
        ], dtype=np.float32)

        # =========================
        # 8. 透视变换
        # =========================
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(frame, M, (WARP_WIDTH, WARP_HEIGHT))

        cv2.rectangle(warped, (0, 0), (WARP_WIDTH - 1, WARP_HEIGHT - 1), (0, 255, 0), 2)

        cv2.imshow("Warped Xiangqi Board", warped)

    cv2.imshow("Original View", display)

    key = cv2.waitKey(1)
    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()