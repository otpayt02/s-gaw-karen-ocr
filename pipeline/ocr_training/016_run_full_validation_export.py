# ============================================================
# FILE: 016_run_full_validation_export.py
# PURPOSE: Runs inference on ALL 4,449 validation images and
#          exports every detection to detections_log.csv.
#          This is your full performance snapshot — every
#          syllable the model can and cannot detect, logged
#          permanently for review in Excel or VS Code.
#          Also appends a new entry to server_terminal_log.txt
#          so the run is documented automatically.
# PIPELINE POSITION: Step 10 — Full validation evaluation + logging
# REQUIRES: best.pt, karen_index_map.json, karendictdatabase.json,
#           valid/images/ (all 4449 images)
# PRODUCES: /root/karen_lang_trans/detections_log.csv
#           /root/karen_lang_trans/server_terminal_log.txt (appended)
# ============================================================

# IMPORT — csv for writing the detections spreadsheet
import csv

# IMPORT — json for loading both lookup files
import json

# IMPORT — os for filesystem navigation across the validation folder
import os

# IMPORT — datetime for timestamping the log entry
from datetime import datetime

# IMPORT — brings in the YOLO inference engine
from ultralytics import YOLO

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

# VARIABLE DECLARATION — path to the trained Karen OCR model weights
MODEL_PATH   = '/workspace/runs/karen_ocr_v1/weights/best.pt'

# VARIABLE DECLARATION — path to the YOLO index → Roboflow label bridge
INDEX_MAP    = '/root/karen_lang_trans/karen_index_map.json'

# VARIABLE DECLARATION — path to the syllable translation database
DICT_PATH    = '/root/karen_lang_trans/karendictdatabase.json'

# VARIABLE DECLARATION — path to the validation images folder
VALID_DIR    = '/root/karen_dataset_yolov8/valid/images/'

# VARIABLE DECLARATION — output CSV path
CSV_OUT      = '/root/karen_lang_trans/detections_log.csv'

# VARIABLE DECLARATION — server log path for automatic documentation
SERVER_LOG   = '/root/karen_lang_trans/server_terminal_log.txt'

# VARIABLE DECLARATION — confidence threshold for detections
CONF_THRESH  = 0.4

# ── LOAD RESOURCES ────────────────────────────────────────────────────────────

# INSTANTIATION — loads trained Karen OCR model into GPU memory
# WHY: best.pt is the highest-mAP checkpoint from training
model = YOLO(MODEL_PATH)

# FILE OPERATION — loads the index→label bridge
with open(INDEX_MAP, 'r') as f:
    # VARIABLE DECLARATION — maps string index → Roboflow label string
    index_map = json.load(f)

# FILE OPERATION — loads the syllable dictionary
with open(DICT_PATH, 'r', encoding='utf-8') as f:
    # VARIABLE DECLARATION — maps Roboflow label → syllable entry dict
    karen_dict = json.load(f)

# ── RUN INFERENCE ON ALL VALIDATION IMAGES ───────────────────────────────────

# VARIABLE DECLARATION — full sorted list of all validation image filenames
# WHY: sorted() ensures consistent ordering across runs for reproducible CSV
all_images = sorted(os.listdir(VALID_DIR))

# VARIABLE DECLARATION — counters for summary statistics
total_detections = 0
images_with_hits = 0
images_no_hits   = 0

# OUTPUT/PRINT — progress header
print(f"Running inference on {len(all_images)} validation images...")
print(f"Confidence threshold: {CONF_THRESH}")
print(f"Output CSV: {CSV_OUT}\n")

