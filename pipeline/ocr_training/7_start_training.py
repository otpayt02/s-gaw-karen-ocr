import os
from roboflow import Roboflow

# â”€â”€ Fill these in â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
API_KEY = os.environ.get("ROBOFLOW_API_KEY", "")
WORKSPACE_SLUG = "sgaw-supervisor-ai"  # from check_workspace.py
PROJECT_ID     = "sgaw-perception"
VERSION_NUMBER = 23   # the version that was already created
TRAIN_SPEED    = "Roboflow 3.0 Object Detection (Accurate)"   # Roboflow 3.0 Accurate subtype
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if not API_KEY:
    raise SystemExit("Set ROBOFLOW_API_KEY before running this script.")

rf        = Roboflow(api_key=API_KEY)
workspace = rf.workspace(WORKSPACE_SLUG)
project   = workspace.project(PROJECT_ID)
version   = project.version(VERSION_NUMBER)

print("Found version:", version)
print("Starting training... speed =", TRAIN_SPEED)

version.train(model_type="yolov8s")

print("Training job submitted to Roboflow cloud.")
print("Monitor at: https://app.roboflow.com/" + WORKSPACE_SLUG + "/" + PROJECT_ID)
print("Roboflow will email you when it finishes.")
