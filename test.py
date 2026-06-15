from ultralytics import YOLO
import cv2

# 加载模型
model = YOLO("fire.pt")

# 检测图片
results = model("image.png", conf=0.1)

# 保存结果
results[0].save("result.jpg")  # 保存到文件

# 打印检测结果
for box in results[0].boxes:
    cls = results[0].names[int(box.cls[0])]
    conf = float(box.conf[0])
    print(f"{cls}: {conf:.2f}")