# FILE OPERATION — opens the CSV file for writing
with open(CSV_OUT, 'w', newline='', encoding='utf-8') as csvfile:
    # INSTANTIATION — creates a CSV writer object
    writer = csv.writer(csvfile)

    # METHOD CALL — writes the column header row
    # WHY: these columns let you filter by syllable, confidence, or image in Excel
    writer.writerow([
        'image', 'cls_idx', 'robo_label', 'syllable',
        'english', 'confidence', 'x_center', 'y_center', 'width', 'height'
    ])

    # LOOP — iterates over every validation image
    for i, img_name in enumerate(all_images):
        # VARIABLE DECLARATION — builds the absolute path to this image
        img_path = os.path.join(VALID_DIR, img_name)

        # METHOD CALL — runs inference silently on this image
        # ARGUMENT — verbose=False suppresses per-image terminal spam
        results = model(img_path, conf=CONF_THRESH, verbose=False)

        # VARIABLE DECLARATION — number of detections in this image
        n_boxes = len(results[0].boxes)

        # CONDITIONAL — updates counters based on detection result
        if n_boxes > 0:
            images_with_hits += 1
        else:
            images_no_hits   += 1

        # LOOP — processes each bounding box in this image
        for box in results[0].boxes:
            # VARIABLE DECLARATION — class index as string key
            cls_idx  = str(int(box.cls))

            # METHOD CALL — translates index to Roboflow label
            robo_lbl = index_map.get(cls_idx, f'unknown_{cls_idx}')

            # METHOD CALL — gets dictionary entry for this syllable
            entry    = karen_dict.get(robo_lbl, {})

            # METHOD CALL — extracts romanized syllable name
            syl_name = entry.get('syllable', robo_lbl)

            # METHOD CALL — extracts English meaning (placeholder until PDF parser)
            meaning  = entry.get('english', 'no translation yet')

            # VARIABLE DECLARATION — confidence score as float
            conf     = float(box.conf)

            # INDEX/SLICE — extracts normalized bounding box [x_center, y_center, w, h]
            # WHY: xywhn gives values 0.0–1.0 relative to image dimensions
            xywh     = box.xywhn[0].tolist()

            # METHOD CALL — writes one row per detection to the CSV
            writer.writerow([
                img_name, cls_idx, robo_lbl, syl_name, meaning,
                f'{conf:.4f}',
                f'{xywh[0]:.4f}', f'{xywh[1]:.4f}',
                f'{xywh[2]:.4f}', f'{xywh[3]:.4f}'
            ])

            # VARIABLE DECLARATION — increments total detection counter
            total_detections += 1

        # OUTPUT/PRINT — progress update every 500 images
        # WHY: 4449 images takes ~45 seconds; this confirms it's still running
        if (i + 1) % 500 == 0:
            print(f"  Processed {i+1}/{len(all_images)} images...")

# ── SUMMARY ──────────────────────────────────────────────────────────────────

# OUTPUT/PRINT — final statistics
print(f"\n=== EXPORT COMPLETE ===")
print(f"Total images processed : {len(all_images)}")
print(f"Images with detections : {images_with_hits}")
print(f"Images with no hit     : {images_no_hits}")
print(f"Total detections logged: {total_detections}")
print(f"CSV saved to           : {CSV_OUT}")

# ── APPEND TO SERVER LOG ──────────────────────────────────────────────────────

# VARIABLE DECLARATION — timestamp for the log entry
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

# VARIABLE DECLARATION — the log entry string to append
log_entry = f"""
────────────────────────────────────────────────────────────────────────────────
[{timestamp}] FULL VALIDATION EXPORT — 016_run_full_validation_export.py
COMMAND:
  python3 016_run_full_validation_export.py
OUTPUT:
  Total images processed : {len(all_images)}
  Images with detections : {{images_with_hits}}
  Images with no hit     : {{images_no_hits}}
  Total detections logged: {{total_detections}}
  CSV saved to           : {CSV_OUT}
WHAT THIS MEANS:
  Every detection across all 4449 validation images is now logged to CSV.
  Open detections_log.csv in Excel to review per-class performance.
  Syllables showing low detection rates are candidates for more training data.
NEXT: Run 017_pdf_dict_parser.py to populate English meanings from Karen PDF.
────────────────────────────────────────────────────────────────────────────────
"""

# FILE OPERATION — opens the server log in append mode
# ARGUMENT — 'a' means append: new content is added after existing content
# WHY: we never overwrite the log — every session accumulates permanently
with open(SERVER_LOG, 'a', encoding='utf-8') as logf:
    # METHOD CALL — writes the new log entry to the end of the file
    logf.write(log_entry.format(
        images_with_hits=images_with_hits,
        images_no_hits=images_no_hits,
        total_detections=total_detections
    ))

# OUTPUT/PRINT — confirms the log was updated
print(f"\nServer log updated: {SERVER_LOG}")
print("Download server_terminal_log.txt to overwrite your local copy.")
