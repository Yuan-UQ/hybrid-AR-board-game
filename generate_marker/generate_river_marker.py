import cv2
import os

# 当前脚本所在目录
base_dir = os.path.dirname(os.path.abspath(__file__))

# 项目里的 markers 文件夹
output_dir = os.path.join(base_dir, "..", "markers")
os.makedirs(output_dir, exist_ok=True)

# 使用和 detect_marker.py 一样的字典
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

# 河道辅助 marker：固定为 4 和 5
river_markers = {
    4: "river_left.png",
    5: "river_right.png",
}

for marker_id, filename in river_markers.items():
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 600)
    save_path = os.path.join(output_dir, filename)
    cv2.imwrite(save_path, marker_img)
    print(f"Saved {save_path} (ID={marker_id})")

print("River markers 4 and 5 generated.")