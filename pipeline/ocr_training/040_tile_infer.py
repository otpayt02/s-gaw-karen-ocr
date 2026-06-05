import json, os
from ultralytics import YOLO
from PIL import Image

MODEL_PATH = "/workspace/runs/karen_ocr_v5/weights/best.pt"
TEST_IMAGE = "/root/karenlangtrans/test_paragraph.png"
INDEX_MAP  = "/root/karen_lang_trans/karen_index_map.json"
OUT_JSON   = "/root/karenlangtrans/040_tile_result.json"
TILE_SIZE  = 640
OVERLAP    = 80
CONF       = 0.25
IOU        = 0.4
TILE_TMP   = "/tmp/karen_tile_tmp.png"

with open(INDEX_MAP) as f: index_map = json.load(f)
model = YOLO(MODEL_PATH)
img   = Image.open(TEST_IMAGE).convert("RGB")
W, H  = img.size
step  = TILE_SIZE - OVERLAP

all_detections = []
for y in range(0, H, step):
    for x in range(0, W, step):
        x2, y2 = min(x + TILE_SIZE, W), min(y + TILE_SIZE, H)
        tile = img.crop((x, y, x2, y2))
        tile.save(TILE_TMP)
        results = model(TILE_TMP, conf=CONF, iou=IOU, verbose=False)
        for r in results:
            for i in range(len(r.boxes)):
                cls_idx  = int(r.boxes.cls[i].item())
                conf_val = float(r.boxes.conf[i].item())
                bx1, by1, bx2, by2 = r.boxes.xyxy[i].tolist()
                syllable = index_map.get(str(cls_idx), str(cls_idx))
                all_detections.append({
                    "syllable": syllable, "class_idx": cls_idx,
                    "conf": round(conf_val, 4),
                    "x1": int(bx1)+x, "y1": int(by1)+y,
                    "x2": int(bx2)+x, "y2": int(by2)+y
                })

def iou_score(a, b):
    ix1 = max(a["x1"], b["x1"]); iy1 = max(a["y1"], b["y1"])
    ix2 = min(a["x2"], b["x2"]); iy2 = min(a["y2"], b["y2"])
    inter = max(0, ix2-ix1) * max(0, iy2-iy1)
    ua = (a["x2"]-a["x1"])*(a["y2"]-a["y1"])
    ub = (b["x2"]-b["x1"])*(b["y2"]-b["y1"])
    return inter / (ua + ub - inter + 1e-6)

all_detections.sort(key=lambda d: -d["conf"])
kept = []
for det in all_detections:
    if all(iou_score(det, k) < 0.4 for k in kept):
        kept.append(det)

kept.sort(key=lambda d: (d["y1"] // 50, d["x1"]))
print(f"\n[040] Total after NMS: {len(kept)} syllables\n[040] Reading order:")
row, line = -1, ""
for d in kept:
    r = d["y1"] // 50
    if r != row:
        if line: print(f"       {line}")
        line = ""; row = r
    line += d["syllable"] + " "
if line: print(f"       {line}")

with open(OUT_JSON, "w") as f:
    json.dump({"total": len(kept), "detections": kept}, f, indent=2)
print(f"\n[040] Saved to {OUT_JSON}")