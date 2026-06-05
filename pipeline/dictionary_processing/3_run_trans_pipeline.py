import json
import os
import sys
from pathlib import Path

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except Exception:
    YOLO_AVAILABLE = False
    print("WARNING: torch not available — self-test mode only.\n")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# ==============================================================================
# 3_run_trans_pipeline.py
# PIPELINE POSITION: Final stage — runs after model is trained
# PURPOSE: Takes an input image, runs the YOLO model on it, converts each
#          detected class index → Karen Unicode syllable → English meaning,
#          and prints the full translation to the terminal.
# INPUT:   Any image file containing Karen script
# OUTPUT:  Printed Karen Unicode text + English translation to terminal
#
# REQUIRES these files in the same folder as this script:
#   - karen_index_map.json
#   - karen_all_syllables-3.json
#   - karendictdatabase.json
#   - best.pt  (only needed for real image inference)
# ==============================================================================

BASE_DIR       = Path(__file__).parent.resolve()
MODEL_PATH     = BASE_DIR / 'best.pt'
INDEX_MAP_PATH = BASE_DIR / 'karen_index_map.json'
SYLLABLES_PATH = BASE_DIR / 'karen_all_syllables.json'
DICT_PATH      = BASE_DIR / 'karendictdatabase.json'
CONF_THRESHOLD = 0.35


# ==============================================================================
# LOOKUP TABLE LOADER
# ==============================================================================

def load_lookup_tables():
    """
    FUNCTION DEFINITION — load_lookup_tables
    Loads all three JSON files and builds fast in-memory lookup dicts.
    RETURN STATEMENT: tuple of (index_map, syllable_by_classid, dict_by_unicode)
    """
    # FILE OPERATION — load karen_index_map.json
    # Maps string YOLO index → string class name e.g. "2" → "10"
    print(f"Loading index map      : {INDEX_MAP_PATH}")
    with open(INDEX_MAP_PATH, 'r', encoding='utf-8') as f:
        index_map = json.load(f)

    # FILE OPERATION — load karen_all_syllables-3.json
    # List of dicts each with class_id, full_unicode, romanized, label
    print(f"Loading syllable list  : {SYLLABLES_PATH}")
    with open(SYLLABLES_PATH, 'r', encoding='utf-8') as f:
        all_syllables = json.load(f)

    # FILE OPERATION — load karendictdatabase.json
    # List of dicts each with unicode and english fields
    print(f"Loading dictionary     : {DICT_PATH}")
    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        dict_db = json.load(f)

    # VARIABLE DECLARATION — build O(1) lookup dicts
    syllable_by_classid = {
        int(entry['class_id']): entry
        for entry in all_syllables
    }

    dict_by_unicode = {
        entry['unicode'].strip(): entry
        for entry in dict_db
        if 'unicode' in entry
    }

    print(f"Syllable classes loaded : {len(syllable_by_classid)}")
    print(f"Dictionary entries      : {len(dict_by_unicode)}\n")

    return index_map, syllable_by_classid, dict_by_unicode


# ==============================================================================
# CORE TRANSLATION FUNCTION
# ==============================================================================

def yolo_index_to_karen(yolo_index, index_map, syllable_by_classid, dict_by_unicode):
    """
    FUNCTION DEFINITION — yolo_index_to_karen
    Converts one YOLO class index → Karen Unicode + romanized + English.

    PARAMETER yolo_index          : int, raw class index from model output
    PARAMETER index_map           : dict from karen_index_map.json
    PARAMETER syllable_by_classid : dict keyed by int class_id
    PARAMETER dict_by_unicode     : dict keyed by unicode string
    RETURN STATEMENT: dict with unicode, romanized, label, english
    """
    # INDEX/SLICE — karen_index_map keys are strings so convert yolo_index to str
    string_class_name = index_map.get(str(yolo_index))

    # CONDITIONAL — index not in map
    if string_class_name is None:
        return {'unicode': '?', 'romanized': 'unknown',
                'label': 'unknown', 'english': 'index not in map'}

    # EXCEPTION HANDLER — class name should always be numeric
    try:
        class_id = int(string_class_name)
    except ValueError:
        return {'unicode': '?', 'romanized': 'unknown',
                'label': string_class_name, 'english': 'non-numeric class name'}

    # INDEX/SLICE — look up the syllable entry by integer class_id
    syllable = syllable_by_classid.get(class_id)

    # CONDITIONAL — class_id not in syllable list
    if syllable is None:
        return {'unicode': '?', 'romanized': 'unknown',
                'label': str(class_id), 'english': 'class_id not in syllable list'}

    # VARIABLE DECLARATION — extract fields from syllable entry
    unicode_str = syllable.get('full_unicode', '?')
    romanized   = syllable.get('romanized',    '?')
    label       = syllable.get('label',        '?')

    # INDEX/SLICE — look up English meaning from dictionary
    dict_entry = dict_by_unicode.get(unicode_str.strip(), {})
    english    = dict_entry.get('english', 'no translation found')

    return {
        'unicode':  unicode_str,
        'romanized': romanized,
        'label':    label,
        'english':  english
    }


# ==============================================================================
# SPATIAL SORT — reading order left-to-right, top-to-bottom
# ==============================================================================

