#!/usr/bin/env python3
"""
041_gen_paragraph_data.py
Karen OCR â€” Paragraph-Level Dataset Generator
Pipeline: Dataset Generation Phase
Requires: path_config.json, karen_index_map.json, padauk-regular.ttf
Produces: paragraph images + multi-syllable YOLO labels in train/images & train/labels
"""

# â”€â”€ IMPORTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import json        # FILE OPERATION â€” reads path_config.json and karen_index_map.json
import os          # FUNCTION CALL â€” creates folders, builds file paths
import random      # FUNCTION CALL â€” randomly selects syllables to build fake Karen sentences
import uuid        # FUNCTION CALL â€” generates unique filenames so no image ever overwrites another
from pathlib import Path   # VARIABLE DECLARATION â€” cleaner cross-platform path handling
from playwright.sync_api import sync_playwright  # IMPORT â€” headless Chromium browser that correctly shapes Karen Unicode glyphs

# â”€â”€ CONFIG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# VARIABLE DECLARATION â€” how many paragraph images to generate per run
NUM_PARAGRAPHS = 2000

# VARIABLE DECLARATION â€” syllables per line (Karen words are ~1-4 syllables each)
SYLLABLES_PER_LINE_MIN = 4
SYLLABLES_PER_LINE_MAX = 9

# VARIABLE DECLARATION â€” lines per paragraph image
LINES_PER_PARA_MIN = 2
LINES_PER_PARA_MAX = 4

# VARIABLE DECLARATION â€” image canvas size; wider than single-syllable 320x320
IMG_W = 640
IMG_H = 480

# VARIABLE DECLARATION â€” Padauk font size; smaller than single-syllable since multiple glyphs share the canvas
FONT_SIZE_PX = 52

# â”€â”€ LOAD PATH CONFIG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FILE OPERATION â€” reads the path_config.json written by 018_find_index_map.py
# so we never hardcode server paths again; if this file is missing, run 018 first
with open('/root/karenlangtrans/path_config.json') as f:
    paths = json.load(f)

# VARIABLE DECLARATION â€” pulls the confirmed server paths for the index map and font
INDEX_MAP_PATH = paths['karen_index_map']
FONT_PATH      = paths['font_path']
TRAIN_IMAGES   = paths['train_images']   # /root/karen_dataset_yolov8/train/images
TRAIN_LABELS   = paths['train_labels']   # /root/karen_dataset_yolov8/train/labels

# FILE OPERATION â€” loads the index map so we know which class index number
# corresponds to each romanized syllable name like "muh_aa_t2"
with open(INDEX_MAP_PATH) as f:
    index_map = json.load(f)

# VARIABLE DECLARATION â€” list of all (class_index, unicode_string) pairs
# index_map keys are class integers as strings, values are syllable names
# We need the reverse: syllable name â†’ class index, for building YOLO labels
syllable_list = []
for class_idx_str, syllable_name in index_map.items():
    syllable_list.append((int(class_idx_str), syllable_name))

print(f"Loaded {len(syllable_list)} syllables from index map âœ…")

