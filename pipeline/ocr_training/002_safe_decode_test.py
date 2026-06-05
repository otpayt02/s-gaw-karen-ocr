# ============================================================
# FILE: safe_decode_test.py
# PURPOSE: Run a single test inference on one validation image
#          using a crash-safe class name lookup. Use this any
#          time you want to verify the model loads and detects
#          without risking an IndexError.
# PIPELINE POSITION: Step 1 — Single image smoke test
# REQUIRES: best.pt, valid/images/ folder with at least one image
# PRODUCES: test_result.jpg saved to /root/karen_lang_trans/
# ============================================================

# IMPORT — brings in the YOLO inference engine
from ultralytics import YOLO

# IMPORT — provides os.path and os.listdir for filesystem navigation
import os

# INSTANTIATION — loads the trained Karen OCR model weights into memory
# WHY: best.pt is the highest-mAP checkpoint from training — always use this
#      over last.pt for inference
model = YOLO('/workspace/runs/karen_ocr_v1/weights/best.pt')

# VARIABLE DECLARATION — path to the folder containing validation images
valid_dir = '/root/karen_dataset_yolov8/valid/images/'

# FUNCTION CALL + INDEX/SLICE — lists all files in valid_dir and takes the first one
# WHY: gives us a real Karen syllable image without hardcoding a filename
test_image = os.path.join(valid_dir, os.listdir(valid_dir)[0])

# METHOD CALL — runs inference on the test image with 40% confidence threshold
# ARGUMENT — conf=0.4 means detections below 40% confidence are discarded
# WHY: 0.4 is a balanced threshold — low enough to catch real syllables,
#      high enough to suppress false positives
results = model(test_image, conf=0.4)

# METHOD CALL — saves the annotated detection image to disk with bounding boxes drawn
# WHY: provides visual proof of what the model detected for local documentation
results[0].save('/root/karen_lang_trans/test_result.jpg')

# OUTPUT/PRINT — prints how many Karen syllables were found in this image
print(f"Detected: {len(results[0].boxes)} Karen syllables")

# LOOP — iterates over every bounding box detection in the result
for box in results[0].boxes:
    # VARIABLE DECLARATION — converts the detection tensor to a plain Python integer
    # WHY: box.cls is a PyTorch tensor; int() extracts the numeric class index
    cls_idx = int(box.cls)

    # METHOD CALL — looks up the class name using .get() with a safe fallback
    # ARGUMENT — f'unknown_{cls_idx}' prints instead of crashing if index missing
    # WHY: model.names is the authoritative dictionary baked into the weights file
    cls_name = model.names.get(cls_idx, f'unknown_{cls_idx}')

    # OUTPUT/PRINT — displays class index, Roboflow label name, and confidence
    print(f"  Class {cls_idx} = '{cls_name}' — {float(box.conf):.1%} confidence")
