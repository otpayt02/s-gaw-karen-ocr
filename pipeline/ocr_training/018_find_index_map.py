#!/usr/bin/env python3
"""
018_find_index_map.py
PIPELINE POSITION: Step 1 of any new-instance setup. Run this FIRST before 019 or 020.
PURPOSE: Scans the entire server filesystem for karen_index_map.json (which may be at
         different paths on different vast.ai instances), verifies it, and writes
         /root/karenlangtrans/path_config.json so all downstream scripts know where everything is.
REQUIRES: Nothing — standalone script, no prior files needed.
PRODUCES: /root/karenlangtrans/path_config.json
"""

import os
import json

# VARIABLE DECLARATION: the directory where this project's scripts live
PROJECT_DIR = '/root/karenlangtrans'

# VARIABLE DECLARATION: the target filename to search for across the whole server
TARGET_FILE = 'karen_index_map.json'

# FUNCTION DEFINITION: recursively scan filesystem for a filename, skipping
# noisy system directories (/proc, /sys, /dev) that would cause permission errors
def find_file(filename, search_root='/'):
    matches = []
    skip_dirs = {'/proc', '/sys', '/dev', '/run', '/snap'}
    for dirpath, dirnames, filenames in os.walk(search_root, onerror=lambda e: None):
        # INDEX/SLICE: remove skip_dirs entries from dirnames in-place so os.walk
        # does not descend into them
        dirnames[:] = [d for d in dirnames
                       if os.path.join(dirpath, d) not in skip_dirs]
        if filename in filenames:
            matches.append(os.path.join(dirpath, filename))
    return matches

print(f"Searching for {TARGET_FILE} across server filesystem...")

# FUNCTION CALL: scan from filesystem root, returns a list of all found paths
found_paths = find_file(TARGET_FILE)

# CONDITIONAL: handle three outcomes — not found, found once, found multiple times
if not found_paths:
    print(f"NOT FOUND: {TARGET_FILE} does not exist on this server.")
    print("You must either:")
    print("  1. scp it from your old server instance using local Windows CMD, OR")
    print("  2. Re-run the index map builder heredoc from the server log.")
    raise SystemExit(1)

# VARIABLE DECLARATION: prefer the path inside /root/karen_dataset_yolov8 or /root if multiple
if len(found_paths) > 1:
    print(f"Multiple matches found:")
    for p in found_paths:
        print(f"  {p}")
    # INDEX/SLICE: pick the shortest (most root-level) path as the primary
    index_map_path = sorted(found_paths, key=len)[0]
    print(f"Using shortest path: {index_map_path}")
else:
    index_map_path = found_paths[0]
    print(f"  FOUND: {index_map_path}")

# FILE OPERATION: load the index map to verify it is valid JSON and count entries
with open(index_map_path, 'r', encoding='utf-8') as f:
    index_map = json.load(f)

# VARIABLE DECLARATION: total number of syllable classes found in the map
total_classes = len(index_map)
print(f"Using: {index_map_path}")
print(f"Total classes mapped: {total_classes}")

# OUTPUT/PRINT: show a few sample entries for a human sanity check
sample_keys = list(index_map.keys())[:3]
sample = {k: index_map[k] for k in sample_keys}
print(f"Sample entries: {sample}")

# VARIABLE DECLARATION: canonical paths for all key project files on this instance
path_config = {
    "karen_index_map":   index_map_path,
    "data_yaml":         "/root/karen_dataset_yolov8/data.yaml",
    "train_images":      "/root/karen_dataset_yolov8/train/images",
    "train_labels":      "/root/karen_dataset_yolov8/train/labels",
    "valid_images":      "/root/karen_dataset_yolov8/valid/images",
    "valid_labels":      "/root/karen_dataset_yolov8/valid/labels",
    "best_weights":      "/workspace/runs/karen_ocr_v3_clean/weights/best.pt",
    "font_path":         "/root/karenlangtrans/padauk-regular.ttf",
    "project_dir":       PROJECT_DIR,
}

# VARIABLE DECLARATION: output path for the config file all downstream scripts will read
config_out = os.path.join(PROJECT_DIR, 'path_config.json')

# FILE OPERATION: write path_config.json so 019, 020, and all future scripts
# can import their paths from one authoritative location instead of hardcoding them
os.makedirs(PROJECT_DIR, exist_ok=True)
with open(config_out, 'w', encoding='utf-8') as f:
    json.dump(path_config, f, indent=2, ensure_ascii=False)

print(f"path_config.json written to {config_out}")
print("All downstream scripts (019+) will load paths from this file.")
print("018 COMPLETE")
