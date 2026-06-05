# ============================================================
# FILE: 017_analyze_detection_gaps.py
# PURPOSE: Reads detections_log.csv and identifies every Karen
#          syllable class the model MISSED in the validation set.
#          Produces a ranked gap report showing which consonants,
#          medials, vowels, and tones are underperforming.
#          This is your precision retraining hit list — instead
#          of retraining everything, we target only the 149 missed
#          classes with more synthetic data.
# PIPELINE POSITION: Step 11 — Gap analysis before retraining
# REQUIRES: detections_log.csv, karendictdatabase.json
# PRODUCES: /root/karen_lang_trans/detection_gap_report.txt
#           /root/karen_lang_trans/missed_syllables.json
# ============================================================

# IMPORT — csv for reading the detections log spreadsheet
import csv

# IMPORT — json for reading the dictionary and saving the gap report
import json

# IMPORT — os for file path operations
import os

# IMPORT — collections.Counter for tallying detections per class
from collections import Counter, defaultdict

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

# VARIABLE DECLARATION — path to the full validation detections CSV
CSV_PATH    = '/root/karen_lang_trans/detections_log.csv'

# VARIABLE DECLARATION — path to the syllable dictionary
DICT_PATH   = '/root/karen_lang_trans/karendictdatabase.json'

# VARIABLE DECLARATION — path to the validation images folder
VALID_DIR   = '/root/karen_dataset_yolov8/valid/images/'

# VARIABLE DECLARATION — output paths for the gap analysis files
GAP_REPORT  = '/root/karen_lang_trans/detection_gap_report.txt'
MISSED_JSON = '/root/karen_lang_trans/missed_syllables.json'

# VARIABLE DECLARATION — server log path for automatic documentation
SERVER_LOG  = '/root/karen_lang_trans/server_terminal_log.txt'

# ── LOAD RESOURCES ────────────────────────────────────────────────────────────

# FILE OPERATION — loads the syllable translation dictionary
with open(DICT_PATH, 'r', encoding='utf-8') as f:
    # VARIABLE DECLARATION — full 6341-entry dictionary
    karen_dict = json.load(f)

# ── BUILD DETECTED CLASS SET FROM CSV ────────────────────────────────────────

# VARIABLE DECLARATION — Counter that tallies how many times each
#                         Roboflow label was detected in the validation set
detected_counts = Counter()

# VARIABLE DECLARATION — set of all image names that HAD at least one detection
images_with_detection = set()

# FILE OPERATION — opens and reads the detections CSV
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    # INSTANTIATION — creates a DictReader so we access columns by name
    reader = csv.DictReader(f)

    # LOOP — iterates over every detection row in the CSV
    for row in reader:
        # METHOD CALL — counts this Roboflow label as detected
        # WHY: we want to know how many times each syllable was correctly found
        detected_counts[row['robo_label']] += 1

        # METHOD CALL — records this image as having a detection
        images_with_detection.add(row['image'])

# ── BUILD EXPECTED CLASS SET FROM VALID IMAGES ───────────────────────────────

# VARIABLE DECLARATION — dict mapping expected syllable name → list of image filenames
# WHY: each image filename encodes the ground truth syllable — this is what
#      SHOULD have been detected in every image
expected = defaultdict(list)

# LOOP — iterates over every validation image filename
for img_name in os.listdir(VALID_DIR):
    # CONDITIONAL — only processes image files
    if not img_name.endswith(('.jpg', '.jpeg', '.png')):
        continue

    # METHOD CALL — splits filename on underscore to find syllable name
    parts    = img_name.split('_')

    # VARIABLE DECLARATION — finds the Roboflow UUID hash position (8 alphanum chars)
    uuid_pos = next(
        (i for i, p in enumerate(parts) if len(p) == 8 and p.isalnum()),
        None
    )

    # VARIABLE DECLARATION — reconstructs the ground truth syllable name
    syl_name = '_'.join(parts[:uuid_pos]) if uuid_pos else img_name.split('.')[0]

    # METHOD CALL — adds this image to the expected list for its syllable
    expected[syl_name].append(img_name)

# ── FIND MISSED SYLLABLES ────────────────────────────────────────────────────

# VARIABLE DECLARATION — set of all syllable names that appear in valid images
expected_syllables = set(expected.keys())

# VARIABLE DECLARATION — set of all syllable names that were actually detected
# WHY: we look up each detected Roboflow label in the dictionary to get its
#      romanized syllable name for comparison
detected_syllables = set()
for robo_label, count in detected_counts.items():
    entry = karen_dict.get(robo_label, {})
    syl   = entry.get('syllable', '')
    if syl:
        detected_syllables.add(syl)

# VARIABLE DECLARATION — syllables present in valid images but never detected
missed_syllables = expected_syllables - detected_syllables

# ── ANALYZE PATTERNS IN MISSED SYLLABLES ─────────────────────────────────────

# VARIABLE DECLARATION — Counters for each component type
missed_bases   = Counter()
missed_medials = Counter()
missed_vowels  = Counter()
missed_tones   = Counter()

