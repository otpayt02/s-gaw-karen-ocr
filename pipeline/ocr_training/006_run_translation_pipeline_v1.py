# ============================================================
# FILE: run_translation_pipeline_v1.py
# PURPOSE: First full end-to-end pipeline run. Loads the model,
#          both lookup files, and runs inference on 5 validation
#          images. At this stage syllable names show as Roboflow
#          numeric labels and english shows "no translation yet"
#          — this confirmed the pipeline architecture is sound.
# PIPELINE POSITION: Step 4 — First full pipeline proof of life
# REQUIRES: best.pt, karen_index_map.json, karendictdatabase.json,
#           valid/images/ folder
# PRODUCES: Terminal output with confidence + class label per image
# ============================================================

# IMPORT — provides json.load() for reading both lookup JSON files
import json

# IMPORT — provides os.listdir() and os.path.join() for image iteration
import os

# IMPORT — brings in the YOLO inference engine
from ultralytics import YOLO

# INSTANTIATION — loads trained Karen OCR model weights into memory
# WHY: karen_ocr_v1 is the run folder YOLO created during training;
#      best.pt is always the highest-mAP checkpoint
model = YOLO('/workspace/runs/karen_ocr_v1/weights/best.pt')

# FILE OPERATION — opens the index→Roboflow label bridge file
with open('/root/karen_lang_trans/karen_index_map.json', 'r') as f:
    # VARIABLE DECLARATION — dictionary mapping int index → string label
    # WHY: YOLO outputs integer indices; this converts them to Roboflow names
    index_map = json.load(f)

# FILE OPERATION — opens the syllable translation database
with open('/root/karen_lang_trans/karendictdatabase.json', 'r') as f:
    # VARIABLE DECLARATION — dictionary mapping Roboflow label → syllable entry
    # WHY: this is where romanized names and English meanings live
    karen_dict = json.load(f)

# VARIABLE DECLARATION — path to the validation images folder
valid_dir = '/root/karen_dataset_yolov8/valid/images/'

# FUNCTION CALL + INDEX/SLICE — gets first 5 filenames from the folder
# WHY: testing on 5 images gives a meaningful sample without a long wait
test_images = os.listdir(valid_dir)[:5]

# LOOP — iterates over each of the 5 test image filenames
for img_name in test_images:
    # VARIABLE DECLARATION — builds the full absolute path to the image
    img_path = os.path.join(valid_dir, img_name)

    # METHOD CALL — runs inference on this image
    # ARGUMENT — verbose=False suppresses per-image YOLO terminal spam
    results = model(img_path, conf=0.4, verbose=False)

    # OUTPUT/PRINT — prints the image filename as a section header
    print(f"\nImage: {img_name}")

    # CONDITIONAL — handles the case where no syllable was detected
    if len(results[0].boxes) == 0:
        print("  No detections above 0.4 confidence")

    # LOOP — processes each bounding box detection found in this image
    for box in results[0].boxes:
        # VARIABLE DECLARATION — converts tensor index to string for dict lookup
        # WHY: JSON keys are strings; int tensor must be cast to str to match
        cls_idx  = str(int(box.cls))

        # METHOD CALL — translates YOLO index to Roboflow label string
        # ARGUMENT — fallback string prevents KeyError if index not in map
        syl_name = index_map.get(cls_idx, f'unknown_{cls_idx}')

        # METHOD CALL (chained) — two-step safe lookup into karen_dict
        # WHY: .get(syl_name, {}) returns empty dict if label missing,
        #      then .get('english', ...) safely pulls the English field
        meaning  = karen_dict.get(syl_name, {}).get('english', 'no translation yet')

        # VARIABLE DECLARATION — extracts confidence score as a plain float
        conf     = float(box.conf)

        # OUTPUT/PRINT — prints confidence, syllable label, and English meaning
        print(f"  [{conf:.1%}] class '{syl_name}' → {meaning}")
