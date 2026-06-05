# ============================================================
# FILE: 4_syllable_gen.py
# PURPOSE: Generates the complete list of all valid Sgaw Karen
#          syllable combinations (base + medial + vowel + tone)
#          and saves them as both a CSV and a JSON class list.
#          This file defines the 6,341 class universe for the
#          entire OCR system.
# PIPELINE POSITION: Step 0b — Class list generation (run before training)
# REQUIRES: Nothing (standalone generator)
# PRODUCES: karen_syllables.csv, karen_class_list.json
# ============================================================

# IMPORT — provides itertools.product for generating all combinations
import itertools

# IMPORT — csv for writing the syllable table
import csv

# IMPORT — json for saving the class list
import json

# IMPORT — os for output directory creation
import os

# LIST/DICT/SET — all Sgaw Karen base consonants with romanized names
# WHY: the romanized name becomes the human-readable syllable label
BASE_CONSONANTS = [
    ('က', 'huh'),  ('ခ', 'hkuh'), ('ဂ', 'ghuh'), ('ဃ', 'hcah'), ('င', 'nguh'),
    ('စ', 'suh'),  ('ဆ', 'shuh'), ('ဇ', 'zuh'),  ('ည', 'nyuh'), ('တ', 'tuh'),
    ('ထ', 'htuh'), ('ဒ', 'duh'),  ('န', 'nuh'),  ('ပ', 'pbuh'), ('ဖ', 'hpuh'),
    ('ဘ', 'buh'),  ('မ', 'muh'),  ('ယ', 'yuh'),  ('ရ', 'ruh'),  ('လ', 'luh'),
    ('ဝ', 'wuh'),  ('သ', 'thuh'), ('ဟ', 'huh'),  ('အ', 'uh')
]

# LIST/DICT/SET — medial consonants with romanized names
# WHY: empty string = no medial (the majority of syllables)
MEDIALS = [
    ('', ''),
    ('\u103c', 'medra'),
    ('\u103d', 'medwa'),
    ('\u103e', 'medgha')
]

# LIST/DICT/SET — vowel markers with romanized names
VOWELS = [
    ('',       'uh'),
    ('\u102c', 'aa'),
    ('\u102d', 'i'),
    ('\u102e', 'ii'),
    ('\u102f', 'u'),
    ('\u1030', 'uu'),
    ('\u1032', 'ai'),
    ('\u1036', 'an'),
    ('\u103a', 'ah'),
    ('\u1031', 'e')
]

# LIST/DICT/SET — tone markers with romanized names
TONES = [
    ('',       't1'),
    ('\u1037', 't2'),
    ('\u1038', 't3'),
    ('\u1039', 't4'),
    ('\u103b', 't5'),
    ('\u103c', 't6')
]

# FUNCTION CALL — creates output directory
os.makedirs('/root/karen_lang_trans', exist_ok=True)

# VARIABLE DECLARATION — list to hold all generated syllable records
syllables = []

# VARIABLE DECLARATION — class index counter
idx = 0

# LOOP — generates every valid combination using itertools.product
for (base_uni, base_rom), (med_uni, med_rom), (vow_uni, vow_rom), (tone_uni, tone_rom) in         itertools.product(BASE_CONSONANTS, MEDIALS, VOWELS, TONES):

    # VARIABLE DECLARATION — full Unicode syllable string
    unicode_str = base_uni + med_uni + vow_uni + tone_uni

    # VARIABLE DECLARATION — full romanized syllable name
    # METHOD CALL — filter(None,...) removes empty strings before joining
    roman_parts = list(filter(None, [base_rom, med_rom, vow_rom, tone_rom]))
    roman_name  = '_'.join(roman_parts)

    # METHOD CALL — appends this syllable record to the list
    syllables.append({
        'index':   idx,
        'unicode': unicode_str,
        'roman':   roman_name
    })

    idx += 1

# OUTPUT/PRINT — reports total syllable count generated
print(f"Generated {len(syllables)} Karen syllable combinations")

# FILE OPERATION — saves syllables as a CSV table
with open('/root/karen_lang_trans/karen_syllables.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['index', 'unicode', 'roman'])
    # METHOD CALL — writes the column header row
    writer.writeheader()
    # METHOD CALL — writes all syllable rows
    writer.writerows(syllables)

# VARIABLE DECLARATION — builds the class list as ordered list of romanized names
class_list = [s['roman'] for s in syllables]

# FILE OPERATION — saves the class list as JSON for use in data.yaml generation
with open('/root/karen_lang_trans/karen_class_list.json', 'w', encoding='utf-8') as f:
    json.dump(class_list, f, ensure_ascii=False, indent=2)

print(f"Saved karen_syllables.csv and karen_class_list.json")
print(f"First syllable: {syllables[0]['roman']} ({syllables[0]['unicode']})")
print(f"Last syllable:  {syllables[-1]['roman']} ({syllables[-1]['unicode']})")