# LOOP — breaks each missed syllable name into its components
for syl in missed_syllables:
    # METHOD CALL — splits romanized name into parts e.g. 'uh_medgha_u_t6'
    parts = syl.split('_')

    # CONDITIONAL — extracts base consonant (always first part)
    if len(parts) >= 1:
        missed_bases[parts[0]] += 1

    # LOOP — identifies medials, vowels, tones by their prefix patterns
    for part in parts[1:]:
        # CONDITIONAL — medials always start with 'med'
        if part.startswith('med'):
            missed_medials[part] += 1
        # CONDITIONAL — tones always start with 't' followed by a digit
        elif part.startswith('t') and len(part) == 2 and part[1].isdigit():
            missed_tones[part] += 1
        # CONDITIONAL — everything else is a vowel marker
        else:
            missed_vowels[part] += 1

# ── WRITE GAP REPORT ─────────────────────────────────────────────────────────

# VARIABLE DECLARATION — builds the full report string
report_lines = [
    '=' * 72,
    '  KAREN OCR — DETECTION GAP REPORT',
    f'  Generated from: {CSV_PATH}',
    '=' * 72,
    '',
    f'Total syllable classes in validation set : {len(expected_syllables)}',
    f'Classes detected at least once           : {len(detected_syllables)}',
    f'Classes NEVER detected (missed)          : {len(missed_syllables)}',
    f'Detection coverage                       : {len(detected_syllables)/len(expected_syllables)*100:.1f}%',
    '',
    '─' * 72,
    'TOP MISSED BASE CONSONANTS (most to least missed)',
    '─' * 72,
]

# LOOP — adds each missed base consonant with its count
for base, count in missed_bases.most_common(15):
    report_lines.append(f'  {base:<12} → {count} missed syllables')

report_lines += [
    '',
    '─' * 72,
    'TOP MISSED MEDIALS',
    '─' * 72,
]
for med, count in missed_medials.most_common():
    report_lines.append(f'  {med:<12} → {count} missed syllables')

report_lines += [
    '',
    '─' * 72,
    'TOP MISSED VOWELS',
    '─' * 72,
]
for vow, count in missed_vowels.most_common():
    report_lines.append(f'  {vow:<12} → {count} missed syllables')

report_lines += [
    '',
    '─' * 72,
    'TOP MISSED TONES',
    '─' * 72,
]
for tone, count in missed_tones.most_common():
    report_lines.append(f'  {tone:<12} → {count} missed syllables')

report_lines += [
    '',
    '─' * 72,
    'ALL MISSED SYLLABLES (for targeted retraining)',
    '─' * 72,
]
for syl in sorted(missed_syllables):
    report_lines.append(f'  {syl}')

report_lines.append('=' * 72)

# VARIABLE DECLARATION — joins all lines into a single string
report_text = '\n'.join(report_lines)

# FILE OPERATION — writes the gap report to disk
with open(GAP_REPORT, 'w', encoding='utf-8') as f:
    f.write(report_text)

# FILE OPERATION — saves the missed syllables list as JSON for 018_retrain_gaps.py
missed_list = sorted(list(missed_syllables))
with open(MISSED_JSON, 'w', encoding='utf-8') as f:
    json.dump(missed_list, f, ensure_ascii=False, indent=2)

# ── PRINT SUMMARY ─────────────────────────────────────────────────────────────

# OUTPUT/PRINT — prints the full report to terminal
print(report_text)

# OUTPUT/PRINT — confirms output files
print(f'\nGap report saved to : {GAP_REPORT}')
print(f'Missed list saved to: {MISSED_JSON}')
print(f'\nDownload both files + updated server_terminal_log.txt')

# ── APPEND TO SERVER LOG ──────────────────────────────────────────────────────

# IMPORT — datetime for timestamping
from datetime import datetime
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

# VARIABLE DECLARATION — log entry for this run
log_entry = f"""
────────────────────────────────────────────────────────────────────────────────
[{timestamp}] GAP ANALYSIS — 017_analyze_detection_gaps.py
COMMAND:
  python3 017_analyze_detection_gaps.py
OUTPUT:
  Total syllable classes in validation set : {{len(expected_syllables)}}
  Classes detected at least once           : {{len(detected_syllables)}}
  Classes NEVER detected                   : {{len(missed_syllables)}}
  Detection coverage                       : {{len(detected_syllables)/len(expected_syllables)*100:.1f}}%
FILES PRODUCED:
  {GAP_REPORT}
  {MISSED_JSON}
NEXT: Run 018_retrain_gap_classes.py to generate extra synthetic images
      for every missed syllable class and merge into the training set.
────────────────────────────────────────────────────────────────────────────────
"""

# FILE OPERATION — appends to server log
with open(SERVER_LOG, 'a', encoding='utf-8') as logf:
    logf.write(log_entry.format(
        len_expected=len(expected_syllables),
        len_detected=len(detected_syllables),
        len_missed=len(missed_syllables),
        coverage=len(detected_syllables)/len(expected_syllables)*100
    ))

print(f'\nServer log updated: {SERVER_LOG}')
