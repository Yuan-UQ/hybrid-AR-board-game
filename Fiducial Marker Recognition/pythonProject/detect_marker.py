import cv2
import numpy as np
import time
import argparse


def main():
    parser = argparse.ArgumentParser(description="Detect ArUco markers from camera or network stream.")
    parser.add_argument(
        "--source",
        default="http://192.168.0.198:8080/video",
        help=(
            "Video source. Use camera index like 0/1, or a URL (e.g. "
            "http://<phone-ip>:8080/video for IP Webcam MJPEG)."
        ),
    )
    parser.add_argument("--width", type=int, default=1280, help="Requested capture width.")
    parser.add_argument("--height", type=int, default=720, help="Requested capture height.")
    args = parser.parse_args()

    source = int(args.source) if str(args.source).isdigit() else args.source

    # 打开摄像头/视频流
    cap = cv2.VideoCapture(source)

    # 可选：设置分辨率，画面清楚一点更利于识别
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        print(f"Error: cannot open video source: {args.source}")
        print("Tip: if using phone, ensure PC and phone are on the same LAN, and the URL is reachable.")
        return

    # 固定使用 DICT_6X6_250
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

    # 检测参数
    parameters = cv2.aruco.DetectorParameters()

    # 创建 detector
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    # 控制终端打印频率，避免每一帧刷屏太快
    last_print_time = 0
    print_interval = 0.5  # 每 0.5 秒打印一次

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: failed to read frame")
            break

        # 检测 marker
        corners, ids, rejected = detector.detectMarkers(frame)

        detected_count = 0 if ids is None else len(ids)
        rejected_count = 0 if rejected is None else len(rejected)

        # 如果检测到了 marker
        if ids is not None and len(ids) > 0:
            detected_count = len(ids)

            # 画出 marker 边框和 ID
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            # 遍历每个检测到的 marker
            for i, marker_id in enumerate(ids.flatten()):
                pts = corners[i][0]  # shape: (4, 2)
                center = np.mean(pts, axis=0).astype(int)
                cx, cy = center

                # 画中心点
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

                # 在画面上显示 ID 和中心点
                text = f"ID:{marker_id} ({cx},{cy})"
                cv2.putText(
                    frame,
                    text,
                    (cx + 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2
                )

        # 在画面左上角显示总体统计信息
        cv2.putText(
            frame,
            f"Detected: {detected_count}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"Rejected: {rejected_count}",
            (20, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2
        )

        cv2.putText(
            frame,
            "ESC to quit",
            (20, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (200, 200, 200),
            2
        )

        # 控制终端打印频率
        current_time = time.time()
        if current_time - last_print_time >= print_interval:
            print("=" * 50)
            print(f"Detected count: {detected_count}")
            print(f"Rejected count: {rejected_count}")

            if ids is not None and len(ids) > 0:
                for i, marker_id in enumerate(ids.flatten()):
                    pts = corners[i][0]
                    center = np.mean(pts, axis=0).astype(int)
                    cx, cy = center
                    print(f"Marker ID {marker_id}: center=({cx}, {cy})")

            last_print_time = current_time

        # 显示画面
        cv2.imshow("ArUco Detection - DICT_6X6_250", frame)

        # ESC 退出
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()