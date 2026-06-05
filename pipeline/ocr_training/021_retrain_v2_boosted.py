#!/usr/bin/env python3
# =============================================================================
# FILE:        021_retrain_v2_boosted.py
# PIPELINE:    Step 5 of 5 in current phase — Fine-tune after booster image generation
# POSITION:    Runs AFTER 020_generate_booster_images.py has finished
# REQUIRES:    /workspace/runs/karen_ocr_v3_clean/weights/best.pt  (your v1 weights)
#              /root/karen_dataset_yolov8/data.yaml (cleaned by 019)
#              /root/karenlangtrans/path_config.json (written by 018)
#              ~14,900 new booster images added to train/images/ by 020
# PRODUCES:    /workspace/runs/karen_ocr_v2_boosted/weights/best.pt
#              /workspace/runs/karen_ocr_v2_boosted/weights/last.pt
#              /workspace/runs/karen_ocr_v2_boosted/results.csv
# PURPOSE:     Fine-tunes your v1 model specifically on the 149 previously
#              missed/low-scoring syllables. Starts FROM v1 best.pt so all
#              88.8% mAP knowledge is preserved — only the weak spots are pushed.
#              This produces karen_ocr_v2_boosted, your second major model version.
# =============================================================================

# IMPORT — brings in the 'os' module from Python's standard library.
# PACKAGE — 'os' provides file system tools like path joining and existence checks.
# WHY — We need to verify that best.pt and data.yaml exist before launching training.
#        Catching a missing file here avoids a confusing mid-training crash.
import os

# IMPORT — brings in the 'json' module from Python's standard library.
# PACKAGE — 'json' reads and writes JSON files, which store structured data as key-value pairs.
# WHY — path_config.json (written by 018) holds the canonical absolute paths for
#        this server instance. Different vast.ai instances can have different layouts,
#        so we always read paths from the config instead of hardcoding them.
import json

# IMPORT — brings in the YOLO class from the Ultralytics library.
# PACKAGE — 'ultralytics' is the library that wraps YOLOv8 model training, validation,
#            and inference behind a simple Python API.
# WHY — The YOLO class is the engine that will load v1's weights and run the
#        fine-tuning training loop on the A100 GPU to produce v2.
from ultralytics import YOLO

# =============================================================================
# SECTION 1: Load canonical paths from path_config.json
# =============================================================================

# VARIABLE DECLARATION — 'config_path' holds the full filesystem path to path_config.json.
# WHY — This file was written by 018_find_index_map.py and maps every important file
#        location on this specific server instance. Always reading from this file
#        means the script works correctly regardless of which vast.ai instance we are on.
config_path = "/root/karenlangtrans/path_config.json"

# CONDITIONAL — checks whether path_config.json actually exists on disk before trying to open it.
# WHY — If 018 has not been run yet, this file will not exist. Crashing here with a clear
#        message is far more helpful than a confusing FileNotFoundError from json.load.
if not os.path.exists(config_path):
    print("ERROR: path_config.json not found.")
    print("Run 018_find_index_map.py first on this server instance.")
    # FUNCTION CALL — 'exit(1)' stops the script immediately with error code 1.
    # WHY — Code 1 signals to the terminal that the script failed. Code 0 means success.
    exit(1)

# FILE OPERATION — opens path_config.json for reading using Python's built-in open().
# WHY — We need to load the dictionary of paths that 018 wrote so we can find best.pt
#        and data.yaml without hardcoding their locations.
with open(config_path, "r") as f:
    # FUNCTION CALL — 'json.load(f)' reads the entire JSON file and returns a Python dict.
    # WHY — Converts the text file into a usable Python dictionary so we can access
    #        values like paths["data_yaml"] and paths["v1_best_pt"].
    paths = json.load(f)

# =============================================================================
# SECTION 2: Resolve all required file paths
# =============================================================================

# VARIABLE DECLARATION — 'data_yaml' is the full path to the YOLO dataset config file.
# WHY — data.yaml tells YOLO where the training images and labels are, what the class
#        names are, and how many classes (nc) exist. Without this file YOLO cannot start.
# METHOD CALL — dict.get() retrieves a value by key, returning the fallback string if
#               the key is absent. This prevents a KeyError crash if 018 wrote a different key name.
data_yaml = paths.get("data_yaml", "/root/karen_dataset_yolov8/data.yaml")

