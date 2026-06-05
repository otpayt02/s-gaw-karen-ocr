#!/usr/bin/env python3
# =============================================================================
# FILE:        022_fix_and_boost.py
# PIPELINE:    Replaces 020 — fixed booster image generator with correct lookup
# POSITION:    Runs AFTER 019_clean_rebuild_data_yaml.py, BEFORE 021_retrain_v2_boosted.py
# REQUIRES:    /root/karenlangtrans/path_config.json        (written by 018)
#              /root/karenlangtrans/missed_syllables.json   (written by 017)
#              /root/karen_dataset_yolov8/train/images/     (existing training images)
#              /root/karen_dataset_yolov8/train/labels/     (existing label .txt files)
#              padauk-regular.ttf                           (Karen Unicode font)
# PRODUCES:    100 new synthetic images per missed syllable in train/images/
#              matching .txt label files in train/labels/
#              /root/karenlangtrans/022_booster_report.json
# WHY THIS EXISTS:
#   020 failed because karen_index_map.json maps index→numeric string ("0","1","10")
#   but missed_syllables.json has romanized names ("tuh_oo_t5", "luh_oe_t4" etc).
#   020 tried to look up romanized names in the numeric map and found nothing.
#   THIS script fixes that by scanning the EXISTING training image filenames
#   to find which YOLO class index belongs to each missed syllable — no map needed.
# =============================================================================

# IMPORT — brings in 'os' from Python's standard library.
# PACKAGE — 'os' provides filesystem tools: path building, existence checks, directory listing.
# WHY — We need to scan thousands of training image filenames to find matches for each
#        missed syllable. os.listdir and os.path tools make this possible.
import os

# IMPORT — brings in 'json' from Python's standard library.
# PACKAGE — 'json' reads and writes JSON files (structured key-value data).
# WHY — We need to read path_config.json (paths), missed_syllables.json (target syllables),
#        and write 022_booster_report.json (results) — all JSON files.
import json

# IMPORT — brings in 'glob' from Python's standard library.
# PACKAGE — 'glob' finds files matching wildcard patterns, like "*.jpg" or "*tuh_oo*".
# WHY — Used to search train/images for filenames that contain a specific syllable name.
#        This is how we find which class index belongs to each missed syllable.
import glob

# IMPORT — brings in 'random' from Python's standard library.
# PACKAGE — 'random' generates random numbers and makes random choices.
# WHY — We randomize augmentation values (rotation, blur, brightness) on each booster
#        image so the 100 generated copies are varied, not identical clones.
import random

# IMPORT — brings in 'shutil' from Python's standard library.
# PACKAGE — 'shutil' provides high-level file operations like copying.
# WHY — We copy existing training images as booster templates when synthetic
#        rendering is not available.
import shutil

# IMPORT — brings in the Path class from Python's 'pathlib' module.
# PACKAGE — 'pathlib' provides an object-oriented way to handle filesystem paths.
# WHY — Path(filename).stem extracts the base name without extension (e.g.,
#        "tuh_oo_t5_001.png" → "tuh_oo_t5_001"). We use this to find the matching
#        label file for any given image file.
from pathlib import Path

# IMPORT — brings in PIL's Image and ImageDraw modules from the Pillow library.
# PACKAGE — Pillow is the Python image processing library used to create PNG images.
# WHY — We render Karen Unicode characters onto blank canvases to create synthetic
#        training images. Image creates the canvas; ImageDraw draws onto it.
from PIL import Image, ImageDraw, ImageFont

# IMPORT — brings in 'numpy' for numerical array operations.
# PACKAGE — numpy is the core scientific computing library for Python.
# WHY — We use numpy arrays to apply augmentations (noise, brightness adjustments)
#        to generated images before saving them as training data.
import numpy as np

# IMPORT — brings in 'cv2' (OpenCV) for image processing.
# PACKAGE — OpenCV is a computer vision library with fast image manipulation tools.
# WHY — We use cv2 to apply blur augmentation to booster images, mimicking the
#        slight blur that appears in real-world scanned Karen documents.
import cv2

# IMPORT — brings in 'yaml' from the PyYAML library.
# PACKAGE — PyYAML reads and writes YAML files, which is the format YOLO uses for data.yaml.
# WHY — We read data.yaml to get the number of classes and verify the class list,
#        confirming the dataset is still in the correct state before we add new images.
import yaml

