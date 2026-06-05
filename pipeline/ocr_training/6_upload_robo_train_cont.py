#!/usr/bin/env python3
import os
"""
6_upload_and_train.py
Karen OCR â€” Upload karendataset to Roboflow and kick off Accurate training.

Install requirements first:
    pip install roboflow

Then set ROBOFLOW_API_KEY in your shell and run:
    python 6_upload_and_train.py
"""

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  CONFIGURATION - set ROBOFLOW_API_KEY before running
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

API_KEY = os.environ.get("ROBOFLOW_API_KEY", "")

WORKSPACE_ID     = "sgaw-perception"
PROJECT_ID       = "sgaw-perception"
NEW_VERSION_NAME = "1_karen_ocr_data"
TRAIN_SPEED      = "accurate"           # "accurate" = Roboflow 3.0 Accurate subtype

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  IMPORTS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

import sys
import time
from pathlib import Path
from roboflow import Roboflow

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  PATHS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

DATASET_DIR  = Path("karendataset")
CLASSES_FILE = Path("roboflow_classes.txt")
DATA_YAML    = Path("data.yaml")
SPLITS       = ["train", "valid", "test"]

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  PRE-FLIGHT CHECKS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def preflight():
    if not API_KEY:
        print("ERROR: You have not filled in your API key.")
        print("Set ROBOFLOW_API_KEY in your shell before running.")
        sys.exit(1)

    missing = []
    for path in [DATASET_DIR, CLASSES_FILE, DATA_YAML]:
        if not path.exists():
            missing.append(str(path))
    if missing:
        print("ERROR: Required paths not found:")
        for m in missing:
            print("  " + m)
        print("Run 1_karen_dataset_gen.py first to generate the dataset.")
        sys.exit(1)

    for split in SPLITS:
        img_dir = DATASET_DIR / split / "images"
        lbl_dir = DATASET_DIR / split / "labels"
        if not img_dir.exists() or not lbl_dir.exists():
            print("ERROR: Missing split folder: " + split)
            sys.exit(1)

    print("Pre-flight checks passed.")


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  COUNT HELPERS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def count_images(split_name):
    d = DATASET_DIR / split_name / "images"
    return len(list(d.glob("*.jpg"))) + len(list(d.glob("*.png")))


def total_images():
    return sum(count_images(s) for s in SPLITS)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  UPLOAD â€” iterates every image+label pair across all splits
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def upload_dataset(project):
    print("\nStarting upload...")
    print("Total images to upload: " + str(total_images()))
    print("This will take a while. Do not close the terminal.\n")

    uploaded   = 0
    skipped    = 0
    errors     = []
    start_time = time.time()

    for split in SPLITS:
        img_dir = DATASET_DIR / split / "images"
        lbl_dir = DATASET_DIR / split / "labels"

        image_files = sorted(list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")))
        split_total = len(image_files)

        print("Uploading split: " + split + "  (" + str(split_total) + " images)")

        for i, img_path in enumerate(image_files):

            if uploaded + skipped < 19926:
                skipped += 1
                continue

            lbl_path = lbl_dir / (img_path.stem + ".txt")

            if not lbl_path.exists():
                skipped += 1
                continue

            try:
                project.upload(
                    image_path=str(img_path),
                    annotation_path=str(lbl_path),
                    split=split,
                    num_retry_uploads=3,
                    batch_name=NEW_VERSION_NAME
                )
                uploaded += 1
            except Exception as e:
                errors.append({"file": img_path.name, "error": str(e)})

            if (i + 1) % 500 == 0 or i + 1 == split_total:
                elapsed = int(time.time() - start_time)
                rate = uploaded / elapsed if elapsed > 0 else 0
                print(
                    "  " + split + ": " + str(i + 1) + "/" + str(split_total) +
                    "  |  total uploaded: " + str(uploaded) +
                    "  |  " + str(round(rate, 1)) + " img/s"
                )

    print("\nUpload complete.")
    print("  Uploaded : " + str(uploaded))
    print("  Skipped  : " + str(skipped) + "  (missing label file)")
    print("  Errors   : " + str(len(errors)))

    if errors:
        print("\nFirst 10 errors:")
        for e in errors[:10]:
            print("  " + e["file"] + " â€” " + e["error"])

    return uploaded, errors


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  GENERATE DATASET VERSION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def generate_version(project):
    print("\nGenerating dataset version: " + NEW_VERSION_NAME)
    print("This creates the versioned snapshot Roboflow will train on.")

    version = project.generate_version(
        settings={
            "preprocessing": {
                "auto-orient": True,
                "resize": {"enabled": True, "width": 640, "height": 640, "format": "Stretch to"}
            },
            "augmentation": {}
        }
    )

    print("Dataset version created.")
    return version


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TRAIN
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def start_training(version):
    print("\nStarting Roboflow 3.0 Object Detection (Accurate) training...")
    print("Speed setting: " + TRAIN_SPEED)
    print("This will run on Roboflow's cloud. You can close this terminal once training starts.")
    print("Monitor progress at: https://app.roboflow.com/" + WORKSPACE_ID + "/" + PROJECT_ID)

    version.train(speed=TRAIN_SPEED)

    print("\nTraining job submitted successfully.")
    print("Roboflow will email you when training completes.")
    print("Compare results against checkpoint sgaw-perception/19 (88.7% mAP@50).")


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  MAIN
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def main():
    print("=== Karen OCR â€” Roboflow Upload + Train ===")
    print("Workspace : " + WORKSPACE_ID)
    print("Project   : " + PROJECT_ID)
    print("Version   : " + NEW_VERSION_NAME)
    print("Speed     : " + TRAIN_SPEED)
    print()

    preflight()

    print("\nConnecting to Roboflow...")
    rf = Roboflow(api_key=API_KEY)

    workspace = rf.workspace()
    project   = workspace.project(PROJECT_ID)

    print("Connected. Project: " + str(project.name))
    print()

    uploaded, errors = upload_dataset(project)

    if uploaded == 0:
        print("\nERROR: Zero images uploaded. Check your dataset folder and label files.")
        sys.exit(1)

    if len(errors) > uploaded * 0.05:
        print("\nWARNING: More than 5% of uploads failed.")
        print("Proceeding anyway, but inspect errors above before training.")

    version = generate_version(project)
    start_training(version)

    print("\n=== ALL DONE ===")
    print("Dataset version  : " + NEW_VERSION_NAME)
    print("Training started : Roboflow 3.0 Accurate")
    print("Monitor at       : https://app.roboflow.com/" + WORKSPACE_ID + "/" + PROJECT_ID)


if __name__ == "__main__":
    main()
