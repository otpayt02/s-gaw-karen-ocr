#!/usr/bin/env python3
"""
Karen OCR Dataset Generator — Playwright + Chromium renderer
Outputs Roboflow-ready YOLO format dataset.

Requirements: pip install playwright opencv-python numpy
              playwright install chromium

Put padauk_reg.ttf in the same folder, then run:
    python karen_dataset_gen.py
"""

import shutil
import random
import uuid
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
FONT_PATH        = Path("padauk_reg.ttf").resolve()
OUTPUT_DIR       = Path("karendataset")
CLASSES_FILE     = Path("roboflow_classes.txt")
YAML_FILE        = Path("data.yaml")

IMG_W            = 320
IMG_H            = 320
FONT_SIZE_PX     = 110
IMAGES_PER_COMBO = 5
SPLIT_TRAIN      = 0.70
SPLIT_VALID      = 0.15
RANDOM_SEED      = 42

# Set to a number like 100 for a quick test run, None for full dataset
MAX_CLASSES      = None

# ══════════════════════════════════════════════════════════
#  KAREN LANGUAGE DATA
# ══════════════════════════════════════════════════════════
CONSONANTS = [
    ("\u1000", "guh"),      ("\u1001", "hkuh"),    ("\u1002", "ghuh"),
    ("\u1003", "hcah"),     ("\u1004", "nguh"),    ("\u1005", "suhchuh"),
    ("\u1006", "hsuhshuh"), ("\u1061", "shuh"),    ("\u100A", "nyuh"),
    ("\u1010", "tuh"),      ("\u1011", "htuh"),    ("\u1012", "duh"),
    ("\u1014", "nuh"),      ("\u1015", "pbuh"),    ("\u1016", "hpuh"),
    ("\u1018", "buh"),      ("\u1019", "muh"),     ("\u101A", "yuh"),
    ("\u101B", "ruh"),      ("\u101C", "luh"),     ("\u101D", "wuh"),
    ("\u101E", "thuh"),     ("\u101F", "huh"),     ("\u1021", "uh"),
    ("\u1027", "uhh"),
]

VOWELS = [
    ("",        "a"),
    ("\u102B",  "ah"),
    ("\u1036",  "ee"),
    ("\u1062",  "er"),
    ("\u1037",  "ay"),
    ("\u102E",  "aw"),
    ("\u102D",  "oh"),
    ("\u1032",  "eh"),
    ("\u1030",  "oo"),
    ("\u102F",  "u"),
]

# ══════════════════════════════════════════════════════════
#  TONES
#  t1 = no tone marker
#  t2 = pler chee        U+1038  (visarga)
#  t3 = geh poh          U+1064
#  t4 = hah thee         U+1063 + U+103A
#  t5 = er thee          U+1062 + U+103A
#  t6 = ah thee          U+102C + U+103A
# ══════════════════════════════════════════════════════════
TONES = [
    ("",                    "t1"),
    ("\u1038",              "t2"),
    ("\u1064",              "t3"),
    ("\u1063\u103A",        "t4"),
    ("\u1062\u103A",        "t5"),
    ("\u102C\u103A",        "t6"),
]

MEDIALS = [
    ("\u103B", "medla"),
    ("\u103C", "medra"),
    ("\u103D", "medwa"),
    ("\u103E", "medgha"),
    ("\u1060", "medya"),
]

ASAT = [
    ("\u1019\u103A", "muh_asat"),
    ("\u1012\u103A", "duh_asat"),
]


# ══════════════════════════════════════════════════════════
#  HTML BUILDER  (no f-strings — avoids CSS brace errors)
# ══════════════════════════════════════════════════════════
def build_html(text, font_posix):
    return (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "@font-face{font-family:'PK';"
        "src:url('file:///" + font_posix + "')format('truetype');}"
        "html,body{margin:0;background:white;}"
        ".w{width:" + str(IMG_W) + "px;height:" + str(IMG_H) + "px;"
        "display:flex;align-items:center;justify-content:center;"
        "padding:30px;box-sizing:border-box;}"
        ".t{font-family:'PK',sans-serif;font-size:" + str(FONT_SIZE_PX) + "px;"
        "line-height:1.45;color:black;white-space:nowrap;}"
        "</style></head><body>"
        "<div class='w'><div class='t'>" + text + "</div></div>"
        "</body></html>"
    )


