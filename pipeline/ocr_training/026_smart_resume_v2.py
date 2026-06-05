# ============================================================
# 026_smart_resume_v2.py
# FILE: /root/karenlangtrans/026_smart_resume_v2.py
# PIPELINE POSITION: Training phase — runs AFTER 018 (pathconfig.json must exist)
# REQUIRES: pathconfig.json, any one of: last.pt (v2), best.pt (v2), best.pt (v1)
# PRODUCES: /workspace/runs/karenocrv2boosted/weights/best.pt (completed v2 model)
# PURPOSE:  Smart resume — auto-detects training state and picks the best recovery
#           path. Handles: true resume from last.pt at epoch 34, fallback to
#           v2 best.pt fine-tune restart, fallback to v1 full retrain, and
#           already-complete detection so you don't accidentally re-train.
# ============================================================

# IMPORT — brings in Python's json library so we can read pathconfig.json,
#          the file that 018 wrote to record where all project files live on
#          this specific server instance.
import json

# IMPORT — brings in Python's os library for checking whether files and folders
#          actually exist before we try to open or load them.
import os

# IMPORT — brings in Python's sys library so we can call sys.exit() to stop
#          the script cleanly with a status code the shell can read.
import sys

# IMPORT — brings in the YOLO class from the Ultralytics library.
# PACKAGE — Ultralytics YOLOv8 is the deep learning framework that manages
#            model loading, the training loop, GPU communication, checkpoint
#            saving (best.pt / last.pt), and metrics logging. It is the entire
#            engine that makes the Karen syllable detection model work.
from ultralytics import YOLO


# ── STEP 1: LOAD pathconfig.json ─────────────────────────────────────────────

# VARIABLE DECLARATION — stores the absolute path where 018 always writes
#                         pathconfig.json. Every script from 019 onward reads
#                         this file instead of hardcoding paths, because vast.ai
#                         server instances change IDs between sessions.
PATHCONFIG = "/root/karenlangtrans/pathconfig.json"

# CONDITIONAL — if 018 has not been run yet on this server instance, pathconfig.json
#               will not exist. We stop here rather than silently using wrong paths,
#               because wrong paths mean training on the wrong dataset or loading
#               the wrong model — a silent failure that wastes 2–4 hours of GPU time
#               and GPU credits on the vast.ai instance.
if not os.path.exists(PATHCONFIG):
    print("[026] ERROR: pathconfig.json not found.")
    print("[026] Run:  python3 /root/karenlangtrans/018_find_index_map.py  first.")
    # FUNCTION CALL — sys.exit(1) terminates the script immediately.
    # ARGUMENT — 1 is a non-zero exit code, which signals failure to the terminal.
    sys.exit(1)

# FILE OPERATION — opens pathconfig.json in read mode ("r") so we can load its
#                  contents. The "with" keyword ensures the file is closed
#                  automatically when we are done reading, even if an error occurs.
with open(PATHCONFIG) as f:
    # VARIABLE DECLARATION — METHOD CALL — json.load(f) parses the JSON text
    #                         from the file into a Python dictionary, giving us
    #                         key-value access to every path 018 recorded.
    cfg = json.load(f)

# VARIABLE DECLARATION — METHOD CALL — cfg.get("data_yaml", fallback) retrieves
#                         the path to data.yaml from the config dictionary.
#                         data.yaml tells YOLO where the training images are,
#                         where the validation images are, how many classes there
#                         are (nc=6341), and what each class is named.
#                         Without this file, YOLO cannot start training at all.
data_yaml = cfg.get("data_yaml", "/root/karen_dataset_yolov8/data.yaml")

# OUTPUTPRINT — prints the resolved data.yaml path to the terminal so you can
#               visually confirm it points at the right dataset before the GPU
#               starts burning through training time.
print(f"[026] data.yaml  : {data_yaml}")
print(f"[026] Starting checkpoint detection...")


