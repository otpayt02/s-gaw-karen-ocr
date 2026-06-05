import json, os, random
from PIL import Image, ImageDraw, ImageFont

GAP_REPORT  = "/root/karenlangtrans/028_v2_gap_report.json"
INDEX_MAP   = "/root/karenlangtrans/karen_index_map.json"
DATA_YAML   = "/root/karen_dataset_yolov8/data.yaml"
TRAIN_IMG   = "/root/karen_dataset_yolov8/train/images"
TRAIN_LBL   = "/root/karen_dataset_yolov8/train/labels"
FONT_PATH   = "/root/karenlangtrans/padauk-regular.ttf"
IMAGES_PER_CLASS = 300

with open(GAP_REPORT) as f: report = json.load(f)
with open(INDEX_MAP) as f:  index_map = json.load(f)

missed_indices = [e["class_idx"] for e in report["missed_classes"]]
print(f"[029] Generating {IMAGES_PER_CLASS} booster images for {len(missed_indices)} missed classes...")

os.makedirs(TRAIN_IMG, exist_ok=True)
os.makedirs(TRAIN_LBL, exist_ok=True)

generated = 0
for class_idx in missed_indices:
    syllable = index_map.get(str(class_idx), str(class_idx))
    try:
        font = ImageFont.truetype(FONT_PATH, random.randint(32, 72))
    except:
        font = ImageFont.load_default()

    for i in range(IMAGES_PER_CLASS):
        img_size = 320
        bg = random.randint(200, 255)
        img = Image.new("RGB", (img_size, img_size), (bg, bg, bg))
        draw = ImageDraw.Draw(img)

        x = random.randint(40, 200)
        y = random.randint(40, 200)
        fg = random.randint(0, 80)
        draw.text((x, y), syllable, font=font, fill=(fg, fg, fg))

        bbox = draw.textbbox((x, y), syllable, font=font)
        bw = bbox[2] - bbox[0]
        bh = bbox[3] - bbox[1]
        cx = (bbox[0] + bbox[2]) / 2 / img_size
        cy = (bbox[1] + bbox[3]) / 2 / img_size
        nw = bw / img_size
        nh = bh / img_size

        fname = f"v3boost_{class_idx}_{i:04d}"
        img.save(os.path.join(TRAIN_IMG, fname + ".jpg"))
        with open(os.path.join(TRAIN_LBL, fname + ".txt"), "w") as lf:
            lf.write(f"{class_idx} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")
        generated += 1

print(f"[029] Done. {generated} booster images written to {TRAIN_IMG}")
print("[029] NEXT: python3 /root/karenlangtrans/030_train_v3.py")