# ============================================================
# FILE: verify_dataset_integrity.py
# PURPOSE: Confirms that every image in train/ and valid/ has
#          a matching label file and vice versa. Catches missing
#          annotations before training so YOLO doesn't silently
#          skip unpaired files and undercount your dataset.
# PIPELINE POSITION: Pre-training health check
# REQUIRES: train/images/, train/labels/, valid/images/, valid/labels/
# PRODUCES: Terminal report showing counts and any mismatches found
# ============================================================

# IMPORT — provides filesystem utilities for listing and path operations
import os

# FUNCTION DEFINITION — checks one split (train or valid) for pairing issues
# PARAMETER — img_dir: the path to the images folder for this split
# PARAMETER — lbl_dir: the path to the labels folder for this split
# PARAMETER — split_name: a label string ("train" or "valid") for display
def check_split(img_dir, lbl_dir, split_name):
    # METHOD CALL — gets all image filenames from the images folder
    # WHY: we use set comprehension so we can do fast set-difference checks
    img_stems = set(
        os.path.splitext(f)[0]
        for f in os.listdir(img_dir)
        if f.endswith(('.jpg', '.jpeg', '.png'))
    )

    # METHOD CALL — gets all label filenames (without extension) from labels folder
    lbl_stems = set(
        os.path.splitext(f)[0]
        for f in os.listdir(lbl_dir)
        if f.endswith('.txt')
    )

    # VARIABLE DECLARATION — images that have no matching label file
    # WHY: YOLO will treat these as background-only images during training
    imgs_without_labels = img_stems - lbl_stems

    # VARIABLE DECLARATION — label files that have no matching image
    # WHY: these are orphaned annotations — YOLO will error or skip them
    labels_without_imgs = lbl_stems - img_stems

    # OUTPUT/PRINT — section header for this split
    print(f"\n--- {split_name.upper()} ---")
    print(f"  Images : {len(img_stems)}")
    print(f"  Labels : {len(lbl_stems)}")

    # CONDITIONAL — reports images missing labels
    if imgs_without_labels:
        print(f"  ⚠ {len(imgs_without_labels)} images have NO label file:")
        for name in sorted(imgs_without_labels)[:5]:
            print(f"    {name}")
    else:
        print(f"  ✓ All images have matching label files")

    # CONDITIONAL — reports orphaned label files
    if labels_without_imgs:
        print(f"  ⚠ {len(labels_without_imgs)} labels have NO image file:")
        for name in sorted(labels_without_imgs)[:5]:
            print(f"    {name}")
    else:
        print(f"  ✓ All label files have matching images")

# FUNCTION CALL — checks the training split
check_split(
    '/root/karen_dataset_yolov8/train/images/',
    '/root/karen_dataset_yolov8/train/labels/',
    'train'
)

# FUNCTION CALL — checks the validation split
check_split(
    '/root/karen_dataset_yolov8/valid/images/',
    '/root/karen_dataset_yolov8/valid/labels/',
    'valid'
)
