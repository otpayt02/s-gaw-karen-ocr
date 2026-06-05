# save as split_rows_from_dict_images.py
import cv2
import numpy as np
import os
from glob import glob

BASE_DIR = os.path.join(os.path.expanduser("~"), "Projects", "karen_lang_trans")
DICT_IMAGES_DIR = os.path.join(BASE_DIR, "dict_images")
DICT_ROWS_DIR = os.path.join(BASE_DIR, "dict_rows")

os.makedirs(DICT_ROWS_DIR, exist_ok=True)

def crop_table_region(gray):
    _, th = cv2.threshold(gray, 0, 255,
                          cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    vertical_profile = np.sum(th, axis=1)
    rows = np.arange(len(vertical_profile))

    mask = vertical_profile > (0.1 * vertical_profile.max())
    if not np.any(mask):
        return gray

    top = rows[mask][0]
    bottom = rows[mask][-1]

    table = gray[top:bottom+1, :]
    _, th2 = cv2.threshold(table, 0, 255,
                           cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    horiz_profile = np.sum(th2, axis=0)
    cols = np.arange(len(horiz_profile))
    mask2 = horiz_profile > (0.1 * horiz_profile.max())
    if not np.any(mask2):
        return table

    left = cols[mask2][0]
    right = cols[mask2][-1]
    return gray[top:bottom+1, left:right+1]

def split_into_row_strips(table_gray, min_gap_px=8, min_row_height=20):
    _, th = cv2.threshold(table_gray, 0, 255,
                          cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    hproj = np.sum(th, axis=1)
    H = table_gray.shape[0]

    gap_threshold = 0.05 * hproj.max()
    is_gap = hproj < gap_threshold

    row_bounds = []
    in_row = False
    start = 0

    for y in range(H):
        if not is_gap[y] and not in_row:
            in_row = True
            start = y
        elif is_gap[y] and in_row:
            in_row = False
            end = y
            if end - start >= min_row_height:
                row_bounds.append((start, end))

    if in_row:
        end = H - 1
        if end - start >= min_row_height:
            row_bounds.append((start, end))

    merged = []
    for y1, y2 in row_bounds:
        if not merged:
            merged.append([y1, y2])
        else:
            py1, py2 = merged[-1]
            if y1 - py2 < min_gap_px:
                merged[-1][1] = y2
            else:
                merged.append([y1, y2])

    return [(a, b) for a, b in merged]

def extract_row_images(page_path):
    page_name = os.path.splitext(os.path.basename(page_path))[0]
    out_dir = os.path.join(DICT_ROWS_DIR, page_name)
    os.makedirs(out_dir, exist_ok=True)

    page = cv2.imread(page_path)
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)

    table = crop_table_region(gray)
    rows = split_into_row_strips(table)

    row_paths = []
    for i, (y1, y2) in enumerate(rows, start=1):
        crop = table[y1:y2, :]
        row_name = f"{page_name}_row{i:03d}.png"
        row_path = os.path.join(out_dir, row_name)
        cv2.imwrite(row_path, crop)
        row_paths.append(row_path)

    return row_paths

def main():
    page_paths = sorted(
        glob(os.path.join(DICT_IMAGES_DIR, "*.jpg")) +
        glob(os.path.join(DICT_IMAGES_DIR, "*.png"))
    )

    print("Found", len(page_paths), "page images")
    for page_path in page_paths:
        print("Processing", page_path)
        rows = extract_row_images(page_path)
        print("  ->", len(rows), "row images")

if __name__ == "__main__":
    main()