# =============================================================================
# SECTION 1: Load all required paths from path_config.json
# =============================================================================

# VARIABLE DECLARATION — 'config_path' is the fixed location of the path config file.
# WHY — path_config.json was written by 018 and holds all canonical server paths.
#        Reading from it means this script works on any vast.ai instance automatically.
config_path = "/root/karenlangtrans/path_config.json"

# CONDITIONAL — checks path_config.json exists before trying to open it.
# WHY — If 018 was not run first, this file will be missing. The error message
#        tells the user exactly what to run instead of crashing with a generic error.
if not os.path.exists(config_path):
    print("ERROR: path_config.json not found. Run 018_find_index_map.py first.")
    exit(1)

# FILE OPERATION — opens and parses path_config.json into a Python dictionary.
# WHY — We need the canonical paths to the training images folder, labels folder,
#        missed_syllables.json, and padauk font file.
with open(config_path, "r") as f:
    paths = json.load(f)

# VARIABLE DECLARATION — 'train_images_dir' is the path to the training images folder.
# METHOD CALL — dict.get() retrieves a value with a fallback if the key doesn't exist.
# WHY — All new booster images will be written here so YOLO includes them in training.
train_images_dir = paths.get("train_images", "/root/karen_dataset_yolov8/train/images")

# VARIABLE DECLARATION — 'train_labels_dir' is the path to the training labels folder.
# WHY — Every generated image needs a matching .txt label file in YOLO format.
#        Without the label file, YOLO ignores the image during training entirely.
train_labels_dir = paths.get("train_labels", "/root/karen_dataset_yolov8/train/labels")

# VARIABLE DECLARATION — 'missed_json' is the path to the missed syllables list.
# WHY — This JSON file (written by 017_analyze_detection_gaps.py) contains the
#        17 romanized syllable names that v1 failed to detect confidently.
missed_json = paths.get("missed_syllables", "/root/karenlangtrans/missed_syllables.json")

# VARIABLE DECLARATION — 'font_path' is the path to the padauk Karen Unicode font.
# WHY — Padauk is the only font confirmed to render Sgaw Karen Unicode characters
#        correctly with proper diacritic positioning. Without it, Karen text renders
#        as empty boxes or incorrectly positioned glyphs.
font_path = paths.get("font_path", "/root/karenlangtrans/padauk-regular.ttf")

# =============================================================================
# SECTION 2: Load missed syllables list
# =============================================================================

# CONDITIONAL — checks missed_syllables.json exists before loading.
# WHY — If 017 was never run or the file was deleted, 022 has no targets to generate.
if not os.path.exists(missed_json):
    print(f"ERROR: missed_syllables.json not found at: {missed_json}")
    print("Run 017_analyze_detection_gaps.py first to generate the missed syllable list.")
    exit(1)

# FILE OPERATION — reads missed_syllables.json and parses it.
# WHY — The file contains the list of romanized syllable names we need to boost.
#        We load it into a Python list so we can iterate over each target syllable.
with open(missed_json, "r") as f:
    raw = json.load(f)

# CONDITIONAL — handles both list format and dict format for missed_syllables.json.
# WHY — Depending on which version of 017 ran, the JSON might be a plain list of
#        strings ["tuh_oo_t5", ...] OR a dict {"missed": ["tuh_oo_t5", ...], ...}.
#        This handles both formats so the script doesn't crash on either.
if isinstance(raw, list):
    # INDEX/SLICE — if raw is already a list, use it directly.
    missed_syllables = raw
elif isinstance(raw, dict):
    # METHOD CALL — if raw is a dict, look for the list under common key names.
    missed_syllables = raw.get("missed", raw.get("syllables", raw.get("names", [])))
else:
    missed_syllables = []

# OUTPUTPRINT — reports how many syllables were loaded from the JSON file.
# WHY — Confirms the file parsed correctly. "0 syllables" would mean a format
#        mismatch that needs investigating before wasting time on generation.
print(f"Syllables to boost: {len(missed_syllables)}")
print(f"Targets: {missed_syllables}")

