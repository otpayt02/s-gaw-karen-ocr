#!/usr/bin/env python3
"""
043_pdf_page_splitter_zoom.py
Pipeline position: STANDALONE — run locally before any OCR/translation step.
Requires: pip install pymupdf pillow
Input:    karen_dict.pdf  (place in same folder as this script)
Output:   karen_dict_pages/  folder containing two cropped+zoomed PNG images per page
          top half  → page_0001_top.png
          bottom half → page_0001_bot.png
"""

# IMPORT — brings in Python's built-in path and file tools
import os

# IMPORT — brings in sys for clean exit on errors
import sys

# IMPORT — PyMuPDF: the library that opens and renders PDF pages as images
# Install with: pip install pymupdf
try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed.  Run:  pip install pymupdf")
    sys.exit(1)

# IMPORT — Pillow: used to crop and save the top/bottom halves as PNG files
try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed.  Run:  pip install pillow")
    sys.exit(1)

# IMPORT — io: lets us pass image bytes between PyMuPDF and Pillow without touching disk
import io

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

# VARIABLE DECLARATION — path to the dictionary PDF sitting next to this script
PDF_PATH = "karen_dict.pdf"

# VARIABLE DECLARATION — folder where all output PNG images will be saved
OUTPUT_DIR = "karen_dict_pages"

# VARIABLE DECLARATION — render resolution.
# 300 DPI is the standard for OCR-quality images.
# Higher = larger files + sharper glyphs. 300 is the sweet spot.
DPI = 300

# VARIABLE DECLARATION — zoom factor applied when rendering each page.
# fitz uses a matrix where 1.0 = 72 DPI.  300/72 ≈ 4.17 → we multiply by this
# to get 300 DPI output.  This makes every glyph large enough to read clearly.
ZOOM = DPI / 72.0

# ─────────────────────────────────────────────────────────────
# FUNCTION DEFINITION — make_output_dir
# Creates the output folder if it does not already exist.
# Why: without this folder the script crashes trying to save images.
# ─────────────────────────────────────────────────────────────
def make_output_dir(path: str) -> None:
    # FUNCTION CALL — os.makedirs creates nested folders safely
    # exist_ok=True means it will not crash if the folder already exists
    os.makedirs(path, exist_ok=True)
    # OUTPUT/PRINT — tells the user where images are going
    print(f"Output folder ready: {path}")


# ─────────────────────────────────────────────────────────────
# FUNCTION DEFINITION — render_page_to_pil
# Takes a single fitz Page object and returns a Pillow Image object
# at the target DPI.
# Why: fitz renders the PDF vector/text at high resolution so Karen
# glyphs are crisp enough for vision models or human reading.
# ─────────────────────────────────────────────────────────────
def render_page_to_pil(page: fitz.Page, zoom: float) -> Image.Image:
    # INSTANTIATION — fitz.Matrix scales the render by zoom factor on both axes
    mat = fitz.Matrix(zoom, zoom)

    # METHOD CALL — get_pixmap renders the page to a raw pixel buffer
    # ARGUMENT: matrix=mat  applies our zoom scaling
    # ARGUMENT: alpha=False  skips transparency channel, giving a clean RGB image
    pix = page.get_pixmap(matrix=mat, alpha=False)

    # METHOD CALL — tobytes("png") converts the raw pixel buffer to PNG bytes
    png_bytes = pix.tobytes("png")

    # FUNCTION CALL — Image.open reads those PNG bytes into a Pillow Image object
    # io.BytesIO wraps the bytes so Pillow can read them like a file
    img = Image.open(io.BytesIO(png_bytes))

    # RETURN STATEMENT — sends the Pillow Image back to the caller
    return img


