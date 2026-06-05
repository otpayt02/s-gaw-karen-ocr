# FILE: 025_resume_v2_training.py
# PIPELINE: direct continuation of interrupted 021_retrain_v2_boosted.py
# POSITION: training stage — picks up from epoch 35, runs to epoch 50
# REQUIRES: /workspace/runs/karen_ocr_v2_boosted/weights/last.pt (CONFIRMED PRESENT)
# PRODUCES: updated best.pt and last.pt in /workspace/runs/karen_ocr_v2_boosted/weights/

# IMPORT — brings in the YOLO class from Ultralytics
# PACKAGE — ultralytics is the YOLOv8 training and inference framework
# WHY — YOLO is the core engine that handles all Karen OCR model training
from ultralytics import YOLO

# VARIABLE DECLARATION — checkpoint_path stores the path to last.pt on this server
# WHY — last.pt is the checkpoint YOLO saved at the end of epoch 34. It contains
#       the full model weights AND the optimizer state, meaning the model remembers
#       exactly how it was learning at the moment training stopped. This is the key
#       difference from best.pt: best.pt only has weights, last.pt has momentum too.
checkpoint_path = '/workspace/runs/karen_ocr_v2_boosted/weights/last.pt'

# INSTANTIATION — creates a YOLO model object loaded from the epoch-34 checkpoint
# ARGUMENT — checkpoint_path points to last.pt saved on Apr 11 at 16:59
# WHY — Loading last.pt restores the model to its exact state at epoch 34 so that
#       when we call train(resume=True), YOLO knows to start at epoch 35 and not 1.
model = YOLO(checkpoint_path)

# METHOD CALL — model.train() resumes training from the checkpoint
# CLASS ATTRIBUTE — resume=True tells YOLO this is a continuation, not a new run
# WHY — Without resume=True, YOLO would start over at epoch 1 and overwrite the
#       karen_ocr_v2_boosted folder with fresh (untrained) results. resume=True
#       reads all training settings (epochs, imgsz, data path, project, name)
#       directly from the checkpoint itself, so nothing needs to be re-specified.
#       Training will continue from epoch 35 to epoch 50 automatically.
model.train(resume=True)