# â”€â”€ HTML BUILDER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FUNCTION DEFINITION â€” builds an HTML page that renders a paragraph of Karen text
# using Padauk font via Playwright; each syllable is wrapped in its own <span>
# so Playwright can measure its individual bounding box via getBoundingClientRect()
def build_paragraph_html(lines_of_syllables, font_path_posix):
    # STRING FORMATTING â€” the font path must be a file:// URI for the browser to load it
    font_uri = f"file://{font_path_posix}"

    # LIST/DICT/SET â€” builds the inner HTML; each line is a <div>, each syllable is a <span>
    line_divs = []
    for line in lines_of_syllables:
        # STRING FORMATTING â€” each syllable gets a data-idx attribute storing its class index
        # so we can retrieve it later when collecting bounding boxes
        spans = "".join(
            f'<span data-class="{cls_idx}" style="display:inline-block;">{syllable_unicode}</span>'
            for cls_idx, syllable_unicode in line
        )
        line_divs.append(f'<div style="line-height:1.6; margin-bottom:4px;">{spans}</div>')

    lines_html = "\n".join(line_divs)

    # RETURN STATEMENT â€” returns complete HTML string; no f-string for the CSS block
    # to avoid brace conflicts, same technique as 1_karen_dataset_gen.py
    return (
        "<html><head><style>"
        "@font-face { font-family: 'Padauk'; src: url('" + font_uri + "'); }"
        "body { margin: 0; padding: 12px; background: white; font-family: 'Padauk'; "
        "font-size: " + str(FONT_SIZE_PX) + "px; color: black; width: " + str(IMG_W) + "px; }"
        "</style></head><body>"
        + lines_html +
        "</body></html>"
    )

# â”€â”€ YOLO LABEL WRITER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FUNCTION DEFINITION â€” converts a pixel bounding box from Playwright into
# normalized YOLO format: class_index cx cy w h  (all values 0.0â€“1.0)
def write_yolo_bbox(label_path, class_idx, px_x, px_y, px_w, px_h, img_w, img_h):
    # VARIABLE DECLARATION â€” YOLO center-x and center-y, normalized to image width/height
    cx = (px_x + px_w / 2) / img_w
    cy = (px_y + px_h / 2) / img_h
    # VARIABLE DECLARATION â€” YOLO width and height, also normalized
    nw = px_w / img_w
    nh = px_h / img_h
    # FILE OPERATION â€” appends one line per syllable to the label file
    # 'a' mode means we keep adding lines for each syllable in this image
    with open(label_path, 'a') as f:
        f.write(f"{class_idx} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")

# â”€â”€ SYLLABLE UNICODE LOOKUP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FUNCTION DEFINITION â€” takes a romanized syllable name like "muh_aa_t2"
# and returns the Karen Unicode string by rebuilding it from the consonant/vowel/tone tables
# NOTE: This requires the same Unicode lookup tables from 1_karen_dataset_gen.py
# For now we use the class index as the rendering key via a pre-built unicode_map

# FILE OPERATION â€” load a unicode_map if it exists (built by 4_syllable_gen.py)
# Maps class_index â†’ Karen Unicode string for rendering
UNICODE_MAP_PATH = paths.get('unicode_map', None)
if UNICODE_MAP_PATH and os.path.exists(UNICODE_MAP_PATH):
    with open(UNICODE_MAP_PATH) as f:
        unicode_map = json.load(f)    # keys are class index strings, values are Unicode
    print(f"Loaded unicode_map with {len(unicode_map)} entries âœ…")
else:
    # BOOLEAN FLAG â€” if no unicode_map, we fall back to rendering the syllable name
    # as Latin text (useful for testing layout logic before real glyphs)
    unicode_map = None
    print("âš ï¸  No unicode_map found â€” rendering syllable names as Latin placeholders")
    print("   Run 4_syllable_gen.py and update path_config.json with 'unicode_map' key to fix")

# â”€â”€ MAIN GENERATION LOOP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
os.makedirs(TRAIN_IMAGES, exist_ok=True)   # FILE OPERATION â€” ensure output folders exist
os.makedirs(TRAIN_LABELS, exist_ok=True)

generated = 0   # VARIABLE DECLARATION â€” counter for progress reporting

