import os, json
from ultralytics import YOLO

MODEL_PATH  = "/workspace/runs/karen_ocr_v2_boosted/weights/best.pt"
DATA_YAML   = "/root/karen_dataset_yolov8/data.yaml"
OUTPUT_JSON = "/root/karenlangtrans/027_v2_val_results.json"

if not os.path.exists(MODEL_PATH):
    print(f"[027] ERROR: model not found at {MODEL_PATH}"); exit(1)

print("[027] Loading v2 model...")
model = YOLO(MODEL_PATH)
print("[027] Running validation...")
results = model.val(data=DATA_YAML, imgsz=320, conf=0.001, iou=0.6, save_json=True, verbose=False)

per_class = []
for i in range(len(results.box.p)):
    per_class.append({"class_idx": i, "precision": float(results.box.p[i]), "recall": float(results.box.r[i]), "mAP50": float(results.box.ap50[i]), "mAP5095": float(results.box.ap[i])})

output = {"model": MODEL_PATH, "summary": {"overall_mAP50": float(results.box.map50), "overall_mAP5095": float(results.box.map), "overall_precision": float(results.box.mp), "overall_recall": float(results.box.mr), "num_classes": len(per_class)}, "per_class": per_class}

with open(OUTPUT_JSON, "w") as f:
    json.dump(output, f, indent=2)

s = output["summary"]
print(f"[027] overall mAP50:   {s['overall_mAP50']:.4f}")
print(f"[027] overall Recall:  {s['overall_recall']:.4f}")
print(f"[027] Saved to {OUTPUT_JSON}")
print("[027] NEXT: python3 /root/karenlangtrans/028_analyze_v2_gaps.py")