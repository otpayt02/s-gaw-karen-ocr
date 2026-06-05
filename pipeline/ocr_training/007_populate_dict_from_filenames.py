# ============================================================
# FILE: populate_dict_from_filenames.py
# PURPOSE: Extracts real romanized Karen syllable names from
#          YOLO label filenames and writes them into
#          karendictdatabase.json. After this runs, every
#          detection shows "uh_medgha_u_t6" instead of "8639".
#          This is the bridge between numeric Roboflow labels
#          and human-readable Karen syllable romanization.
# PIPELINE POSITION: Step 5 — Populate dictionary with real names
# REQUIRES: train/labels/, valid/labels/, karen_index_map.json,
#           karendictdatabase.json (bootstrap version)
# PRODUCES: karendictdatabase.json (updated with syllable names)
# ============================================================

# IMPORT — json for reading and writing the dictionary files
import json

# IMPORT — os for filesystem navigation across label folders
import os

# IMPORT — yaml for reading data.yaml class name list
import yaml

# VARIABLE DECLARATION — list of both label directories to scan
# WHY: syllable names are encoded in filenames across both train and valid sets
label_dirs = [
    '/root/karen_dataset_yolov8/train/labels/',
    '/root/karen_dataset_yolov8/valid/labels/'
]

# VARIABLE DECLARATION — matching image directories (parallel to label_dirs)
# WHY: label files share the same base filename as their image counterparts
img_dirs = [
    '/root/karen_dataset_yolov8/train/images/',
    '/root/karen_dataset_yolov8/valid/images/'
]

# VARIABLE DECLARATION — empty dict that will map YOLO class index → syllable name
# WHY: we build this by reading label files + their filenames together
class_to_syllable = {}

# LOOP — iterates over both label/image directory pairs simultaneously
for lbl_dir, img_dir in zip(label_dirs, img_dirs):
    # LOOP — iterates over every file in this label directory
    for lbl_file in os.listdir(lbl_dir):
        # CONDITIONAL — skips any file that is not a YOLO annotation .txt file
        if not lbl_file.endswith('.txt'):
            continue

        # VARIABLE DECLARATION — builds full path to this label file
        lbl_path = os.path.join(lbl_dir, lbl_file)

        # FILE OPERATION — reads all lines from the label file
        # WHY: each line is one annotation; the first number is the class index
        with open(lbl_path, 'r') as f:
            lines = f.readlines()

        # CONDITIONAL — skips empty label files (images with no annotations)
        if not lines:
            continue

        # INDEX/SLICE + METHOD CALL — extracts class index from first annotation line
        # WHY: YOLO label format is "class_idx x_center y_center width height"
        #      split()[0] gets the class index, int() converts it, str() makes it
        #      a string key for dictionary lookup
        cls_idx = str(int(lines[0].split()[0]))

        # VARIABLE DECLARATION — removes .txt extension to get the base image name
        img_base = lbl_file.replace('.txt', '')

        # METHOD CALL — splits the filename on underscores into a list of parts
        # WHY: filenames are structured as "syllable_parts_UUID_rf_hash.jpg"
        #      e.g. "uh_medgha_u_t6_a6f11605_jpg_rf_XxcoViy..."
        parts = img_base.split('_')

        # VARIABLE DECLARATION — finds where the Roboflow UUID hash starts
        # WHY: the UUID is always 8 alphanumeric characters; everything before it
        #      is the syllable name we want to extract
        uuid_pos = next(
            (i for i, p in enumerate(parts) if len(p) == 8 and p.isalnum()),
            None
        )

        # CONDITIONAL — joins only the pre-UUID parts back into the syllable name
        # WHY: rejoining with _ reconstructs "uh_medgha_u_t6" from the split list
        syl_name = '_'.join(parts[:uuid_pos]) if uuid_pos else img_base

        # VARIABLE DECLARATION — stores the mapping from class index to syllable name
        class_to_syllable[cls_idx] = syl_name

# OUTPUT/PRINT — confirms how many unique classes were successfully mapped
print(f"Mapped {len(class_to_syllable)} unique classes to syllable names")

# FILE OPERATION — loads the index→Roboflow label bridge
with open('/root/karen_lang_trans/karen_index_map.json', 'r') as f:
    index_map = json.load(f)

# FILE OPERATION — loads the current (bootstrap) dictionary
with open('/root/karen_lang_trans/karendictdatabase.json', 'r') as f:
    karen_dict = json.load(f)

# VARIABLE DECLARATION — counter for tracking how many entries get updated
updated = 0

# LOOP — iterates over every class index → syllable name pair we collected
for cls_idx, syl_name in class_to_syllable.items():
    # METHOD CALL — translates the YOLO index to the Roboflow string label
    roboflow_label = index_map.get(cls_idx, '')

    # CONDITIONAL — only updates if both the label exists and is in the dictionary
    if roboflow_label and roboflow_label in karen_dict:
        # VARIABLE DECLARATION — overwrites the placeholder syllable name
        # WHY: replaces "0" or the numeric Roboflow label with the real romanized name
        karen_dict[roboflow_label]['syllable'] = syl_name
        # VARIABLE DECLARATION — increments the counter
        updated += 1

# FILE OPERATION — saves the updated dictionary back to disk
with open('/root/karen_lang_trans/karendictdatabase.json', 'w', encoding='utf-8') as f:
    json.dump(karen_dict, f, ensure_ascii=False, indent=2)

# OUTPUT/PRINT — confirms how many entries received real syllable names
print(f"Updated {updated} dictionary entries with real syllable names")
print(f"\nVerification — our 5 known detections:")

# LOOP — spot-checks the exact 5 Roboflow labels from our first pipeline run
for label in ['8639', '7916', '4316', '8497', '5016']:
    # OUTPUT/PRINT — shows each Roboflow label alongside its new romanized syllable name
    print(f"  class '{label}' → syllable '{karen_dict[label]['syllable']}'")