def sort_detections_reading_order(detections, line_height_tolerance=0.4):
    """
    FUNCTION DEFINITION — sort_detections_reading_order
    Groups bounding boxes into lines by y_center proximity,
    then sorts each line left to right by x_center.

    PARAMETER detections            : list of detection dicts
    PARAMETER line_height_tolerance : float fraction of avg height for line grouping
    RETURN STATEMENT: sorted list of detection dicts
    """
    if not detections:
        return []

    # VARIABLE DECLARATION — average box height used to set line grouping threshold
    avg_height = sum(d['height'] for d in detections) / len(detections)
    tolerance  = avg_height * line_height_tolerance

    # LOOP — assign each detection to a line bucket by y proximity
    lines = []
    for det in sorted(detections, key=lambda d: d['y_center']):
        placed = False
        for line in lines:
            line_y = sum(d['y_center'] for d in line) / len(line)
            if abs(det['y_center'] - line_y) <= tolerance:
                line.append(det)
                placed = True
                break
        if not placed:
            lines.append([det])

    # LOOP — sort each line left to right and flatten into one list
    sorted_detections = []
    for line in lines:
        sorted_detections.extend(sorted(line, key=lambda d: d['x_center']))

    return sorted_detections


# ==============================================================================
# INFERENCE
# ==============================================================================

def run_inference(image_path, model, conf_threshold):
    """
    FUNCTION DEFINITION — run_inference
    Runs YOLO model on one image and returns raw detection dicts.

    PARAMETER image_path     : str or Path
    PARAMETER model          : loaded YOLO object
    PARAMETER conf_threshold : float minimum confidence
    RETURN STATEMENT: list of detection dicts
    """
    # METHOD CALL — run YOLO prediction on the image file
    results = model.predict(
        source  = str(image_path),
        conf    = conf_threshold,
        verbose = False
    )

    detections = []

    # LOOP — iterate over result objects (one per image in the batch)
    for result in results:
        # LOOP — iterate over each bounding box in the result
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append({
                'x_center':    (x1 + x2) / 2,
                'y_center':    (y1 + y2) / 2,
                'width':       x2 - x1,
                'height':      y2 - y1,
                'class_index': int(box.cls[0].item()),
                'confidence':  float(box.conf[0].item())
            })

    return detections


# ==============================================================================
# FULL PIPELINE — detect → sort → translate → print
# ==============================================================================

def translate_image(image_path, model, index_map, syllable_by_classid, dict_by_unicode):
    """
    FUNCTION DEFINITION — translate_image
    Runs the full pipeline on one image and prints results to terminal.
    """
    print(f"\n{'='*60}")
    print(f"Image: {image_path}")
    print(f"{'='*60}")

    # FUNCTION CALL — run YOLO inference
    detections = run_inference(image_path, model, CONF_THRESHOLD)
    print(f"Detections found: {len(detections)}")

    # CONDITIONAL — nothing detected
    if not detections:
        print("No Karen script detected in this image.")
        return

    # FUNCTION CALL — sort into reading order
    ordered = sort_detections_reading_order(detections)

    # OUTPUT — print column headers
    print(f"\n{'─'*60}")
    print(f"{'#':<4} {'Unicode':<12} {'Romanized':<22} {'Conf':<6} English")
    print(f"{'─'*60}")

    unicode_line = ''

    # LOOP — translate and print each detection
    for i, det in enumerate(ordered):
        result = yolo_index_to_karen(
            det['class_index'], index_map, syllable_by_classid, dict_by_unicode
        )
        print(
            f"{i+1:<4} "
            f"{result['unicode']:<12} "
            f"{result['romanized']:<22} "
            f"{det['confidence']:.2f}  "
            f"{result['english'][:50]}"
        )
        unicode_line += result['unicode']

    # OUTPUT — full assembled Karen Unicode text of the image
    print(f"\n{'─'*60}")
    print(f"Full Karen Unicode:")
    print(f"  {unicode_line}")
    print(f"{'─'*60}\n")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main():
    """
    FUNCTION DEFINITION — main
    No args → lookup self-test only (no model needed).
    Args    → full inference on each image path provided.

    Usage:
        python 3_run_trans_pipeline.py
        python 3_run_trans_pipeline.py image.png
    """
    # FUNCTION CALL — load all three lookup tables
    index_map, syllable_by_classid, dict_by_unicode = load_lookup_tables()

    # CONDITIONAL — no image arguments: run self-test only
    if len(sys.argv) < 2:
        print("No image provided. Running lookup self-test on indices 0–9:\n")
        print(f"{'Index':<8} {'Unicode':<14} {'Romanized':<22} English")
        print(f"{'─'*70}")
        for test_index in range(10):
            r = yolo_index_to_karen(
                test_index, index_map, syllable_by_classid, dict_by_unicode
            )
            print(
                f"{test_index:<8} "
                f"{r['unicode']:<14} "
                f"{r['romanized']:<22} "
                f"{r['english'][:30]}"
            )
        print(f"\nTo run on a real image:")
        print(f"  python 3_run_trans_pipeline.py path\\to\\image.png")
        return

    # CONDITIONAL — image args provided but torch is not available
    if not YOLO_AVAILABLE:
        print("ERROR: torch/ultralytics not available on this machine.")
        print("Cannot run model inference without torch.")
        print("Fix torch or run without arguments for self-test only.")
        return

    # CONDITIONAL — check best.pt exists before trying to load it
    if not MODEL_PATH.exists():
        print(f"ERROR: Model weights not found at {MODEL_PATH}")
        print("Copy best.pt from the server:")
        print("  /workspace/runs/karen_ocr_v3_clean/weights/best.pt")
        return

    # INSTANTIATION — load YOLO model from best.pt
    print(f"Loading model from {MODEL_PATH}...")
    model = YOLO(str(MODEL_PATH))
    print("Model loaded.\n")

    # LOOP — run full pipeline on each image path given as argument
    for image_path in sys.argv[1:]:
        image_path = Path(image_path)
        if not image_path.exists():
            print(f"WARNING: {image_path} not found — skipping.")
            continue
        translate_image(
            image_path, model, index_map, syllable_by_classid, dict_by_unicode
        )


if __name__ == '__main__':
    main()