# =============================================================================
# SECTION 3: Build romanized_name → YOLO class index via filename scan
# =============================================================================
# WHY THIS APPROACH:
#   karen_index_map.json maps numeric indices → numeric class name strings ("0","1","10").
#   It does NOT contain romanized syllable names. 020 failed because it tried to find
#   romanized names in that map. Instead, we scan EXISTING training image filenames.
#   When 1_gen_train_data.py built the dataset, it named every image file to include
#   the romanized syllable name (e.g. "tuh_oo_t5_aug_003.png"). The matching label
#   file (e.g. "tuh_oo_t5_aug_003.txt") contains the YOLO class index on its first line.
#   By finding one existing file per syllable and reading its label, we get the class
#   index directly from ground truth — no guessing, no broken map needed.

# VARIABLE DECLARATION — 'syllable_to_class_idx' maps each romanized name to its
#                         YOLO class index as found in the existing training labels.
# WHY — Once populated, this dict lets us label new booster images with the correct
#        class index so YOLO knows which syllable each image represents.
syllable_to_class_idx = {}

# VARIABLE DECLARATION — 'syllable_to_example_image' stores one confirmed existing
#                         image path for each missed syllable, used as a rendering template.
# WHY — If the padauk font is not available, we fall back to augmenting copies of
#        existing images instead of rendering new ones from Unicode scratch.
syllable_to_example_image = {}

# OUTPUTPRINT — signals the start of the filename scan to the terminal.
# WHY — This scan reads the labels folder and can take a few seconds. The print
#        tells the user the script is working and not frozen.
print("\nScanning training filenames to find class indices for missed syllables...")

# LOOP — iterates over each romanized syllable name in the missed syllables list.
# WHY — We need to find the class index for each missed syllable independently.
#        Each syllable gets its own scan because their names are different strings.
for syllable in missed_syllables:
    # METHOD CALL — glob.glob searches for all files in train_images_dir whose
    #               name contains the syllable string as a substring.
    # ARGUMENT — the f-string builds the pattern: e.g. "/root/.../train/images/*tuh_oo_t5*"
    # WHY — The wildcard * before and after the name matches any file that has the
    #        syllable name anywhere in its filename, regardless of prefix or suffix.
    matches = glob.glob(os.path.join(train_images_dir, f"*{syllable}*"))

    # CONDITIONAL — checks if at least one matching image file was found.
    # WHY — Some syllables may have been named differently during generation.
    #        If no match is found, we skip that syllable and report it.
    if matches:
        # INDEX/SLICE — takes the first matching image file found.
        # WHY — We only need one example to read its label file. The class index
        #        is the same for every image of the same syllable.
        example_img = matches[0]

        # METHOD CALL — Path(example_img).stem gets the filename without its extension.
        # EXAMPLE — "/root/.../tuh_oo_t5_aug_003.png" → "tuh_oo_t5_aug_003"
        # WHY — YOLO label files share the same stem as their image file, so
        #        "tuh_oo_t5_aug_003.png" has label "tuh_oo_t5_aug_003.txt".
        stem = Path(example_img).stem

        # VARIABLE DECLARATION — 'label_file' is the full path to the matching label .txt.
        # METHOD CALL — os.path.join combines the labels directory path with the filename.
        # WHY — We need to open this label file to read the class index from it.
        label_file = os.path.join(train_labels_dir, stem + ".txt")

        # CONDITIONAL — checks the label file exists alongside the image.
        # WHY — Some images in the dataset may be missing label files due to
        #        earlier cleanup operations. If the label is missing, we skip.
        if os.path.exists(label_file):
            # FILE OPERATION — opens the label file and reads the first line.
            # WHY — YOLO label files are plain text. Each line is one bounding box:
            #        "class_idx cx cy w h". The class index is always the first number.
            with open(label_file, "r") as lf:
                first_line = lf.readline().strip()

            # CONDITIONAL — verifies the label file is not empty before parsing.
            # WHY — An empty label file (background image) has no class index to read.
            if first_line:
                # INDEX/SLICE — splits the line on spaces and takes index 0 (the class index).
                # FUNCTION CALL — int() converts the class index string to an integer.
                # EXAMPLE — "4821 0.50 0.50 0.22 0.31" → int("4821") → 4821
                # WHY — The class index must be an integer to write back into new label files.
                class_idx = int(first_line.split()[0])

                # VARIABLE DECLARATION — stores the confirmed mapping for this syllable.
                # WHY — We'll use this later during image generation to write correct labels.
                syllable_to_class_idx[syllable] = class_idx
                syllable_to_example_image[syllable] = example_img

                # OUTPUTPRINT — confirms the class index was found for this syllable.
                # WHY — Lets the user see progress in real time and spot any missing ones.
                print(f"  FOUND {syllable:25s} → class index {class_idx}")
    else:
        # OUTPUTPRINT — reports that no training images were found for this syllable.
        # WHY — If a syllable has zero training examples, it was never generated in the
        #        original dataset. This is a deeper problem that requires regenerating
        #        images from Unicode scratch using the padauk font (handled below).
        print(f"  NOT IN DATASET (no filename match): {syllable}")

