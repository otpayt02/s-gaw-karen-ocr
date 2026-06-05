#!/usr/bin/env python3
"""
020_generate_booster_images.py
PIPELINE POSITION: Step 3 of new-instance setup. Run AFTER 019.
PURPOSE: Takes the list of under-performing syllable classes identified by the gap
         analysis (syllables the model missed or detected below 50% confidence),
         generates 100 augmented training images per missed class using the Padauk font,
         writes them into the train/images and train/labels directories with proper
         YOLO format annotations, and saves a report.
REQUIRES: /root/karenlangtrans/path_config.json (written by 018)
           /root/karenlangtrans/padauk-regular.ttf
           /root/karen_dataset_yolov8/data.yaml (cleaned by 019)
PRODUCES: Up to 100 new .jpg images per missed syllable in train/images/
           Matching YOLO .txt label files in train/labels/
           /root/karenlangtrans/020_booster_report.json
"""

import os
import json
import random
import yaml
import numpy as np

# IMPORT: PIL (Pillow) for image creation and drawing Karen Unicode syllables
from PIL import Image, ImageDraw, ImageFont

# IMPORT: OpenCV for augmentation transforms (blur, noise, rotation)
import cv2

# VARIABLE DECLARATION: load canonical paths from path_config.json (written by 018)
CONFIG_PATH = '/root/karenlangtrans/path_config.json'
with open(CONFIG_PATH, 'r') as f:
    paths = json.load(f)