# ── STEP 2: DEFINE CHECKPOINT CANDIDATES (priority order) ────────────────────

# VARIABLE DECLARATION — path to last.pt from the interrupted v2 run.
#                         WHY THIS IS PRIORITY 1: last.pt contains not just the
#                         network weights but also the optimizer's momentum state —
#                         the "memory" of how the model was adjusting itself when
#                         training stopped at epoch 34. Resume from here and training
#                         picks up exactly as if nothing happened. The model
#                         continues improving Karen syllable detection from exactly
#                         where it left off.
V2_LAST = "/workspace/runs/karenocrv2boosted/weights/last.pt"

# VARIABLE DECLARATION — path to best.pt from the interrupted v2 run.
#                         WHY THIS IS PRIORITY 2: best.pt holds the weights from
#                         whichever single epoch had the highest mAP50 in epochs
#                         1–34. It does NOT carry optimizer momentum, so using it
#                         means a fine-tune restart rather than a true resume.
#                         Still far better than starting from v1 because 34 epochs
#                         of Karen syllable fine-tuning are preserved in the weights.
V2_BEST = "/workspace/runs/karenocrv2boosted/weights/best.pt"

# VARIABLE DECLARATION — path to best.pt from v1 (the completed 88.8% mAP50 model).
#                         WHY THIS IS PRIORITY 3 (worst case): if every v2 checkpoint
#                         is gone — server wiped, storage reset — we can still start
#                         a full 50-epoch v2 fine-tune from the v1 Karen knowledge.
#                         No v2 progress is recovered, but the 100-epoch v1 baseline
#                         means we are not starting from zero Karen recognition.
V1_BEST = "/workspace/runs/karenocrv3clean/weights/best.pt"

# VARIABLE DECLARATION — path to the training results CSV that YOLOv8 writes
#                         automatically after each epoch. Each row = one epoch.
#                         Reading this tells us exactly how many epochs completed
#                         before training was interrupted.
RESULTS_CSV = "/workspace/runs/karenocrv2boosted/results.csv"


# ── STEP 3: CHECK WHETHER v2 TRAINING ALREADY COMPLETED ──────────────────────

# VARIABLE DECLARATION — will hold the number of epochs already done.
#                         We start at 0 and update it if results.csv exists.
epochs_done = 0

# CONDITIONAL — only try to read results.csv if the file actually exists.
#               If it does not exist, we have never written any completed epoch
#               on this server (either fresh instance or 021 was never run).
if os.path.exists(RESULTS_CSV):
    # FILE OPERATION — opens results.csv in read mode so we can count epoch rows.
    with open(RESULTS_CSV) as f:
        # VARIABLE DECLARATION — METHOD CALL — f.readlines() loads every line of
        #                         the CSV into a Python list. One entry per line.
        all_lines = f.readlines()

    # LIST/DICT/SET — a list comprehension that keeps only lines which:
    #   (1) are not blank (l.strip() is truthy)
    #   (2) do not start with "epoch" (the CSV header row starts with that word)
    # Each remaining line represents one completed training epoch.
    data_rows = [
        l for l in all_lines
        if l.strip() and not l.strip().lower().startswith("epoch")
    ]

    # VARIABLE DECLARATION — FUNCTION CALL — len() counts how many epoch rows
    #                         remain after stripping the header. This is the
    #                         number of epochs that fully completed before the
    #                         training run was interrupted.
    epochs_done = len(data_rows)

    # OUTPUTPRINT — tells you exactly how far v2 got so you understand the
    #               recovery situation before anything runs.
    print(f"[026] results.csv found: {epochs_done} / 50 epochs completed.")

    # CONDITIONAL — if 50 or more epochs are recorded, v2 is already done.
    #               We print the next evaluation commands and exit cleanly
    #               so you don't accidentally burn GPU time re-training a
    #               model that already finished.
    if epochs_done >= 50:
        print("[026] v2 training is ALREADY COMPLETE.")
        print("[026] Proceed to evaluation — run these two command pairs on the server:")
        print()
        print("  sed -i 's/karenocrv3clean/karenocrv2boosted/g' /root/karenlangtrans/016_run_full_validation_export.py")
        print("  python3 /root/karenlangtrans/016_run_full_validation_export.py")
        print()
        print("  sed -i 's/karenocrv3clean/karenocrv2boosted/g' /root/karenlangtrans/017_analyze_detection_gaps.py")
        print("  python3 /root/karenlangtrans/017_analyze_detection_gaps.py")
        # FUNCTION CALL — sys.exit(0) = clean exit, code 0 = success. No error.
        sys.exit(0)

