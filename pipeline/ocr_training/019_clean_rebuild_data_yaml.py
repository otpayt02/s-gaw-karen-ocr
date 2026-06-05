#!/usr/bin/env python3
"""
019_clean_rebuild_data_yaml.py
PIPELINE POSITION: Step 2 of new-instance setup. Run AFTER 018_find_index_map.py.
PURPOSE: Reads data.yaml, removes all 2025-paradigm individual-component class names
         (vowel -ah, medial -r, tone2fall, yolo_sgaw_plural, etc.), resets nc to the
         pure 2026 count, and scrubs any matching label file annotation lines.
REQUIRES: /root/karenlangtrans/path_config.json (written by 018)
PRODUCES: Updated /root/karen_dataset_yolov8/data.yaml
          Updated label .txt files in train/ and valid/
          /root/karenlangtrans/019_cleanup_report.json
"""

import os
import glob
import json
import yaml

# VARIABLE DECLARATION: load the canonical paths from 018's output
CONFIG_PATH = '/root/karenlangtrans/path_config.json'

# FILE OPERATION: open and parse path_config.json written by 018
with open(CONFIG_PATH, 'r') as f:
    paths = json.load(f)

# VARIABLE DECLARATION: extract the data.yaml path from the config
data_yaml_path = paths['data_yaml']

print(f"Loading {data_yaml_path}...")

# FILE OPERATION: open and parse the YOLO dataset configuration file
with open(data_yaml_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

# VARIABLE DECLARATION: the full list of class names currently in data.yaml
names = cfg.get('names', [])

# VARIABLE DECLARATION: total class count before cleaning
original_count = len(names)
print(f"Total classes before cleanup: {original_count}")

# LIST/DICT/SET: keywords that identify 2025-paradigm individual-component class names
# Any class name containing one of these strings is a legacy class to remove
LEGACY_KEYWORDS = [
    'vowel', 'medial', 'tone', 'yolo_sgaw', 'plural',
    'hpuh', 'thuh', 'dtuh', 'hkuh', 'contraction',
    'wah guh', 'yah aw', 'yeh'
]

# LIST/DICT/SET: build a list of (index, name) tuples for all legacy classes
legacy_classes = [
    (i, n) for i, n in enumerate(names)
    if any(kw in str(n).lower() for kw in LEGACY_KEYWORDS)
]

print(f"Garbage 2025-paradigm classes found: {len(legacy_classes)}")
for i, n in legacy_classes[:20]:
    print(f"  [{i}] {n}")

# SET: build a set of legacy indices for O(1) lookup when cleaning label files
legacy_indices = {i for i, _ in legacy_classes}

# LIST/DICT/SET: rebuild the names list with only 2026 full-syllable classes
clean_names = [n for i, n in enumerate(names) if i not in legacy_indices]
clean_count = len(clean_names)

# VARIABLE DECLARATION: update the cfg dict in memory before writing back to disk
cfg['names'] = clean_names
cfg['nc'] = clean_count

# FILE OPERATION: write the cleaned data.yaml back to disk, preserving Unicode
with open(data_yaml_path, 'w', encoding='utf-8') as f:
    yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

print(f"data.yaml updated: {original_count} → {clean_count} classes")

# VARIABLE DECLARATION: counters for reporting how many label files were touched
removed_lines = 0
cleaned_files = 0
cleaned_file_list = []

# LOOP: process both train and valid label directories
for split in ['train', 'valid']:
    # VARIABLE DECLARATION: glob pattern to find all label txt files for this split
    label_dir = paths[f'{split}_labels']
    label_files = glob.glob(os.path.join(label_dir, '*.txt'))
    print(f"Scanning {len(label_files)} {split} label files...")

    # LOOP: process each individual label file
    for lf in label_files:
        # FILE OPERATION: read all annotation lines from this label file
        with open(lf, 'r') as f:
            lines = f.readlines()

        # LIST/DICT/SET: keep only annotation lines whose class index is NOT legacy
        # Each YOLO label line format: <class_index> <cx> <cy> <w> <h>
        clean_lines = [
            line for line in lines
            if len(line.split()) > 0 and int(line.split()[0]) not in legacy_indices
        ]

        # CONDITIONAL: only rewrite the file if something was actually removed
        if len(clean_lines) != len(lines):
            removed_lines += len(lines) - len(clean_lines)
            cleaned_files += 1
            cleaned_file_list.append(lf)
            # FILE OPERATION: write the cleaned lines back over the original file
            with open(lf, 'w') as f:
                f.writelines(clean_lines)

# VARIABLE DECLARATION: build a summary dict for the JSON report
report = {
    "original_class_count":   original_count,
    "legacy_classes_removed": len(legacy_classes),
    "final_class_count":      clean_count,
    "label_files_cleaned":    cleaned_files,
    "annotation_lines_removed": removed_lines,
    "legacy_class_names":     [n for _, n in legacy_classes],
    "cleaned_files":          cleaned_file_list,
}

# VARIABLE DECLARATION: output path for the cleanup report
report_path = '/root/karenlangtrans/019_cleanup_report.json'

# FILE OPERATION: write the cleanup report so you have a permanent record
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

# OUTPUT/PRINT: final summary for terminal confirmation
print(f"Original class count : {original_count}")
print(f"Garbage classes removed: {len(legacy_classes)}")
print(f"Final class count    : {clean_count}")
print(f"Label files cleaned  : {cleaned_files}")
print(f"Annotation lines removed: {removed_lines}")
print(f"Report saved to      : {report_path}")
print(f"data.yaml updated    : {data_yaml_path}")
print("019 COMPLETE — ready to retrain with clean dataset")