# VARIABLE DECLARATION — 'v1_weights' is the full path to your v1 best.pt checkpoint.
# WHY — We are FINE-TUNING, not training from scratch. Starting from v1's best.pt means
#        the model already knows 93.3% of Karen syllables at 88.8% mAP. We only need to
#        improve the 149 syllables it struggled with. This saves ~40-60 training epochs.
#        Note: the internal YOLO folder for v1 is named 'karen_ocr_v3_clean' — that is
#        just the Ultralytics run name from that session. Your model versioning calls it v1.
v1_weights = paths.get(
    "v1_best_pt",
    "/workspace/runs/karen_ocr_v3_clean/weights/best.pt"
)

# VARIABLE DECLARATION — 'output_run_name' is the name for this training run's output folder.
# WHY — YOLO saves all results (weights, charts, CSV) to /workspace/runs/<name>/. Naming it
#        karen_ocr_v2_boosted makes it clear this is your second model version, trained on
#        the booster-augmented dataset that targets the 149 missed syllables.
output_run_name = "karen_ocr_v2_boosted"

# =============================================================================
# SECTION 3: Pre-flight checks — verify required files exist before training starts
# =============================================================================

# CONDITIONAL — checks that data.yaml is on disk before starting.
# WHY — If 019 failed silently or the path is wrong, training will fail at epoch 1.
#        Catching it here saves 30+ minutes of waiting for a doomed run.
if not os.path.exists(data_yaml):
    print(f"ERROR: data.yaml not found at: {data_yaml}")
    print("Run 019_clean_rebuild_data_yaml.py first, then retry.")
    exit(1)

# CONDITIONAL — checks that v1 best.pt exists before fine-tuning from it.
# WHY — If the weights file was deleted or never copied to this instance, YOLO will
#        crash immediately with a confusing PyTorch error. This gives you the exact
#        scp command to fix it instead.
if not os.path.exists(v1_weights):
    print(f"ERROR: v1 best.pt not found at: {v1_weights}")
    print("Upload it from your local machine using:")
    print("  scp -P [PORT] C:\\Users\\olive\\Projects\\karen_lang_trans\\karen_ocr_v1_best.pt")
    print(f"  root@[IP]:{v1_weights}")
    exit(1)

# OUTPUTPRINT — confirms to the terminal that all files were found and training is ready.
# WHY — Seeing this block means every pre-flight check passed. Nothing will crash at launch.
print("=" * 65)
print("  021_retrain_v2_boosted.py  |  Karen OCR v2 Fine-Tune Run")
print("=" * 65)
print(f"  Base weights : {v1_weights}")
print(f"  Dataset      : {data_yaml}")
print(f"  Output run   : /workspace/runs/{output_run_name}/")
print("  Fine-tuning from v1 — 149 booster classes targeted")
print("  This run produces karen_ocr_v2_boosted — your second model.")
print("=" * 65)

# =============================================================================
# SECTION 4: Load v1 weights and run fine-tune training to produce v2
# =============================================================================

# INSTANTIATION — creates a YOLO model object loaded with v1's trained weights.
# WHY — Passing best.pt (instead of yolov8s.pt) means the model already knows Karen
#        script at 88.8% mAP. The training loop will adjust weights only where the
#        booster images reveal gaps, preserving everything v1 already learned.
model = YOLO(v1_weights)