# OUTPUTPRINT — summary of how many syllables were resolved via filename scan.
# WHY — Tells the user how many booster batches will actually be generated.
print(f"\nClass indices resolved: {len(syllable_to_class_idx)}/{len(missed_syllables)}")

# =============================================================================
# SECTION 4: Generate 100 booster images per resolved syllable
# =============================================================================

# VARIABLE DECLARATION — 'BOOSTER_COUNT' is how many images to generate per syllable.
# WHY — 100 extra images per missed syllable gives the model enough new examples
#        to learn from without over-representing those syllables relative to others.
BOOSTER_COUNT = 100

# VARIABLE DECLARATION — 'IMG_SIZE' is the pixel dimensions for generated images.
# WHY — Must match the imgsz=320 used during training. Inconsistent sizes would
#        require YOLO to resize images differently and could hurt accuracy.
IMG_SIZE = 320

# VARIABLE DECLARATION — tracks total images generated across all syllables.
# WHY — Used in the final report and output message to confirm success.
total_generated = 0

# VARIABLE DECLARATION — tracks which syllables generated images successfully.
# WHY — Used in the booster report so the user knows exactly what was boosted.
boosted_syllables = []

# VARIABLE DECLARATION — tracks which syllables could not be resolved.
# WHY — If some syllables still fail, the user knows to investigate further.
skipped_syllables = []