else:
    # OUTPUTPRINT — no results.csv means this is either a fresh server instance
    #               or 021 was never run. We proceed to checkpoint detection.
    print("[026] No results.csv found — checking for checkpoint files...")


# ── STEP 4: DETECT CHECKPOINT AND LAUNCH APPROPRIATE TRAINING PATH ────────────

# CONDITIONAL — PRIORITY 1: last.pt from the interrupted v2 run is present.
#               This is the ideal recovery. Ultralytics resume=True reads ALL
#               training hyperparameters (epochs, data.yaml, lr, batch, imgsz)
#               directly from inside last.pt, so we do not pass them again.
#               Training continues from epoch 34 through epoch 50 seamlessly.
if os.path.exists(V2_LAST):
    print(f"[026] CHECKPOINT: v2 last.pt found — TRUE RESUME from epoch {epochs_done}")
    print(f"[026] Path: {V2_LAST}")
    print(f"[026] Continuing epochs {epochs_done + 1} → 50 ...")
    print()

    # INSTANTIATION — creates a YOLOv8s model object by loading v2 last.pt.
    #                 This is not a fresh model. It carries the weights AND the
    #                 optimizer momentum state (Adam optimizer's m and v vectors)
    #                 from all training steps up to epoch 34.
    model = YOLO(V2_LAST)

    # METHOD CALL — model.train(resume=True) tells Ultralytics to pick up exactly
    #               where training stopped. It reads every hyperparameter from
    #               inside last.pt itself. We pass NO other arguments because
    #               overriding any setting mid-run could corrupt the training
    #               continuity and invalidate the loss curve history.
    model.train(resume=True)


# CONDITIONAL — PRIORITY 2: last.pt is gone but v2 best.pt is still present.
#               We cannot do a true resume (no optimizer state) but we can
#               fine-tune FROM best.pt using the same hyperparameters as 021.
#               The Karen syllable knowledge from the best epoch is preserved.
elif os.path.exists(V2_BEST):
    print(f"[026] CHECKPOINT: last.pt not found. Falling back to v2 best.pt.")
    print(f"[026] Path: {V2_BEST}")
    print(f"[026] Fine-tune RESTART (optimizer state not preserved).")
    print(f"[026] Karen knowledge from best epoch IS preserved in weights.")
    print()

    # INSTANTIATION — creates a YOLO model from v2 best.pt.
    #                 Weights contain everything the model learned about Karen
    #                 syllables up to the best checkpoint. Optimizer state is gone.
    model = YOLO(V2_BEST)

    # METHOD CALL — model.train() with explicit hyperparameters matching 021.
    #               We must pass these manually because best.pt does not store them.
    model.train(
        # ARGUMENT — data.yaml loaded from pathconfig.json — 6,341-class Karen dataset
        data=data_yaml,
        # ARGUMENT — 50 epochs of fine-tuning from this checkpoint
        epochs=50,
        # ARGUMENT — 320px matches the resolution all training images were generated at
        imgsz=320,
        # ARGUMENT — batch 16 fits A100 80GB VRAM comfortably for this model size
        batch=16,
        # ARGUMENT — stop early if mAP50 doesn't improve for 20 straight epochs
        patience=20,
        # ARGUMENT — writes output to /workspace/runs/karenocrv2boosted/
        name="karenocrv2boosted",
        # ARGUMENT — parent folder for all training output files
        project="/workspace/runs",
        # ARGUMENT — lr0=0.001 conservative fine-tune rate, lower than default 0.01
        lr0=0.001,
        # ARGUMENT — lrf=0.01 means final LR = 0.001 * 0.01 = 0.00001 at epoch 50
        lrf=0.01,
        # ARGUMENT — device=0 explicitly selects the A100 GPU (first GPU in system)
        device=0,
        # ARGUMENT — 4 CPU data-loading threads; enough for A100 throughput
        workers=4,
        # ARGUMENT — exist_ok=True prevents a crash if the karenocrv2boosted
        #            output folder already exists from the interrupted 021 run
        exist_ok=True,
    )


