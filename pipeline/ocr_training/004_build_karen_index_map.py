# ============================================================
# FILE: build_karen_index_map.py
# PURPOSE: Reads data.yaml and creates karen_index_map.json —
#          a permanent lookup table that translates every YOLO
#          class index (0-6340) to its Roboflow string label.
#          This is the first bridge in the translation chain.
# PIPELINE POSITION: Step 2 — Build index→label bridge
# REQUIRES: /root/karen_dataset_yolov8/data.yaml
# PRODUCES: /root/karen_lang_trans/karen_index_map.json
# ============================================================

# IMPORT — provides json.dump() for saving the map as a JSON file
import json

# IMPORT — provides yaml.safe_load() for reading the YOLO config file
import yaml

# FILE OPERATION — opens the YOLO dataset config in read mode
# WHY: data.yaml contains the ordered list of 6341 class names that
#      YOLO used during training — the order defines the index mapping
with open('/root/karen_dataset_yolov8/data.yaml', 'r') as f:
    # METHOD CALL — parses YAML text into a Python dictionary
    cfg = yaml.safe_load(f)

# VARIABLE DECLARATION — extracts the ordered list of class name strings
# WHY: position 0 in this list = YOLO class index 0, position 1 = index 1, etc.
names = cfg['names']

# VARIABLE DECLARATION — dict comprehension building the index→name map
# WHY: enumerate() pairs each name with its position (the YOLO class index)
#      str(name) ensures all keys are strings for consistent JSON lookups
index_map = {i: str(name) for i, name in enumerate(names)}

# FILE OPERATION — opens the output file for writing with UTF-8 encoding
# WHY: UTF-8 is required so any Unicode Karen characters in class names
#      are written correctly to disk
with open('/root/karen_lang_trans/karen_index_map.json', 'w', encoding='utf-8') as f:
    # METHOD CALL — serializes the dictionary to JSON on disk
    # ARGUMENT — ensure_ascii=False preserves Unicode characters as-is
    # ARGUMENT — indent=2 makes the file human-readable in VS Code
    json.dump(index_map, f, ensure_ascii=False, indent=2)

# OUTPUT/PRINT — confirms how many entries were saved
print(f"Saved {len(index_map)} entries to karen_index_map.json")

# OUTPUT/PRINT — spot-checks the index we detected (5878 → '8639')
print(f"Example: index 5878 → '{index_map.get(5878)}'")

# OUTPUT/PRINT — spot-checks the first class
print(f"Example: index 0    → '{index_map.get(0)}'")

# OUTPUT/PRINT — spot-checks the last class
print(f"Example: index 6340 → '{index_map.get(6340)}'")
