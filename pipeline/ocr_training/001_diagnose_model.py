# ============================================================
# FILE: diagnose_model.py
# PURPOSE: Verify that data.yaml and the trained .pt model
#          agree on class count (nc). Run this any time you
#          suspect a mismatch between training config and weights.
# PIPELINE POSITION: Step 0 — Pre-flight check before inference
# REQUIRES: data.yaml, best.pt
# PRODUCES: Terminal output only (no files written)
# ============================================================

# IMPORT — brings in the yaml library for reading .yaml config files
import yaml

# IMPORT — brings in the YOLO class from Ultralytics for loading model weights
from ultralytics import YOLO

# FILE OPERATION — opens data.yaml in read mode so we can inspect its contents
with open('/root/karen_dataset_yolov8/data.yaml', 'r') as f:
    # METHOD CALL — parses the YAML text into a Python dictionary
    cfg = yaml.safe_load(f)

# OUTPUT/PRINT — prints the nc value declared inside data.yaml
# WHY: nc must equal 6341 (our clean 2026 paradigm syllable count)
print(f"data.yaml nc      : {cfg.get('nc')}")

# OUTPUT/PRINT — prints how many entries are in the names list
# WHY: len(names) must match nc exactly or YOLO will silently misalign labels
print(f"data.yaml names   : {len(cfg['names'])} classes")

# OUTPUT/PRINT — prints the last class name in the list
# WHY: confirms the list ends at the right place and wasn't truncated
print(f"Last class name   : {cfg['names'][-1]}")

# INSTANTIATION — loads the trained model weights file into memory
# WHY: we need to read the nc baked INTO the weights, not just the yaml
model = YOLO('/workspace/runs/karen_ocr_v1/weights/best.pt')

# OUTPUT/PRINT — prints the class count stored inside the model weights
# WHY: this is the authoritative number — if it differs from data.yaml nc,
#      detections will map to wrong syllables
print(f"Model nc          : {model.model.nc}")

# OUTPUT/PRINT — prints how many names the model carries internally
print(f"Model names count : {len(model.names)}")

# METHOD CALL — safely looks up index 8639 in the model name dictionary
# ARGUMENT — 'NOT FOUND' is the fallback if the index doesn't exist
# WHY: 8639 is a CLASS NAME (Roboflow numeric label), not an index.
#      If this returns NOT FOUND it confirms the model has 6341 classes only.
print(f"Class 8639 name   : {model.names.get(8639, 'NOT FOUND')}")
