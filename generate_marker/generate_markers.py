import cv2
import os

# 当前脚本所在目录
base_dir = os.path.dirname(os.path.abspath(__file__))

# 项目里的 markers 文件夹（和 detect_marker.py 同级）
output_dir = os.path.join(base_dir, "..", "markers")
os.makedirs(output_dir, exist_ok=True)

# 使用统一字典
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

# 按游戏规则文件定义的 14 枚棋子命名，ID 使用 10~23，避免和棋盘角 marker 冲突
PIECE_IDS = {
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

for marker_id, piece_name in PIECE_IDS.items():
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 300)

    save_path = os.path.join(output_dir, f"{piece_name}.png")
    cv2.imwrite(save_path, marker_img)

    print(f"Saved {save_path} (ID={marker_id})")

print("All 14 Xiangqi Arena piece markers generated.")