# ══════════════════════════════════════════════════════════
#  RENDER
# ══════════════════════════════════════════════════════════
def render(page, text, font_posix, font_loaded):
    html = build_html(text, font_posix)
    page.set_content(html, wait_until="load")
    if not font_loaded[0]:
        try:
            page.wait_for_function(
                "document.fonts && document.fonts.status === 'loaded'",
                timeout=5000
            )
            font_loaded[0] = True
        except Exception:
            pass
    png = page.screenshot(
        clip={"x": 0, "y": 0, "width": IMG_W, "height": IMG_H}
    )
    arr = np.frombuffer(png, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


# ══════════════════════════════════════════════════════════
#  YOLO BOUNDING BOX
# ══════════════════════════════════════════════════════════
def yolo_bbox(img, class_id):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
    pts = cv2.findNonZero(mask)
    if pts is None:
        return None
    x, y, w, h = cv2.boundingRect(pts)
    PAD = 8
    H, W = img.shape[:2]
    x  = max(0, x - PAD)
    y  = max(0, y - PAD)
    x2 = min(W, x + w + PAD * 2)
    y2 = min(H, y + h + PAD * 2)
    w, h = x2 - x, y2 - y
    cx = (x + w / 2.0) / W
    cy = (y + h / 2.0) / H
    return "%d %.6f %.6f %.6f %.6f" % (class_id, cx, cy, w / W, h / H)


# ══════════════════════════════════════════════════════════
#  AUGMENTATION
# ══════════════════════════════════════════════════════════
def augment(img):
    h, w = img.shape[:2]
    angle = random.uniform(-7, 7)
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    img = cv2.warpAffine(img, M, (w, h),
                         flags=cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_CONSTANT,
                         borderValue=(255, 255, 255))
    if random.random() < 0.35:
        k = random.choice([3, 5])
        img = cv2.GaussianBlur(img, (k, k), 0)
    noise = np.random.normal(0, 5, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return img


# ══════════════════════════════════════════════════════════
#  BUILD ALL SYLLABLE COMBINATIONS
# ══════════════════════════════════════════════════════════
def build_combos():
    out = []
    for c_ch, c_rm in CONSONANTS:
        for v_ch, v_rm in VOWELS:
            for t_ch, t_rm in TONES:
                out.append((c_ch + v_ch + t_ch,
                             c_rm + "_" + v_rm + "_" + t_rm))
    for c_ch, c_rm in CONSONANTS:
        for m_ch, m_rm in MEDIALS:
            for v_ch, v_rm in VOWELS:
                for t_ch, t_rm in TONES:
                    out.append((c_ch + m_ch + v_ch + t_ch,
                                 c_rm + "_" + m_rm + "_" + v_rm + "_" + t_rm))
    for text, label in ASAT:
        out.append((text, label))
    return out


# ══════════════════════════════════════════════════════════
#  STRATIFIED SPLIT
# ══════════════════════════════════════════════════════════
def stratified_split(per_class):
    rng = random.Random(RANDOM_SEED)
    result = {"train": [], "valid": [], "test": []}
    for pairs in per_class:
        rng.shuffle(pairs)
        n = len(pairs)
        n_tr = max(1, int(n * SPLIT_TRAIN))
        n_vl = max(1, int(n * SPLIT_VALID))
        result["train"].extend(pairs[:n_tr])
        result["valid"].extend(pairs[n_tr:n_tr + n_vl])
        result["test"].extend(pairs[n_tr + n_vl:])
    return result


# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════
def main():
    random.seed(RANDOM_SEED)

    if not FONT_PATH.exists():
        raise FileNotFoundError(
            "padauk_reg.ttf not found at: " + str(FONT_PATH) +
            "\nPut it in the same folder as this script."
        )

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    CLASSES_FILE.write_text("", encoding="utf-8")
    if YAML_FILE.exists():
        YAML_FILE.unlink()

    stage = OUTPUT_DIR / "_stage"
    stage.mkdir()

    combos = build_combos()
    if MAX_CLASSES is not None:
        combos = combos[:MAX_CLASSES]

    total_imgs = len(combos) * IMAGES_PER_COMBO
    print("Classes      : " + str(len(combos)))
    print("Total images : " + str(total_imgs))
    print("Font         : " + str(FONT_PATH))
    print("")

    with open(CLASSES_FILE, "w", encoding="utf-8") as f:
        for _, label in combos:
            f.write(label + "\n")
    print("Wrote " + str(CLASSES_FILE))

    font_posix = FONT_PATH.as_posix()
    font_loaded = [False]
    per_class = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": IMG_W, "height": IMG_H})

        for idx, (text, label) in enumerate(combos):
            base_img = render(page, text, font_posix, font_loaded)
            pairs = []

            for copy_i in range(IMAGES_PER_COMBO):
                uid = uuid.uuid4().hex[:8]
                fname = label + "_" + uid
                img_path = stage / (fname + ".jpg")
                txt_path = stage / (fname + ".txt")

                img = augment(base_img) if copy_i > 0 else base_img.copy()
                bbox_str = yolo_bbox(img, idx)
                if bbox_str is None:
                    continue

                cv2.imwrite(str(img_path), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                txt_path.write_text(bbox_str + "\n", encoding="utf-8")
                pairs.append((img_path, txt_path))

            per_class.append(pairs)

            if (idx + 1) % 200 == 0 or idx + 1 == len(combos):
                pct = int(100 * (idx + 1) / len(combos))
                print("  " + str(idx + 1) + "/" + str(len(combos)) +
                      " classes  (" + str(pct) + "%)")

        browser.close()

    print("\nSplitting dataset ...")
    splits = stratified_split(per_class)
    for split_name, pairs in splits.items():
        img_dir = OUTPUT_DIR / split_name / "images"
        lbl_dir = OUTPUT_DIR / split_name / "labels"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        for img_src, txt_src in pairs:
            shutil.move(str(img_src), str(img_dir / img_src.name))
            shutil.move(str(txt_src), str(lbl_dir / txt_src.name))

    shutil.rmtree(stage, ignore_errors=True)

    names_list = [label for _, label in combos]
    with open(YAML_FILE, "w", encoding="utf-8") as f:
        f.write("path: " + str(OUTPUT_DIR.resolve()) + "\n")
        f.write("train: train/images\n")
        f.write("val:   valid/images\n")
        f.write("test:  test/images\n\n")
        f.write("nc: " + str(len(combos)) + "\n")
        f.write("names:\n")
        for n in names_list:
            f.write("  - " + n + "\n")

    tr = len(list((OUTPUT_DIR / "train" / "images").glob("*.jpg")))
    vl = len(list((OUTPUT_DIR / "valid" / "images").glob("*.jpg")))
    te = len(list((OUTPUT_DIR / "test"  / "images").glob("*.jpg")))

    print("\n DONE")
    print("  Classes file : " + str(CLASSES_FILE))
    print("  YAML file    : " + str(YAML_FILE))
    print("  Dataset dir  : " + str(OUTPUT_DIR))
    print("  Train images : " + str(tr))
    print("  Valid images : " + str(vl))
    print("  Test images  : " + str(te))


if __name__ == "__main__":
    main()