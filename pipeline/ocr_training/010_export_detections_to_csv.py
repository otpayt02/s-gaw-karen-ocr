# ============================================================
# FILE: export_detections_to_csv.py
# PURPOSE: Runs inference on the full validation set and writes
#          every detection (image, syllable, confidence, bounding
#          box) to a CSV file. Use this to review model performance
#          across all classes in a spreadsheet locally.
# PIPELINE POSITION: Step 7 — Evaluation and local documentation
# REQUIRES: best.pt, karen_index_map.json, karendictdatabase.json,
#           valid/images/ folder
# PRODUCES: /root/karen_lang_trans/detections_log.csv
# ============================================================

# IMPORT — provides csv writing utilities
import csv

# IMPORT — provides json.load() for lookup files
import json

# IMPORT — provides filesystem utilities
import os

# IMPORT — brings in the YOLO inference engine
from ultralytics import YOLO

# INSTANTIATION — loads trained Karen OCR model weights
model = YOLO('/workspace/runs/karen_ocr_v1/weights/best.pt')

# FILE OPERATION — loads the YOLO index → Roboflow label map
with open('/root/karen_lang_trans/karen_index_map.json', 'r') as f:
    index_map = json.load(f)

# FILE OPERATION — loads the syllable translation dictionary
with open('/root/karen_lang_trans/karendictdatabase.json', 'r') as f:
    karen_dict = json.load(f)

# VARIABLE DECLARATION — path to the validation images folder
valid_dir = '/root/karen_dataset_yolov8/valid/images/'

# VARIABLE DECLARATION — full list of all validation image filenames
all_images = os.listdir(valid_dir)

# VARIABLE DECLARATION — path where the output CSV will be saved
out_csv = '/root/karen_lang_trans/detections_log.csv'

# FILE OPERATION — opens the CSV file for writing
with open(out_csv, 'w', newline='', encoding='utf-8') as csvfile:
    # INSTANTIATION — creates a CSV writer object bound to this file
    writer = csv.writer(csvfile)

    # METHOD CALL — writes the column header row
    # WHY: defines the structure of the spreadsheet for local review
    writer.writerow(['image', 'cls_idx', 'robo_label', 'syllable', 'english', 'confidence',
                     'x_center', 'y_center', 'width', 'height'])

    # LOOP — runs inference on every validation image
    for img_name in all_images:
        # VARIABLE DECLARATION — builds absolute image path
        img_path = os.path.join(valid_dir, img_name)

        # METHOD CALL — runs Karen OCR inference silently
        results = model(img_path, conf=0.4, verbose=False)

        # LOOP — processes each detection bounding box
        for box in results[0].boxes:
            # VARIABLE DECLARATION — class index as string
            cls_idx  = str(int(box.cls))

            # METHOD CALL — gets Roboflow label from index map
            robo_lbl = index_map.get(cls_idx, f'unknown_{cls_idx}')

            # METHOD CALL — gets dictionary entry for this syllable
            entry    = karen_dict.get(robo_lbl, {})

            # METHOD CALL — extracts romanized syllable name
            syl_name = entry.get('syllable', robo_lbl)

            # METHOD CALL — extracts English meaning
            meaning  = entry.get('english', 'no translation yet')

            # VARIABLE DECLARATION — confidence as plain float
            conf     = float(box.conf)

            # INDEX/SLICE — extracts normalized bounding box coordinates
            # WHY: xyxyn gives [x1,y1,x2,y2] normalized 0-1; xywhn gives center+size
            xywh = box.xywhn[0].tolist()

            # METHOD CALL — writes one row per detection to the CSV
            writer.writerow([img_name, cls_idx, robo_lbl, syl_name, meaning,
                             f'{conf:.4f}', f'{xywh[0]:.4f}', f'{xywh[1]:.4f}',
                             f'{xywh[2]:.4f}', f'{xywh[3]:.4f}'])

# OUTPUT/PRINT — confirms where the CSV was saved
print(f"Detections log saved to: {out_csv}")
print(f"Open in Excel or VS Code to review all {len(all_images)} validation images")
