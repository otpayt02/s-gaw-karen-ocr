import os, json
from ultralytics import YOLO

MODEL_PATH  = "/workspace/runs/karen_ocr_v5/weights/best.pt"
TEST_IMAGE  = "/root/karenlangtrans/test_paragraph.png"
INDEX_MAP   = "/root/karen_lang_trans/karen_index_map.json"
OUT_JSON    = "/root/karenlangtrans/038_inference_result.json"

if not os.path.exists(MODEL_PATH):
    print(f"[038] ERROR: {MODEL_PATH} not found."); exit(1)
if not os.path.exists(TEST_IMAGE):
    print(f"[038] ERROR: {TEST_IMAGE} not found. Run 037 first."); exit(1)

with open(INDEX_MAP) as f: index_map = json.load(f)

print("[038] Loading v5 model...")
model = YOLO(MODEL_PATH)

print(f"[038] Running inference on {TEST_IMAGE} ...")
results = model(TEST_IMAGE, conf=0.25, iou=0.4, verbose=False)

detections = []
for r in results:
    boxes = r.boxes
    for i in range(len(boxes)):
        cls_idx = int(boxes.cls[i].item())
        conf    = float(boxes.conf[i].item())
        x1, y1, x2, y2 = boxes.xyxy[i].tolist()
        syllable = index_map.get(str(cls_idx), str(cls_idx))
        detections.append({
            "syllable":  syllable,
            "class_idx": cls_idx,
            "conf":      round(conf, 4),
            "x1": round(x1), "y1": round(y1),
            "x2": round(x2), "y2": round(y2),
        })

# Sort left→right, top→bottom to read like a page
detections.sort(key=lambda d: (d["y1"] // 60, d["x1"]))

print(f"\n[038] Detected {len(detections)} syllables\n")
print("[038] Reading order:")
current_row = -1
line_text = ""
for d in detections:
    row = d["y1"] // 60
    if row != current_row:
        if line_text: print(f"       {line_text}")
        line_text = ""
        current_row = row
    line_text += d["syllable"] + " "
if line_text: print(f"       {line_text}")

with open(OUT_JSON, "w") as f:
    json.dump({"total_detections": len(detections), "detections": detections}, f, indent=2)

print(f"\n[038] Full results saved to {OUT_JSON}")
print("[038] NEXT: download test_paragraph.png to see what the model was reading")
print(f'       scp -P 8998 root@146.115.17.156:/root/karenlangtrans/test_paragraph.png "C:\\Users\\olive\\Projects\\karen_lang_trans\\test_paragraph.png"')