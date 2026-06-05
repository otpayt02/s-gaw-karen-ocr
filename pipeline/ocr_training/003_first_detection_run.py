# ============================================================
# FILE: first_detection_run.py
# PURPOSE: The proof-of-life run. Detects a Karen syllable,
#          prints its YOLO class index AND its Roboflow class
#          name string side by side. This script confirmed the
#          model is working at 91.4% confidence on the first try.
# PIPELINE POSITION: Step 1b — First confirmed detection
# REQUIRES: best.pt, valid/images/ folder
# PRODUCES: Terminal output showing index → class name → confidence
# ============================================================

# IMPORT — brings in the YOLO inference engine
from ultralytics import YOLO

# IMPORT — provides filesystem utilities
import os

# INSTANTIATION — loads trained Karen OCR weights into GPU/CPU memory
model = YOLO('/workspace/runs/karen_ocr_v1/weights/best.pt')

# VARIABLE DECLARATION — path to validation images folder
valid_dir = '/root/karen_dataset_yolov8/valid/images/'

# FUNCTION CALL + INDEX/SLICE — picks the first validation image dynamically
# WHY: avoids hardcoding a filename that may not exist on another machine
test_image = os.path.join(valid_dir, os.listdir(valid_dir)[0])

# METHOD CALL — runs the Karen OCR model on the test image
# ARGUMENT — conf=0.4 filters low-confidence noise detections
results = model(test_image, conf=0.4)

# OUTPUT/PRINT — shows total syllable count detected in the image
print(f"Detected: {len(results[0].boxes)} Karen syllables")

# LOOP — processes every detection bounding box in the result
for box in results[0].boxes:
    # VARIABLE DECLARATION — extracts the raw class index from the detection tensor
    # WHY: This integer (e.g. 5878) is YOLO's internal position in the 6341-class list
    cls_idx = int(box.cls)

    # INDEX/SLICE — looks up the Roboflow label name at position cls_idx
    # WHY: model.names[cls_idx] returns the string Roboflow assigned during training
    #      e.g. index 5878 → '8639'. The number '8639' is the CLASS NAME, not an index.
    cls_name = model.names[cls_idx]

    # OUTPUT/PRINT — prints the full mapping: internal index → Roboflow name → confidence
    # WHY: seeing both numbers side by side was the key insight that resolved the
    #      IndexError — 8639 is a name, not a position
    print(f"  Index {cls_idx} → class name '{cls_name}' → {float(box.conf):.1%} confidence")
