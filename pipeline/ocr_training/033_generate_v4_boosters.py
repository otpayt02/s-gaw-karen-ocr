import json, os, random
from PIL import Image, ImageDraw, ImageFont

GAP_REPORT       = "/root/karenlangtrans/032_true_gap_report.json"
INDEX_MAP        = "/root/karen_lang_trans/karen_index_map.json"
TRAIN_IMG        = "/root/karen_dataset_yolov8/train/images"
TRAIN_LBL        = "/root/karen_dataset_yolov8/train/labels"
VALID_IMG        = "/root/karen_dataset_yolov8/valid/images"
VALID_LBL        = "/root/karen_dataset_yolov8/valid/labels"
FONT_PATH        = "/root/karenlangtrans/padauk-regular.ttf"
TRAIN_PER_CLASS  = 500
VAL_PER_CLASS    = 50

with open(GAP_REPORT) as f: report = json.load(f)
with open(INDEX_MAP)  as f: index_map = json.load(f)

missed_indices = [e["class_idx"] for e in report["missed_classes"]]
print(f"[033] Targeting {len(missed_indices)} truly missed classes")
print(f"[033] {TRAIN_PER_CLASS} train + {VAL_PER_CLASS} val images per class")

os.makedirs(TRAIN_IMG, exist_ok=True)
os.makedirs(TRAIN_LBL, exist_ok=True)
os.makedirs(VALID_IMG, exist_ok=True)
os.makedirs(VALID_LBL, exist_ok=True)

def write_images(indices, out_img, out_lbl, count, prefix):
    generated = 0
    for class_idx in indices:
        syllable = index_map.get(str(class_idx), str(class_idx))
        try:
            font = ImageFont.truetype(FONT_PATH, random.randint(28, 80))
        except:
            font = ImageFont.load_default()
        for i in range(count):
            img_size = 320
            bg  = random.randint(180, 255)
            img = Image.new("RGB", (img_size, img_size), (bg, bg, bg))
            draw = ImageDraw.Draw(img)
            x   = random.randint(20, 220)
            y   = random.randint(20, 220)
            fg  = random.randint(0, 60)
            draw.text((x, y), syllable, font=font, fill=(fg, fg, fg))
            bbox = draw.textbbox((x, y), syllable, font=font)
            cx = (bbox[0] + bbox[2]) / 2 / img_size
            cy = (bbox[1] + bbox[3]) / 2 / img_size
            nw = (bbox[2] - bbox[0]) / img_size
            nh = (bbox[3] - bbox[1]) / img_size
            fname = f"{prefix}_{class_idx}_{i:04d}"
            img.save(os.path.join(out_img, fname + ".jpg"))
            with open(os.path.join(out_lbl, fname + ".txt"), "w") as lf:
                lf.write(f"{class_idx} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")
            generated += 1
    return generated

t = write_images(missed_indices, TRAIN_IMG, TRAIN_LBL, TRAIN_PER_CLASS, "v4tr")
v = write_images(missed_indices, VALID_IMG, VALID_LBL, VAL_PER_CLASS,   "v4vl")

for cache in ["/root/karen_dataset_yolov8/train/labels.cache",
              "/root/karen_dataset_yolov8/valid/labels.cache"]:
    if os.path.exists(cache): os.remove(cache)

print(f"[033] Done. {t} train + {v} val images written.")
print("[033] NEXT: python3 /root/karenlangtrans/034_train_v4.py")