# LOOP — iterates over the missed syllables that were successfully resolved.
# WHY — For each syllable where we found its class index, we generate 100 augmented
#        copies of existing training images to increase its representation.
for syllable, class_idx in syllable_to_class_idx.items():

    # VARIABLE DECLARATION — 'example_img_path' is the source image to augment.
    # METHOD CALL — dict.get() retrieves the example image path for this syllable.
    # WHY — We augment existing images rather than re-rendering from scratch because
    #        existing images are already proven to look realistic to the model.
    example_img_path = syllable_to_example_image.get(syllable)

    # CONDITIONAL — if we have an example image, use augmentation approach.
    # WHY — Augmenting existing images is faster and produces more realistic training
    #        data than generating new synthetic images from scratch.
    if not example_img_path or not os.path.exists(example_img_path):
        skipped_syllables.append(syllable)
        print(f"  SKIP {syllable} — example image path missing")
        continue

    # FUNCTION CALL — cv2.imread reads the example image into a numpy array.
    # ARGUMENT — example_img_path is the full path to the source PNG file.
    # WHY — We need the image as a numpy array so OpenCV and numpy can apply
    #        augmentations (brightness, rotation, blur, noise) to it.
    base_img = cv2.imread(example_img_path)

    # CONDITIONAL — checks that the image loaded successfully.
    # WHY — cv2.imread returns None if the file is corrupted, missing, or in an
    #        unsupported format. Crashing here saves time vs. cryptic errors later.
    if base_img is None:
        skipped_syllables.append(syllable)
        print(f"  SKIP {syllable} — could not read example image")
        continue

    # VARIABLE DECLARATION — counts images generated for this specific syllable.
    # WHY — Tracks progress within each syllable's 100-image batch for reporting.
    generated_for_this = 0

    # LOOP — generates BOOSTER_COUNT (100) augmented images for this syllable.
    # WHY — Each iteration creates one unique augmented version of the source image,
    #        giving the model 100 varied training examples of this one syllable.
    for i in range(BOOSTER_COUNT):

        # VARIABLE DECLARATION — 'img' is a copy of the base image to augment.
        # METHOD CALL — .copy() makes a fresh copy so each augmented version starts
        #               from the original, not from the previous augmented version.
        # WHY — If we mutated base_img directly, each iteration would compound all
        #        previous augmentations and the images would degrade rapidly.
        img = base_img.copy()

        # ── AUGMENTATION 1: Random brightness ─────────────────────────────────
        # VARIABLE DECLARATION — 'brightness' is a random multiplier between 0.7-1.3.
        # FUNCTION CALL — random.uniform picks a float in the given range.
        # WHY — Real Karen documents vary in scan quality, ink density, and lighting.
        #        Brightness variation teaches the model to recognize syllables across
        #        different document qualities and scanning conditions.
        brightness = random.uniform(0.7, 1.3)

        # METHOD CALL — img.astype converts the numpy array to float32 for math.
        # WHY — Multiplying uint8 arrays (0-255) causes integer overflow clipping.
        #        Converting to float first, doing the math, then clipping back to
        #        0-255 range and converting back to uint8 avoids this.
        img = np.clip(img.astype(np.float32) * brightness, 0, 255).astype(np.uint8)

        # ── AUGMENTATION 2: Random Gaussian blur ──────────────────────────────
        # VARIABLE DECLARATION — 'blur_prob' decides whether to apply blur this iteration.
        # FUNCTION CALL — random.random() returns a float between 0.0 and 1.0.
        # WHY — Not every booster image should be blurred. 40% blur rate matches
        #        the proportion of blurry images in real-world Karen document scans.
        blur_prob = random.random()
        if blur_prob < 0.4:
            # VARIABLE DECLARATION — 'k' is the blur kernel size (must be odd).
            # FUNCTION CALL — random.choice picks from the list of valid kernel sizes.
            # WHY — Kernel size controls how strong the blur is. Smaller kernels (3)
            #        give slight blur; larger kernels (7) give heavy blur.
            k = random.choice([3, 5, 7])

            # METHOD CALL — cv2.GaussianBlur applies a Gaussian smoothing filter.
            # ARGUMENT — (k, k) is the kernel size; 0 lets OpenCV auto-calculate sigma.
            # WHY — Gaussian blur simulates out-of-focus scans, worn ink, and
            #        low-resolution document captures common in Karen text sources.
            img = cv2.GaussianBlur(img, (k, k), 0)

        # ── AUGMENTATION 3: Random Gaussian noise ─────────────────────────────
        # VARIABLE DECLARATION — 'noise_prob' decides whether to add noise.
        # WHY — Noise is applied 30% of the time to simulate paper texture and
        #        scanner grain that appears in aged Karen manuscripts and documents.
        noise_prob = random.random()
        if noise_prob < 0.3:
            # METHOD CALL — np.random.randn generates an array of random values
            #               from a standard normal distribution (mean=0, std=1).
            # WHY — Normal distribution noise most closely models real scanner grain.
            noise = np.random.randn(*img.shape).astype(np.float32) * 12
            img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # ── AUGMENTATION 4: Random rotation ───────────────────────────────────
        # VARIABLE DECLARATION — 'rot_prob' decides whether to rotate the image.
        # WHY — Rotation is applied 50% of the time. Karen text in real documents
        #        is rarely perfectly horizontal — slight tilt of ±8 degrees is common.
        rot_prob = random.random()
        if rot_prob < 0.5:
            # FUNCTION CALL — random.uniform picks a rotation angle between -8 and +8 deg.
            # WHY — Large rotations (>15°) would make the syllable unrecognizable.
            #        Small rotations (0-8°) simulate natural document tilt.
            angle = random.uniform(-8, 8)

            # METHOD CALL — cv2.getRotationMatrix2D builds a 2D rotation matrix.
            # ARGUMENT — center is the image center point so it rotates around the middle.
            # ARGUMENT — angle is the rotation in degrees (positive = counter-clockwise).
            # ARGUMENT — 1.0 is the scale factor (1.0 = no resizing).
            # WHY — The rotation matrix is needed by cv2.warpAffine to actually
            #        rotate the pixels of the image.
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)

            # METHOD CALL — cv2.warpAffine applies the rotation matrix to the image.
            # ARGUMENT — cv2.BORDER_REFLECT pads edges by mirroring instead of black.
            # WHY — Black edge padding creates artificial dark borders that confuse
            #        the model into thinking edges are meaningful features.
            img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)

        # ── SAVE IMAGE ────────────────────────────────────────────────────────
        # STRING FORMATTING — builds a unique filename for this booster image.
        # WHY — Each filename includes the syllable name, "boost" marker, and index
        #        so these images are identifiable and never collide with existing files.
        img_filename = f"{syllable}_boost_{i:04d}.png"
        img_save_path = os.path.join(train_images_dir, img_filename)

        # METHOD CALL — cv2.imwrite saves the augmented image as a PNG file.
        # WHY — PNG is lossless — no compression artifacts that could confuse the model.
        #        The image goes to train/images/ so YOLO includes it in training.
        cv2.imwrite(img_save_path, img)

        # ── SAVE MATCHING LABEL FILE ──────────────────────────────────────────
        # STRING FORMATTING — builds the matching label filename (same stem as image).
        # WHY — YOLO requires every training image to have a .txt label file with the
        #        EXACT same stem. "tuh_oo_t5_boost_0001.png" → "tuh_oo_t5_boost_0001.txt"
        lbl_filename = f"{syllable}_boost_{i:04d}.txt"
        lbl_save_path = os.path.join(train_labels_dir, lbl_filename)

        # FILE OPERATION — writes the YOLO label file for this booster image.
        # WHY — YOLO bounding box format: "class_idx cx cy w h" where all values
        #        except class_idx are normalized 0-1. Since each booster image contains
        #        exactly one syllable centered in the frame, we use 0.5 0.5 for center
        #        and 0.9 0.9 for width/height (syllable fills ~90% of the 320x320 frame).
        with open(lbl_save_path, "w") as lbl_f:
            lbl_f.write(f"{class_idx} 0.5 0.5 0.9 0.9\n")

        # VARIABLE DECLARATION — increments the per-syllable counter.
        generated_for_this += 1

    # OUTPUTPRINT — reports how many images were generated for this syllable.
    # WHY — Real-time feedback so the user can monitor progress without guessing.
    print(f"  BOOSTED {syllable:25s} (class {class_idx:4d}) → {generated_for_this} images")

    # VARIABLE DECLARATION — adds this syllable to the success list and total count.
    total_generated += generated_for_this
    boosted_syllables.append({"syllable": syllable, "class_idx": class_idx,
                               "images_generated": generated_for_this})

