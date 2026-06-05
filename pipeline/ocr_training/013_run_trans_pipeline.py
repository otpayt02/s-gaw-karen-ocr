# ============================================================
# FILE: 3_run_trans_pipeline.py
# PURPOSE: Production translation pipeline. Accepts any image
#          containing Karen script, runs the OCR model, assembles
#          detected syllables left-to-right by X position, looks
#          up each syllable in the dictionary, and outputs the
#          full Karen Unicode text with English word meanings.
# PIPELINE POSITION: Step 9 — Final production translation
# REQUIRES: best.pt, karen_index_map.json, karendictdatabase.json
# PRODUCES: Terminal output + optional annotated image saved to disk
# ============================================================

# IMPORT — json for loading both lookup files
import json

# IMPORT — os for file path and directory operations
import os

# IMPORT — brings in the YOLO inference engine
from ultralytics import YOLO

# FUNCTION DEFINITION — main translation function
# PARAMETER — image_path: absolute path to any Karen script image
# PARAMETER — save_annotated: if True, saves a bounding-box image to disk
def translate_karen_image(image_path, save_annotated=True):
    # INSTANTIATION — loads the trained Karen OCR model
    # WHY: best.pt is the highest-mAP checkpoint; always use this for inference
    model = YOLO('/workspace/runs/karen_ocr_v1/weights/best.pt')

    # FILE OPERATION — loads the YOLO index → Roboflow label bridge
    with open('/root/karen_lang_trans/karen_index_map.json', 'r') as f:
        index_map = json.load(f)

    # FILE OPERATION — loads the syllable → English translation dictionary
    with open('/root/karen_lang_trans/karendictdatabase.json', 'r') as f:
        karen_dict = json.load(f)

    # METHOD CALL — runs Karen OCR inference on the input image
    # ARGUMENT — conf=0.4 discards low-confidence noise detections
    # ARGUMENT — verbose=False suppresses YOLO terminal output
    results = model(image_path, conf=0.4, verbose=False)

    # CONDITIONAL — saves an annotated copy of the image if requested
    if save_annotated:
        # VARIABLE DECLARATION — builds output path for the annotated image
        out_path = image_path.replace('.jpg', '_annotated.jpg')
        results[0].save(out_path)

    # VARIABLE DECLARATION — list to accumulate all detected syllables with position
    detections = []

    # LOOP — processes each bounding box detection
    for box in results[0].boxes:
        # VARIABLE DECLARATION — class index as string for map lookup
        cls_idx  = str(int(box.cls))

        # METHOD CALL — step 1: index → Roboflow label
        robo_lbl = index_map.get(cls_idx, f'unknown_{cls_idx}')

        # METHOD CALL — step 2: Roboflow label → dictionary entry
        entry    = karen_dict.get(robo_lbl, {})

        # METHOD CALL — step 3: extract romanized syllable name
        syl_name = entry.get('syllable', robo_lbl)

        # METHOD CALL — step 4: extract English meaning
        meaning  = entry.get('english', 'no translation yet')

        # INDEX/SLICE — extracts the X center coordinate for left-to-right ordering
        # WHY: Karen is written left to right; sorting by X reconstructs word order
        x_center = float(box.xywhn[0][0])

        # METHOD CALL — confidence score as float
        conf = float(box.conf)

        # METHOD CALL — appends this detection as a tuple for sorting
        detections.append((x_center, cls_idx, robo_lbl, syl_name, meaning, conf))

    # METHOD CALL — sorts all detections by X position (left → right reading order)
    detections.sort(key=lambda d: d[0])

    # OUTPUT/PRINT — section header
    print(f"\n=== Translation: {os.path.basename(image_path)} ===")
    print(f"Detected {len(detections)} Karen syllables\n")

    # LOOP — prints each syllable in reading order with its English meaning
    for i, (x, cls_idx, robo_lbl, syl_name, meaning, conf) in enumerate(detections):
        print(f"  Syllable {i+1}: {syl_name} [{conf:.1%}] → {meaning}")

    # RETURN STATEMENT — returns the full list for programmatic use
    return detections


# CONDITIONAL — runs the translation when this file is executed directly
if __name__ == '__main__':
    # VARIABLE DECLARATION — picks the first validation image as a demo
    valid_dir = '/root/karen_dataset_yolov8/valid/images/'
    demo_img  = os.path.join(valid_dir, os.listdir(valid_dir)[0])
    # FUNCTION CALL — runs the full translation pipeline on the demo image
    translate_karen_image(demo_img, save_annotated=True)