# VARIABLE DECLARATION: load data.yaml to map class names → indices (2026 paradigm only)
with open(paths['data_yaml'], 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
names = cfg['names']
# LIST/DICT/SET: name-to-index lookup dict so we can find a class number by syllable name
name_to_index = {name: i for i, name in enumerate(names)}

# VARIABLE DECLARATION: load the index map for index → romanized syllable name lookups
with open(paths['karen_index_map'], 'r', encoding='utf-8') as f:
    index_map = json.load(f)
# LIST/DICT/SET: reverse of index_map: romanized syllable → class index number
syllable_to_index = {v: int(k) for k, v in index_map.items()}

# LIST/DICT/SET: syllables identified by gap analysis (016/017) as missed or weak.
# These are romanized syllable names from karen_index_map.json.
# UPDATE THIS LIST each time you run a new gap analysis.
MISSED_SYLLABLES = [
    "tuh_oo_t5", "tuh_oo_t6", "uh_u_t2", "uh_u_t3",
    "shuh_aw_t4", "shuh_aw_t5", "muh_ay_t6", "nuh_ay_t6",
    "pbuh_ih_t2", "pbuh_ih_t3", "luh_oe_t4", "luh_oe_t5",
    "ghuh_eh_t1", "ghuh_eh_t2", "ruh_au_t3", "ruh_au_t4",
    "yuh_u_t6"
]

# VARIABLE DECLARATION: how many booster images to generate per missed syllable
IMAGES_PER_SYLLABLE = 100

# VARIABLE DECLARATION: output directories (already exist from dataset generation)
train_img_dir = paths['train_images']
train_lbl_dir = paths['train_labels']
font_path      = paths['font_path']

# VARIABLE DECLARATION: image dimensions — must match the training imgsz=320
IMG_SIZE = 320

print(f"Syllables to boost: {len(MISSED_SYLLABLES)}")

# VARIABLE DECLARATION: counters for the final report
total_generated = 0
skipped = []
per_class_counts = {}

# LOOP: process each missed syllable name one at a time
for syllable_name in MISSED_SYLLABLES:

    # CONDITIONAL: skip if this syllable name is not in our index map
    if syllable_name not in syllable_to_index:
        print(f"Not found in map (skipped): {syllable_name}")
        skipped.append(syllable_name)
        continue

    # VARIABLE DECLARATION: the integer class index for this syllable
    class_idx = syllable_to_index[syllable_name]

    # VARIABLE DECLARATION: the Unicode string for this syllable from the index map
    unicode_str = index_map[str(class_idx)]
    print(f"Boosting class {class_idx} ({syllable_name}) → Unicode: {unicode_str}")

    # VARIABLE DECLARATION: counter for images generated for this one syllable
    count_this_class = 0

    # LOOP: generate IMAGES_PER_SYLLABLE augmented images for this class
    for img_idx in range(IMAGES_PER_SYLLABLE):

        # VARIABLE DECLARATION: random background shade (near-white, slight variation)
        bg_val = random.randint(240, 255)

        # INSTANTIATION: create a blank PIL image with the random background
        img = Image.new('RGB', (IMG_SIZE, IMG_SIZE), color=(bg_val, bg_val, bg_val))
        draw = ImageDraw.Draw(img)

        # VARIABLE DECLARATION: random font size between 48px and 180px to create scale variety
        font_size = random.randint(48, 180)

        # EXCEPTION HANDLER: load the Padauk font; fall back to PIL default if missing
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()

        # VARIABLE DECLARATION: random text color (dark gray to black range)
        text_color = random.randint(0, 60)

        # VARIABLE DECLARATION: measure the text bounding box so we can center it
        bbox = draw.textbbox((0, 0), unicode_str, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # VARIABLE DECLARATION: random offset from center to avoid always-centered images
        offset_x = random.randint(-20, 20)
        offset_y = random.randint(-20, 20)

        # VARIABLE DECLARATION: top-left corner position to draw the text centered + offset
        x = (IMG_SIZE - text_w) // 2 + offset_x
        y = (IMG_SIZE - text_h) // 2 + offset_y

        # METHOD CALL: draw the Karen Unicode syllable onto the blank image
        draw.text((x, y), unicode_str, font=font, fill=(text_color, text_color, text_color))

        # VARIABLE DECLARATION: convert PIL image to OpenCV numpy array for augmentation
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # CONDITIONAL: apply random Gaussian blur (50% chance)
        if random.random() < 0.5:
            ksize = random.choice([3, 5])
            img_cv = cv2.GaussianBlur(img_cv, (ksize, ksize), 0)

        # CONDITIONAL: apply random noise (40% chance)
        if random.random() < 0.4:
            noise = np.random.normal(0, random.randint(3, 10), img_cv.shape).astype(np.int16)
            img_cv = np.clip(img_cv.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # CONDITIONAL: apply random rotation up to ±8 degrees (60% chance)
        if random.random() < 0.6:
            angle = random.uniform(-8, 8)
            M = cv2.getRotationMatrix2D((IMG_SIZE // 2, IMG_SIZE // 2), angle, 1.0)
            img_cv = cv2.warpAffine(img_cv, M, (IMG_SIZE, IMG_SIZE),
                                     borderMode=cv2.BORDER_CONSTANT,
                                     borderValue=(bg_val, bg_val, bg_val))

        # VARIABLE DECLARATION: unique filename for this booster image
        img_filename = f"boost_{syllable_name}_{img_idx:04d}.jpg"
        img_out_path = os.path.join(train_img_dir, img_filename)

        # FILE OPERATION: save the augmented image as JPEG
        cv2.imwrite(img_out_path, img_cv)

        # VARIABLE DECLARATION: YOLO annotation values — bounding box centered on character
        # cx, cy = center as fraction of image size; w, h = box size as fraction
        cx = (x + text_w / 2) / IMG_SIZE
        cy = (y + text_h / 2) / IMG_SIZE
        w  = min(text_w / IMG_SIZE, 1.0)
        h  = min(text_h / IMG_SIZE, 1.0)

        # VARIABLE DECLARATION: clamp all values to valid [0, 1] range
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        w  = max(0.01, w)
        h  = max(0.01, h)

        # VARIABLE DECLARATION: label file path (same base name as image, .txt extension)
        lbl_filename  = img_filename.replace('.jpg', '.txt')
        lbl_out_path  = os.path.join(train_lbl_dir, lbl_filename)

        # FILE OPERATION: write the YOLO annotation line: <class_idx> <cx> <cy> <w> <h>
        with open(lbl_out_path, 'w') as f:
            f.write(f"{class_idx} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

        count_this_class += 1
        total_generated  += 1

    per_class_counts[syllable_name] = count_this_class

# VARIABLE DECLARATION: build the report dict
report = {
    "missed_syllables":    MISSED_SYLLABLES,
    "images_per_syllable": IMAGES_PER_SYLLABLE,
    "skipped_syllables":   skipped,
    "total_generated":     total_generated,
    "per_class_counts":    per_class_counts,
    "added_to":            train_img_dir,
}

# VARIABLE DECLARATION: report output path
report_path = '/root/karenlangtrans/020_booster_report.json'

# FILE OPERATION: save the report to disk
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

# OUTPUT/PRINT: final terminal summary
print(f"Total booster images generated: {total_generated}")
print(f"Skipped (not in map): {len(skipped)}")
print(f"Added to: {train_img_dir}")
print(f"Report saved: {report_path}")
print("020 COMPLETE — retrain now with boosted dataset")