# METHOD CALL — 'model.train()' starts the YOLOv8 training loop on the A100 GPU.
# WHY — This is the core command that runs all 50 epochs of fine-tuning. Every
#        argument below is a CLASS ATTRIBUTE that configures one aspect of training.
results = model.train(
    # CLASS ATTRIBUTE — 'data' points YOLO to the dataset config YAML.
    # WHY — Tells the trainer where train/images/, valid/images/, and class names live.
    data=data_yaml,

    # CLASS ATTRIBUTE — 'epochs=50' runs 50 training passes over the full dataset.
    # WHY — 50 epochs is enough for fine-tuning. v1 needed 100 epochs to learn Karen
    #        from scratch. v2 is only correcting the 149 weak classes — fewer passes
    #        get the job done and avoid overfitting on the new booster images.
    epochs=50,

    # CLASS ATTRIBUTE — 'imgsz=320' sets input image size to 320x320 pixels.
    # WHY — Must match v1's training size exactly. Changing this mid-project breaks
    #        the feature maps and degrades accuracy on all existing classes.
    imgsz=320,

    # CLASS ATTRIBUTE — 'batch=32' processes 32 images per gradient update step.
    # WHY — 32 is the confirmed stable batch size for the A100-80GB. Larger batches
    #        would be faster but risk running out of memory on 6,341-class output heads.
    batch=32,

    # CLASS ATTRIBUTE — 'half=True' enables FP16 mixed precision training.
    # WHY — Halves GPU memory usage with no accuracy loss on the A100, which handles
    #        FP16 natively at full speed. This is what prevented OOM crashes in v1.
    half=True,

    # CLASS ATTRIBUTE — 'name' sets the output folder name under /workspace/runs/.
    # WHY — All checkpoints, CSVs, and result charts will be saved to
    #        /workspace/runs/karen_ocr_v2_boosted/. Never reuse a name or results overwrite.
    name=output_run_name,

    # CLASS ATTRIBUTE — 'device=0' assigns training to GPU 0, the A100.
    # WHY — On a single-GPU vast.ai instance, device 0 is always the A100-80GB.
    #        Using 'cpu' instead would make training take days, not hours.
    device=0,

    # CLASS ATTRIBUTE — 'workers=8' spawns 8 CPU threads for loading images from disk.
    # WHY — The A100 processes batches so fast that the bottleneck becomes disk I/O.
    #        8 workers keeps the GPU fully fed with zero idle time between batches.
    workers=8,

    # CLASS ATTRIBUTE — 'patience=20' triggers early stopping if mAP does not improve
    #                    for 20 consecutive epochs.
    # WHY — If v2 plateaus before epoch 50, this stops training automatically and saves
    #        the best checkpoint seen so far, preventing overfitting on booster images.
    patience=20,

    # CLASS ATTRIBUTE — 'project' sets the root output directory for this training run.
    # WHY — /workspace/ is persistent storage on vast.ai. Files here survive container
    #        restarts, unlike /tmp which is wiped on reboot.
    project="/workspace/runs",

    # CLASS ATTRIBUTE — 'lr0=0.001' sets the initial learning rate for fine-tuning.
    # WHY — Fine-tuning always uses a LOWER lr than training from scratch. v1 trained
    #        at the default lr0=0.01. Dropping to 0.001 makes smaller weight updates
    #        so the model improves the 149 weak syllables without forgetting the 6,192
    #        that already score well. Think of it as a scalpel instead of a hammer.
    lr0=0.001,

    # CLASS ATTRIBUTE — 'lrf=0.01' is the final learning rate as a fraction of lr0.
    # WHY — The cosine scheduler decays lr from lr0 down to lr0 * lrf across all epochs.
    #        With lr0=0.001 and lrf=0.01, the final lr = 0.00001. These very small steps
    #        in the last epochs lock in precise improvements on the booster syllables.
    lrf=0.01,
)

# =============================================================================
# SECTION 5: Confirm output and print next steps
# =============================================================================

# VARIABLE DECLARATION — 'best_pt_path' is the expected output location of the v2 checkpoint.
# WHY — We use this to verify the file was actually saved and to print the exact scp
#        command the user needs to download v2 to their local machine.
best_pt_path = f"/workspace/runs/{output_run_name}/weights/best.pt"

# CONDITIONAL — checks that the output weights file exists after training completes.
# WHY — If training crashed (e.g. OOM at epoch 1), best.pt will not exist.
#        This check prevents the user from thinking training succeeded when it did not.
if os.path.exists(best_pt_path):
    # OUTPUTPRINT — prints the full success message and exact next commands.
    # WHY — After a long training run the user needs clear, copy-pasteable instructions
    #        for what to do next. No ambiguity about paths or script numbers.
    print("\n" + "=" * 65)
    print("  TRAINING COMPLETE  |  karen_ocr_v2_boosted")
    print("=" * 65)
    print(f"  Best model saved: {best_pt_path}")
    print("\n  NEXT STEPS:")
    print("  1. Download v2 best.pt to your local machine (local CMD):")
    print(f"     scp -P [PORT] root@[IP]:{best_pt_path}")
    print("        C:\\Users\\olive\\Projects\\karen_lang_trans\\karen_ocr_v2_best.pt")
    print("  2. Run 016 inference test — update model path inside 016 to v2 first:")
    print("     python3 /root/karenlangtrans/016_run_full_validation_export.py")
    print("  3. Run 017 gap analysis to compare missed syllable count vs v1:")
    print("     python3 /root/karenlangtrans/017_analyze_detection_gaps.py")
    print("  TARGET: missed syllables drop from 149 (v1) to below 50 (v2)")
    print("  AFTER v2: v3 will target any remaining gaps, then v4 for real-world docs.")
    print("=" * 65)
else:
    # OUTPUTPRINT — prints a failure message with root cause and exact fix commands.
    # WHY — A missing best.pt means training never completed a full epoch. The most
    #        common cause is CUDA out-of-memory. The fix below is the confirmed solution.
    print("\nWARNING: best.pt not found — training may have crashed before epoch 1.")
    print("Check the output above for 'CUDA out of memory' errors.")
    print("If OOM is the cause:")
    print("  Open 021_retrain_v2_boosted.py and change batch=32 to batch=16")
    print("  Then re-run:")
    print("  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python3 021_retrain_v2_boosted.py")
