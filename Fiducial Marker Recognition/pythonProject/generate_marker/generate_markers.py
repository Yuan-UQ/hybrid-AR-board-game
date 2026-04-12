import cv2
import os

# 创建文件夹（如果不存在）
os.makedirs("../markers", exist_ok=True)

# 使用你项目统一的字典
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

# 生成14个marker（0~13）
for marker_id in range(14):
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 300)

    filename = f"markers/marker_{marker_id}.png"
    cv2.imwrite(filename, marker_img)

    print(f"Saved {filename}")

print("All markers generated.")