# ============================================================
# FILE: 2_build_dict_data.py
# PURPOSE: Parses the Karen dictionary PDF, extracts syllable
#          entries, and writes them into karendictdatabase.json
#          with English meanings and Unicode strings. This is
#          Phase 2 of the translation chain — after this runs,
#          the pipeline shows real English meanings instead of
#          "no translation yet".
# PIPELINE POSITION: Step 8 — Populate real English translations
# REQUIRES: Karen dictionary PDF, karendictdatabase.json (bootstrap)
# PRODUCES: karendictdatabase.json (with English meanings filled in)
# ============================================================

# IMPORT — pdfplumber for extracting text from the Karen dictionary PDF
import pdfplumber

# IMPORT — json for reading and writing the dictionary file
import json

# IMPORT — re for regular expression pattern matching on extracted text
import re

# IMPORT — os for file path operations
import os

# VARIABLE DECLARATION — path to the Karen dictionary PDF file
PDF_PATH = '/root/karen_lang_trans/karen_dictionary.pdf'

# VARIABLE DECLARATION — path to the bootstrap dictionary to update
DICT_PATH = '/root/karen_lang_trans/karendictdatabase.json'

# FILE OPERATION — loads the existing bootstrap dictionary
with open(DICT_PATH, 'r', encoding='utf-8') as f:
    karen_dict = json.load(f)

# VARIABLE DECLARATION — counter for successfully matched entries
matched = 0

# EXCEPTION HANDLER — wraps the entire PDF parsing in try/except
# WHY: PDF text extraction can fail on corrupted or legacy-encoded pages;
#      we want partial results saved even if some pages error out
try:
    # FUNCTION CALL — opens the PDF file with pdfplumber
    with pdfplumber.open(PDF_PATH) as pdf:
        # LOOP — iterates over every page in the dictionary PDF
        for page_num, page in enumerate(pdf.pages):
            # METHOD CALL — extracts raw text from this page
            # WHY: Karen dictionary PDFs may use legacy ASCII encoding;
            #      we extract the raw text and then map it to Unicode
            text = page.extract_text()

            # CONDITIONAL — skips empty pages
            if not text:
                continue

            # LOOP — processes each line of text on this page
            for line in text.split('\n'):
                # METHOD CALL — looks for lines starting with a Karen syllable pattern
                # WHY: dictionary entries follow "syllable — english meaning" format
                match = re.match(r'^([\u1000-\u109f]+)\s*[—\-]\s*(.+)$', line.strip())

                # CONDITIONAL — processes matched dictionary entries only
                if match:
                    # VARIABLE DECLARATION — the Karen Unicode syllable string
                    karen_unicode = match.group(1)

                    # VARIABLE DECLARATION — the English definition text
                    english_meaning = match.group(2).strip()

                    # LOOP — searches all dictionary entries for this Unicode string
                    for robo_label, entry in karen_dict.items():
                        # CONDITIONAL — matches entries that have the same unicode value
                        if entry.get('unicode') == karen_unicode:
                            # VARIABLE DECLARATION — writes the English meaning
                            entry['english'] = english_meaning
                            matched += 1

except Exception as e:
    # OUTPUT/PRINT — reports parsing errors without crashing
    print(f"PDF parsing error: {e}")

# FILE OPERATION — saves the updated dictionary with English meanings
with open(DICT_PATH, 'w', encoding='utf-8') as f:
    json.dump(karen_dict, f, ensure_ascii=False, indent=2)

# OUTPUT/PRINT — reports how many entries received English translations
print(f"Updated {matched} entries with English meanings")
print(f"Saved to: {DICT_PATH}")
