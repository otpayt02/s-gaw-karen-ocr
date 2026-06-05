# ============================================================
# FILE: build_bootstrap_dictionary.py
# PURPOSE: Creates karendictdatabase.json with one entry per
#          Karen syllable class. English translations start as
#          placeholders ("no translation yet") and get filled
#          in later by 2_build_dict_data.py parsing the PDF.
#          This file makes the pipeline runnable immediately
#          before the PDF parser is complete.
# PIPELINE POSITION: Step 3 — Bootstrap translation database
# REQUIRES: /root/karen_dataset_yolov8/data.yaml
# PRODUCES: /root/karen_lang_trans/karendictdatabase.json
# ============================================================

# IMPORT — provides json serialization for saving the dictionary
import json

# IMPORT — provides os.makedirs() for creating the output folder safely
import os

# IMPORT — provides yaml.safe_load() for reading the YOLO config
import yaml

# FUNCTION CALL — creates the output directory if it doesn't exist yet
# ARGUMENT — exist_ok=True prevents crashing if the folder already exists
# WHY: /root/karen_lang_trans/ must exist before we write any files into it
os.makedirs('/root/karen_lang_trans', exist_ok=True)

# FILE OPERATION — reads the YOLO dataset configuration file
with open('/root/karen_dataset_yolov8/data.yaml', 'r') as f:
    # METHOD CALL — converts YAML text to a Python dictionary
    cfg = yaml.safe_load(f)

# VARIABLE DECLARATION — the ordered list of 6341 Roboflow class name strings
names = cfg['names']

# VARIABLE DECLARATION — empty dictionary that will hold all syllable entries
karen_dict = {}

# LOOP — iterates over every class name string from data.yaml
for name in names:
    # LIST/DICT/SET — creates one dictionary entry per syllable with 3 fields:
    # 'syllable': the romanized name (populated later by populate_dict_from_filenames.py)
    # 'english':  placeholder until 2_build_dict_data.py parses the Karen PDF dictionary
    # 'unicode':  Karen Unicode string (empty until PDF parser runs)
    # WHY: this structure lets the pipeline run end-to-end immediately while
    #      real translations are filled in incrementally
    karen_dict[str(name)] = {
        "syllable": str(name),
        "english":  "no translation yet",
        "unicode":  ""
    }

# VARIABLE DECLARATION — full output path for the dictionary file
out_path = '/root/karen_lang_trans/karendictdatabase.json'

# FILE OPERATION — opens output file for writing with UTF-8 encoding
with open(out_path, 'w', encoding='utf-8') as f:
    # METHOD CALL — writes the full dictionary to disk as formatted JSON
    # ARGUMENT — ensure_ascii=False preserves Karen Unicode characters
    # ARGUMENT — indent=2 keeps the file readable in VS Code
    json.dump(karen_dict, f, ensure_ascii=False, indent=2)

# OUTPUT/PRINT — confirms total entries saved
print(f"Built bootstrap dictionary: {len(karen_dict)} entries")

# OUTPUT/PRINT — confirms the file path
print(f"Saved to: {out_path}")

# OUTPUT/PRINT — shows an example entry so we can verify the structure
print(f"Example entry: {json.dumps(karen_dict[str(names[0])], indent=2)}")
