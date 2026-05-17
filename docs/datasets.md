# 施工安全检测 — 开源数据集下载汇总

---

## 一、施工安全主数据集（基础 11 类）

### 1. Construction Site Safety (Roboflow v28) ⭐推荐
- **图片数**: 2,801
- **类别**: Hardhat, Mask, NO-Hardhat, NO-Mask, NO-Safety Vest, Person, Safety Cone, Safety Vest, machinery, vehicle
- **格式**: 支持 YOLOv11 / YOLOv8 / COCO / Pascal VOC
- **许可证**: CC BY 4.0

| 平台 | 链接 |
|------|------|
| Roboflow | https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety |
| Kaggle | https://www.kaggle.com/datasets/snehilsanyal/construction-site-safety-image-dataset-roboflow |
| HuggingFace | https://huggingface.co/datasets/keremberke/construction-safety-object-detection |

### 2. SHWD — Safety Helmet Wearing Dataset
- **图片数**: 7,581
- **类别**: hat, person
- **格式**: Pascal VOC

| 来源 | 链接 |
|------|------|
| GitHub | https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset |
| Google Drive | https://drive.google.com/open?id=1qWm7rrwvjAWs1slymbrLaCf7Q-wnGLEX |
| 百度网盘 | https://pan.baidu.com/s/1UbFkGm4EppdAU660Vu7SdQ |

### 3. Construction Site Safety v27（扩展 25 类）
- **图片数**: 717
- **类别**: Hardhat, Mask, NO-Hardhat, NO-Mask, NO-Safety Vest, Person, Safety Cone, Safety Vest, machinery, vehicle, Ladder, Gloves, Excavator, Dump Truck, truck, bus, sedan, trailer, mini-van, SUV, wheel loader, semi, dumpster, barricade, fire hydrant
- **Roboflow**: https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety/dataset/27

---

## 二、明火 & 烟雾检测

### 4. FireAndSmokeDataset (Kaggle) ⭐推荐
- **图片数**: 35,000+
- **类别**: Fire, Smoke
- **格式**: YOLO
- **许可证**: CC BY-SA 4.0
- **Kaggle**: https://www.kaggle.com/datasets/roscoekerby/firesmoke-detection-yolo-v9

### 5. Fire-Smoke-Detection-YOLOv11 (Roboflow)
- **类别**: Fire, Smoke
- **格式**: 支持 YOLOv11 直接下载
- **Roboflow**: https://universe.roboflow.com/sayed-gamall/fire-smoke-detection-yolov11

### 6. NEWFireSmokeDataset (GitHub)
- **类别**: Fire, Smoke, Other
- **许可证**: 开源
- **GitHub**: https://github.com/CostiCatargiu/NEWFireSmokeDataset_YoloModels

### 7. Fire Dataset for YOLOv8 (Roboflow)
- **图片数**: 约 1,500
- **类别**: Fire
- **场景**: 室内火灾检测
- **Roboflow**: https://universe.roboflow.com/aj-garcia-736tc/fire-dataset-for-yolov8

### 8. Fire and Smoke (HuggingFace) — 预训练模型
- **说明**: YOLOv10 预训练模型（Fire + Smoke）
- **HuggingFace**: https://huggingface.co/TommyNgx/YOLOv10-Fire-and-Smoke-Detection

### 9. Fire & Smoke (Roboflow)
- **图片数**: 1,950
- **Roboflow**: https://universe.roboflow.com/browse/fire

---

## 三、人员摔倒检测

### 10. Fall Detection (Roboflow) ⭐推荐
- **图片数**: 4,497
- **类别**: Fall-Detected
- **格式**: 支持 YOLOv11 / YOLOv8 / YOLOv5 / COCO
- **Roboflow**: https://universe.roboflow.com/roboflow-universe-projects/fall-detection-ca3o8

### 11. Fallen Person v2 ⭐推荐
- **图片数**: 2,876
- **类别**: Fallen Person
- **Roboflow**: https://universe.roboflow.com/fallen-people-data-set/fallen-person-uhif8/dataset/2

### 12. Falling Person Detection
- **图片数**: 474
- **Roboflow**: https://universe.roboflow.com/siriusai/falling-person-detection

---

## 四、人员打斗/暴力检测

### 13. Fight dataset (Roboflow) ⭐推荐
- **图片数**: 3,806
- **类别**: Fight.-hit-punch-
- **Roboflow**: https://universe.roboflow.com/suspicious-activity-detector/fight-dataset

### 14. Violence Detection (Roboflow)
- **图片数**: 6,160
- **类别**: violence, non_violence
- **Roboflow**: https://universe.roboflow.com/securityviolence/violence-detection-p4qev

### 15. Real Life Violence Situations Dataset
- **数量**: 2,000 个视频（1,000 暴力 + 1,000 非暴力）
- **格式**: 视频分类
- **Kaggle**: https://www.kaggle.com/datasets/mohamedmustafa/real-life-violence-situations-dataset

### 16. Violence Detection (YOLOv11 — GitHub)
- **说明**: 完整 YOLOv11 + Roboflow 训练方案
- **GitHub**: https://github.com/sharavak/violence_detection

---

## 五、快速下载脚本（Roboflow 格式）

```python
from roboflow import Roboflow

rf = Roboflow(api_key="YOUR_ROBOFLOW_API_KEY")

# 施工安全 v28（10 类，2,801 张）
project = rf.workspace("roboflow-universe-projects").project("construction-site-safety")
dataset = project.version(28).download("yolov11")

# 明火烟雾检测
project = rf.workspace("sayed-gamall").project("fire-smoke-detection-yolov11")
dataset = project.version(2).download("yolov11")

# 摔倒检测
project = rf.workspace("roboflow-universe-projects").project("fall-detection-ca3o8")
dataset = project.version(4).download("yolov11")

# 打斗检测
project = rf.workspace("suspicious-activity-detector").project("fight-dataset")
dataset = project.version(1).download("yolov11")
```
