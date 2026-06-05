import os
from ultralytics import YOLO

V4_BEST   = "/workspace/runs/karen_ocr_v4/weights/best.pt"
DATA_YAML = "/root/karen_dataset_yolov8/data.yaml"

if not os.path.exists(V4_BEST):
    print(f"[036] ERROR: {V4_BEST} not found."); exit(1)

print("[036] Starting v5 fine-tune from v4 best.pt...")
model = YOLO(V4_BEST)
model.train(
    data=DATA_YAML,
    epochs=20,
    imgsz=320,
    batch=16,
    lr0=0.0001,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=1,
    optimizer="SGD",
    half=True,
    project="/workspace/runs",
    name="karen_ocr_v5",
    exist_ok=True,
    patience=10,
    workers=4,
    cache=False,
)
print("[036] v5 training complete.")
print("[036] Best weights: /workspace/runs/karen_ocr_v5/weights/best.pt")
print("[036] NEXT: run 027 + 032 pointing at karen_ocr_v5")