# ─────────────────────────────────────────────────────────────
# FUNCTION DEFINITION — split_and_save
# Takes a Pillow Image and a page number, crops it into top and bottom halves,
# and saves each half as a numbered PNG file.
# Why: splitting each dictionary page into two halves doubles the effective
# zoom level when the image is later sent for OCR or visual inspection,
# making every entry easier to read.
# ─────────────────────────────────────────────────────────────
def split_and_save(img: Image.Image, page_num: int, out_dir: str) -> None:
    # VARIABLE DECLARATION — get the pixel dimensions of the full rendered page
    width, height = img.size

    # VARIABLE DECLARATION — midpoint pixel row that divides top from bottom
    mid = height // 2

    # METHOD CALL — img.crop cuts a rectangular region from the image
    # ARGUMENT: (left, upper, right, lower) in pixels
    # Top half: from row 0 down to the midpoint
    top_half = img.crop((0, 0, width, mid))

    # METHOD CALL — bottom half: from midpoint down to the last pixel row
    bot_half = img.crop((0, mid, width, height))

    # STRING FORMATTING — build zero-padded filenames so files sort correctly
    # e.g. page 1 → page_0001_top.png, page 1896 → page_1896_bot.png
    top_name = os.path.join(out_dir, f"page_{page_num:04d}_top.png")
    bot_name = os.path.join(out_dir, f"page_{page_num:04d}_bot.png")

    # METHOD CALL — save each half as a PNG file to disk
    top_half.save(top_name)
    bot_half.save(bot_name)


# ─────────────────────────────────────────────────────────────
# FUNCTION DEFINITION — main
# Orchestrates the full pipeline:
#   open PDF → loop pages → render → split → save → report progress
# ─────────────────────────────────────────────────────────────
def main() -> None:
    # CONDITIONAL — check the PDF exists before trying to open it
    if not os.path.exists(PDF_PATH):
        # OUTPUT/PRINT — clear error telling the user exactly what to fix
        print(f"ERROR: '{PDF_PATH}' not found.")
        print("Place karen_dict.pdf in the same folder as this script and re-run.")
        # FUNCTION CALL — exits Python with error code 1
        sys.exit(1)

    # FUNCTION CALL — make_output_dir ensures the output folder exists
    make_output_dir(OUTPUT_DIR)

    # INSTANTIATION — fitz.open loads the PDF into memory
    # Why: this gives us access to every page as a renderable object
    doc = fitz.open(PDF_PATH)

    # VARIABLE DECLARATION — total page count, printed for the user's reference
    total_pages = len(doc)
    print(f"PDF loaded: {total_pages} pages found in '{PDF_PATH}'")
    print(f"Rendering at {DPI} DPI, splitting each page into top + bottom halves...")
    print("This will produce two PNG files per page.")
    print()

    # LOOP — iterate over every page in the PDF, one at a time
    for page_index in range(total_pages):
        # VARIABLE DECLARATION — human-readable page number (1-based, not 0-based)
        page_num = page_index + 1

        # METHOD CALL — doc.load_page returns a fitz Page object for this page
        page = doc.load_page(page_index)

        # FUNCTION CALL — render the page to a Pillow Image at our target DPI
        img = render_page_to_pil(page, ZOOM)

        # FUNCTION CALL — split the image in half and save both halves to disk
        split_and_save(img, page_num, OUTPUT_DIR)

        # OUTPUT/PRINT — progress report every 10 pages so the user knows it's working
        if page_num % 10 == 0 or page_num == total_pages:
            print(f"  Processed page {page_num}/{total_pages} → "
                  f"page_{page_num:04d}_top.png + page_{page_num:04d}_bot.png")

    # METHOD CALL — close the PDF to release file handles and memory
    doc.close()

    # OUTPUT/PRINT — final success summary
    print()
    print(f"Done. {total_pages * 2} image files saved to: {OUTPUT_DIR}/")
    print("Each dictionary page was split into a top half and bottom half PNG.")
    print("Images are zoomed to 300 DPI — every Karen glyph is clearly readable.")


# CONDITIONAL — standard Python entry point guard
# This block only runs when you execute this file directly (python 043_pdf_page_splitter_zoom.py)
# It does NOT run if another script imports this file as a module
if __name__ == "__main__":
    main()