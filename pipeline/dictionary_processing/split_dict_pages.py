import fitz  # IMPORT â€” PyMuPDF, fitz is its internal module name
import cv2
import numpy as np
import os

# VARIABLE DECLARATION â€” input PDF in your project folder
PDF_PATH   = os.path.join(os.path.expanduser("~"), "Projects", "karen_lang_trans", "karendict.pdf")

# VARIABLE DECLARATION â€” output folder for all split JPG slices
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Projects", "karen_lang_trans", "dict_images")

# VARIABLE DECLARATION â€” zoom factor: 3.0 = 216 DPI, crisp enough for Gemini Vision
ZOOM = 3.0

os.makedirs(OUTPUT_DIR, exist_ok=True)


def find_table_bounds(gray):
    """
    FUNCTION DEFINITION â€” detects the pixel boundary of the printed text table
    by finding the outermost rows and columns that contain real ink.
    Removes ALL surrounding white margin before splitting.
    RETURNS: (top, bottom, left, right) as pixel integers.
    """
    # METHOD CALL â€” inverts so ink = 255 (white), background = 0 (black)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # METHOD CALL â€” sums ink pixels along every row and every column
    row_sums = np.sum(binary, axis=1)
    col_sums = np.sum(binary, axis=0)

    # VARIABLE DECLARATION â€” minimum ink count to treat a row/col as real content
    ROW_THRESHOLD = 50
    COL_THRESHOLD = 50

    #
