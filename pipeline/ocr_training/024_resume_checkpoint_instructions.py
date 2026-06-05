# FILE: 024_resume_checkpoint_instructions.py
# PIPELINE: one-off recovery helper after interrupted 021 training
# POSITION: recovery / resume only; does not replace core pipeline files
# REQUIRES: a saved YOLO checkpoint either on server or uploaded from local
# PRODUCES: none directly; used as reference for exact resume commands

# VARIABLE DECLARATION — recovery_paths ranks resume options from best to worst.
# WHY — In Karen OCR training, the highest-value resume source is last.pt because it
# preserves optimizer state and exact epoch position. best.pt is second best because
# it preserves model weights but not exact training momentum.
recovery_paths = [
    "1) /workspace/runs/karen_ocr_v2_boosted/weights/last.pt  -> exact resume point",
    "2) local karen_ocr_v2_last.pt uploaded back to server     -> exact resume point",
    "3) /workspace/runs/karen_ocr_v2_boosted/weights/best.pt  -> restart from best checkpoint",
    "4) local karen_ocr_v2_best.pt uploaded back to server     -> restart from best checkpoint",
    "5) /workspace/runs/karen_ocr_v1/weights/best.pt          -> earliest safe fallback"
]

# LOOP — prints each ranked recovery path.
# WHY — This gives a simple priority order for recovering the interrupted Karen OCR run.
for path in recovery_paths:
    print(path)
