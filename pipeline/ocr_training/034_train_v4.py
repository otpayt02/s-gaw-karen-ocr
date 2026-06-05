import os
from ultralytics import YOLO

V3_BEST   = "/workspace/runs/karen_ocr_v3/weights/best.pt"
DATA_YAML = "/root/karen_dataset_yolov8/data.yaml"

if not os.path.exists(V3_BEST):
    print(f"[034] ERROR: {V3_BEST} not found."); exit(1)

print(f"[034] Starting v4 fine-tune from v3 best.pt...")
model = YOLO(V3_BEST)

model.train(
    data=DATA_YAML,
    epochs=20,
    imgsz=320,
    batch=16,
    lr0=0.0002,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=1,
    optimizer="SGD",
    half=True,
    project="/workspace/runs",
    name="karen_ocr_v4",
    exist_ok=True,
    patience=10,
    workers=4,
    cache=False,
)

print("[034] v4 training complete.")
print("[034] Best weights: /workspace/runs/karen_ocr_v4/weights/best.pt")
print("[034] NEXT: run 027 + 032 pointing at karen_ocr_v4")