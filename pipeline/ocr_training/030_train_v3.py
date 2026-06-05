import os
from ultralytics import YOLO

V2_BEST   = "/workspace/runs/karen_ocr_v2_boosted/weights/best.pt"
DATA_YAML = "/root/karen_dataset_yolov8/data.yaml"

if not os.path.exists(V2_BEST):
    print(f"[030] ERROR: {V2_BEST} not found."); exit(1)

print(f"[030] Starting v3 fine-tune from {V2_BEST}")
model = YOLO(V2_BEST)

model.train(
    data=DATA_YAML,
    epochs=30,
    imgsz=320,
    batch=16,
    lr0=0.0005,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=2,
    optimizer="SGD",
    half=True,
    project="/workspace/runs",
    name="karen_ocr_v3",
    exist_ok=True,
    patience=15,
    workers=4,
    cache=False,
)

print("[030] v3 training complete.")
print("[030] Best weights: /workspace/runs/karen_ocr_v3/weights/best.pt")
print("[030] NEXT: run 027 and 028 again pointing at karen_ocr_v3 to measure final gap.")