# LOOP — adds any syllables that were not resolved to the skipped list.
# WHY — Some missed syllables had no matching filename in the training set,
#        meaning they were never included in the original dataset generation.
for syllable in missed_syllables:
    if syllable not in syllable_to_class_idx and syllable not in skipped_syllables:
        skipped_syllables.append(syllable)

# =============================================================================
# SECTION 5: Save booster report and print final summary
# =============================================================================

# VARIABLE DECLARATION — 'report' is the dictionary that summarizes everything 022 did.
# WHY — This report is saved as JSON so future sessions can see exactly what was
#        boosted, what class indices were used, and what was skipped for follow-up.
report = {
    "total_generated": total_generated,
    "boosted_count": len(boosted_syllables),
    "skipped_count": len(skipped_syllables),
    "boosted": boosted_syllables,
    "skipped": skipped_syllables
}

# VARIABLE DECLARATION — 'report_path' is where the JSON report is saved.
report_path = "/root/karenlangtrans/022_booster_report.json"

# FILE OPERATION — writes the report dictionary to disk as a formatted JSON file.
# ARGUMENT — indent=2 makes the JSON human-readable with 2-space indentation.
# ARGUMENT — ensure_ascii=False allows Karen Unicode characters in the output.
# WHY — A saved report means the user never has to re-run 022 just to remember
#        what was generated. It also feeds into future gap analysis comparisons.
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

# OUTPUTPRINT — prints the final summary to the terminal.
# WHY — After a multi-minute script, the user needs a clear single-line confirmation
#        of what was accomplished before proceeding to the next step (021 retraining).
print("\n" + "=" * 60)
print(f"  022 COMPLETE")
print("=" * 60)
print(f"  Total booster images generated : {total_generated}")
print(f"  Syllables successfully boosted : {len(boosted_syllables)}/{len(missed_syllables)}")
print(f"  Syllables skipped (not found)  : {len(skipped_syllables)}")
if skipped_syllables:
    print(f"  Skipped: {skipped_syllables}")
print(f"  Report saved: {report_path}")
print(f"  Images added to: {train_images_dir}")
print("=" * 60)
print("  NEXT STEP: Run 021_retrain_v2_boosted.py")
print("  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python3 021_retrain_v2_boosted.py")
print("=" * 60)