# CONDITIONAL — PRIORITY 3: No v2 checkpoints at all.
#               Falls back to v1 best.pt and re-does the full 50-epoch v2 fine-tune.
#               All v2 progress is lost but the 88.8% v1 Karen knowledge is kept.
elif os.path.exists(V1_BEST):
    print(f"[026] WARNING: No v2 checkpoints found anywhere.")
    print(f"[026] FALLBACK: Full retrain from v1 best.pt (88.8% mAP50 baseline).")
    print(f"[026] Path: {V1_BEST}")
    print(f"[026] Estimated time: 2–4 hours on A100. All 50 v2 epochs will re-run.")
    print()

    # INSTANTIATION — creates a YOLO model from v1 best.pt.
    #                 v1 = karenocrv3clean = 100 epochs, 88.8% mAP50, 6,341 classes.
    #                 This is the starting point for all v2 fine-tuning work.
    model = YOLO(V1_BEST)

    # METHOD CALL — identical training config to the elif above, just different
    #               starting weights. The model learns to improve on v1's gaps.
    model.train(
        data=data_yaml,
        epochs=50,
        imgsz=320,
        batch=16,
        patience=20,
        name="karenocrv2boosted",
        project="/workspace/runs",
        lr0=0.001,
        lrf=0.01,
        device=0,
        workers=4,
        exist_ok=True,
    )


# CONDITIONAL — CRITICAL FAILURE: no checkpoint found anywhere on the server.
#               This means the server storage has been completely reset.
#               We cannot train without a starting model.
else:
    print("[026] CRITICAL ERROR: No checkpoint found at any expected path.")
    print("[026] Checked:")
    print(f"       {V2_LAST}")
    print(f"       {V2_BEST}")
    print(f"       {V1_BEST}")
    print("[026] If this is a brand-new server instance, run 018 first to update")
    print("      pathconfig.json, then check whether /workspace/ was preserved.")
    # FUNCTION CALL — sys.exit(1) signals failure to the shell
    sys.exit(1)


# ── STEP 5: POST-TRAINING CONFIRMATION ───────────────────────────────────────

# OUTPUTPRINT — success message printed after the training loop finishes
print()
print("[026] ✓ v2 training complete.")
# OUTPUTPRINT — exact path to the best weights so you can copy-paste it into
#               016, 017, or the translation pipeline without hunting for it
print("[026] Best weights: /workspace/runs/karenocrv2boosted/weights/best.pt")
# OUTPUTPRINT — reminds you what to do immediately after this script finishes
print("[026] NEXT STEPS on SERVER:")
print("      sed -i 's/karenocrv3clean/karenocrv2boosted/g' /root/karenlangtrans/016_run_full_validation_export.py")
print("      python3 /root/karenlangtrans/016_run_full_validation_export.py")
print("      sed -i 's/karenocrv3clean/karenocrv2boosted/g' /root/karenlangtrans/017_analyze_detection_gaps.py")
print("      python3 /root/karenlangtrans/017_analyze_detection_gaps.py")
