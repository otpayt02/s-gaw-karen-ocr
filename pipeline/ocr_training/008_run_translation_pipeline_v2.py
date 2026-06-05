# ============================================================
# FILE: run_translation_pipeline_v2.py
# PURPOSE: Final working pipeline. After populate_dict_from_filenames.py
#          runs, this script shows real romanized Karen syllable names
#          (e.g. "uh_medgha_u_t6") for every detection instead of
#          numeric Roboflow labels. English meanings show "no translation
#          yet" until 2_build_dict_data.py parses the dictionary PDF.
# PIPELINE POSITION: Step 6 — Production inference with real syllable names
# REQUIRES: best.pt, karen_index_map.json, karendictdatabase.json (populated)
# PRODUCES: Terminal output: confidence + romanized syllable + English meaning
# ============================================================

# IMPORT — provides json.load() for both lookup files
import json

# IMPORT — provides filesystem utilities for image iteration
import os

# IMPORT — brings in the YOLO inference engine
from ultralytics import YOLO

# INSTANTIATION — loads the trained Karen OCR model
model = YOLO('/workspace/runs/karen_ocr_v1/weights/best.pt')

# FILE OPERATION — loads the YOLO index → Roboflow label bridge
with open('/root/karen_lang_trans/karen_index_map.json', 'r') as f:
    # VARIABLE DECLARATION — maps string index to Roboflow numeric label string
    index_map = json.load(f)

# FILE OPERATION — loads the populated translation dictionary
with open('/root/karen_lang_trans/karendictdatabase.json', 'r') as f:
    # VARIABLE DECLARATION — maps Roboflow label → syllable name + English meaning
    karen_dict = json.load(f)

# VARIABLE DECLARATION — validation images folder path
valid_dir = '/root/karen_dataset_yolov8/valid/images/'

# FUNCTION CALL + INDEX/SLICE — selects the first 5 validation images
test_images = os.listdir(valid_dir)[:5]

# LOOP — runs the full pipeline on each of the 5 test images
for img_name in test_images:
    # VARIABLE DECLARATION — builds absolute path to this image
    img_path = os.path.join(valid_dir, img_name)

    # METHOD CALL — runs Karen OCR inference silently
    results = model(img_path, conf=0.4, verbose=False)

    # OUTPUT/PRINT — image filename as section separator
    print(f"\nImage: {img_name}")

    # CONDITIONAL — prints a message when nothing was detected
    if len(results[0].boxes) == 0:
        print("  No detections above 0.4 confidence")

    # LOOP — processes each detection in this image
    for box in results[0].boxes:
        # VARIABLE DECLARATION — YOLO class index as a string for dict lookup
        cls_idx  = str(int(box.cls))

        # METHOD CALL — step 1 of translation chain: index → Roboflow label
        robo_lbl = index_map.get(cls_idx, f'unknown_{cls_idx}')

        # METHOD CALL — step 2: Roboflow label → full dictionary entry
        entry    = karen_dict.get(robo_lbl, {})

        # METHOD CALL — step 3: extract romanized syllable name from entry
        # ARGUMENT — falls back to robo_lbl if syllable field is missing
        # WHY: after populate_dict_from_filenames.py runs, this returns
        #      the real name like "uh_medgha_u_t6" instead of "8639"
        syl_name = entry.get('syllable', robo_lbl)

        # METHOD CALL — step 4: extract English meaning
        # ARGUMENT — placeholder until 2_build_dict_data.py fills this in
        meaning  = entry.get('english', 'no translation yet')

        # VARIABLE DECLARATION — detection confidence as a plain Python float
        conf     = float(box.conf)

        # OUTPUT/PRINT — final readable output: confidence, syllable, meaning
        print(f"  [{conf:.1%}] {syl_name} → {meaning}")