# INSTANTIATION â€” launches Playwright's headless Chromium browser
with sync_playwright() as pw:
    browser = pw.chromium.launch()     # METHOD CALL â€” opens a headless Chrome instance
    page    = browser.new_page()       # METHOD CALL â€” opens a new browser tab

    # LOOP â€” generates NUM_PARAGRAPHS paragraph images
    for para_idx in range(NUM_PARAGRAPHS):

        # VARIABLE DECLARATION â€” randomly decide how many lines this paragraph has
        num_lines = random.randint(LINES_PER_PARA_MIN, LINES_PER_PARA_MAX)

        # LIST/DICT/SET â€” each entry is a list of (class_idx, unicode_char) tuples
        # representing one line of Karen text
        lines_of_syllables = []

        for _ in range(num_lines):
            # VARIABLE DECLARATION â€” how many syllables on this line
            n_syl = random.randint(SYLLABLES_PER_LINE_MIN, SYLLABLES_PER_LINE_MAX)

            # LOOP â€” randomly pick n_syl syllables from the full 6,341-class list
            chosen = random.choices(syllable_list, k=n_syl)

            line = []
            for cls_idx, syllable_name in chosen:
                # CONDITIONAL â€” use real Karen Unicode if the map exists, else use name
                if unicode_map and str(cls_idx) in unicode_map:
                    unicode_str = unicode_map[str(cls_idx)]
                else:
                    unicode_str = syllable_name   # Latin fallback for testing
                line.append((cls_idx, unicode_str))

            lines_of_syllables.append(line)

        # STRING FORMATTING â€” build the HTML for this paragraph
        html = build_paragraph_html(lines_of_syllables, Path(FONT_PATH).as_posix())

        # METHOD CALL â€” set the viewport to exactly our canvas size so screenshots are consistent
        page.set_viewport_size({"width": IMG_W, "height": IMG_H})

        # METHOD CALL â€” loads the HTML string directly into the browser (no file needed)
        page.set_content(html, wait_until="networkidle")

        # VARIABLE DECLARATION â€” unique filename for this paragraph image
        uid = uuid.uuid4().hex[:10]
        img_path   = os.path.join(TRAIN_IMAGES, f"para_{uid}.jpg")
        label_path = os.path.join(TRAIN_LABELS, f"para_{uid}.txt")

        # METHOD CALL â€” takes a screenshot of the rendered paragraph at full canvas size
        page.screenshot(path=img_path, clip={"x": 0, "y": 0, "width": IMG_W, "height": IMG_H})

        # LOOP â€” iterates over every syllable span in every line to get its bounding box
        for line in lines_of_syllables:
            for cls_idx, unicode_str in line:
                # METHOD CALL â€” finds all <span> elements with this class index
                # querySelectorAll returns a list; we use the first unprocessed one
                spans = page.query_selector_all(f'span[data-class="{cls_idx}"]')

                for span in spans:
                    # METHOD CALL â€” getBoundingClientRect gives pixel x, y, width, height
                    # relative to the top-left of the viewport â€” exactly what we need
                    rect = span.bounding_box()

                    # CONDITIONAL â€” skip spans that rendered off-canvas or have zero size
                    if rect is None:
                        continue
                    if rect['width'] < 2 or rect['height'] < 2:
                        continue
                    if rect['x'] + rect['width'] > IMG_W:
                        continue
                    if rect['y'] + rect['height'] > IMG_H:
                        continue

                    # FUNCTION CALL â€” write this syllable's normalized bounding box
                    # to the YOLO label file, appending one line per syllable
                    write_yolo_bbox(
                        label_path,
                        cls_idx,
                        rect['x'], rect['y'],
                        rect['width'], rect['height'],
                        IMG_W, IMG_H
                    )

        generated += 1
        # OUTPUT/PRINT â€” progress update every 100 images so you can monitor the run
        if generated % 100 == 0:
            print(f"  Generated {generated}/{NUM_PARAGRAPHS} paragraph images...")

    browser.close()   # METHOD CALL â€” cleanly shuts down the headless browser

print(f"\nâœ… Paragraph dataset generation complete!")
print(f"   {generated} images â†’ {TRAIN_IMAGES}")
print(f"   {generated} label files â†’ {TRAIN_LABELS}")
print(f"   These are appended to your existing syllable dataset for v6 retraining.")
