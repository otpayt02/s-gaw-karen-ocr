import pdfplumber
import json
import os
import re

# ==============================================================================
# KNU FONT CHARACTER MAP
# Maps KNU-encoded ASCII characters to Myanmar Unicode codepoints
# ==============================================================================

KNU_MAP = {
    # Base consonants
    'u': '\u1000',  # က
    'c': '\u1001',  # ခ
    'g': '\u1002',  # ဂ
    'C': '\u1003',  # ဃ
    'i': '\u1004',  # င
    'p': '\u1018',  # ပ
    'q': '\u1006',  # ဆ
    'Z': '\u1007',  # ဇ
    'P': '\u1008',  # ဈ
    'n': '\u1014',  # န
    'm': '\u1019',  # မ
    'y': '\u101A',  # ယ
    'r': '\u101B',  # ရ
    'l': '\u101C',  # လ
    'w': '\u101D',  # ဝ
    'o': '\u101E',  # သ
    'h': '\u101F',  # ဟ
    'e': '\u1021',  # အ
    'E': '\u1021',  # အ alt
    'b': '\u1015',  # ပ
    'k': '\u1016',  # ဖ
    'x': '\u1011',  # ဗ
    'v': '\u1009',  # ဉ
    'j': '\u100A',  # ည
    'D': '\u100A',  # ည alt
    's': '\u1005',  # စ
    't': '\u1000',  # က alt
    'f': '\u101C',  # လ alt
    '&': '\u1021',  # အ alt
    # Vowels / diacritics / tones
    '>': '\u102D',  # ိ
    'G': '\u102E',  # ီ
    'H': '\u103D',  # ွ
    'J': '\u103C',  # ြ
    'X': '\u102C',  # ာ
    'L': '\u102C',  # ာ alt
    "'": '\u103A',  # ်
    '.': '\u1037',  # ့
    ',': '\u1036',  # ံ
    ';': '\u1038',  # း
    '<': '\u1039',  # ္
    '0': '\u1040',  # ၀
    'R': '\u103B',  # ျ
    'M': '\u1036',  # ံ alt
    '[': '\u1031',  # ေ
    ']': '\u1032',  # ဲ
    'z': '\u103F',  # ဿ
    'd': '\u102B',  # ာ
    # Uppercase phonetic values
    'S': '\u103B',  # ျ alt
    'V': '\u102C',  # ာ alt
    'K': '\u103D',  # ွ alt
    'A': '\u102D',  # ိ alt
    'B': '\u1015',  # ပ alt
    'F': '\u101C',  # လ alt
    'N': '\u1014',  # န alt
    'T': '\u1000',  # က alt
    'W': '\u101D',  # ဝ alt
    'I': '\u1004',  # င alt
    'O': '\u105A',  # ၚ Karen vowel
    'U': '\u1025',  # ဥ
    # Scanner-identified unmapped characters
    '%': '\u1038',  # း tone alt
    '+': '\u103C',  # ြ medial alt
    '/': '\u1039',  # ္ stacker alt
    '=': '\u102C',  # ာ vowel alt
    '_': '\u1038',  # း tone alt
}

# Characters silently dropped during KNU cleaning (not mapped, not Myanmar)
PASSTHROUGH_CHARS = set(' \t\n-{}*')


# ==============================================================================
# DEDUPLICATION
# The KNU font repeats every entry 4x (sometimes 2x or 8x) as an encoding
# artifact. These functions strip that repetition at both the raw KNU level
# and the post-conversion Unicode level.
# ==============================================================================

def deduplicate_block(text):
    """
    Given a string that may be an exact Nx repeat of a smaller chunk,
    return just one copy of that chunk.
    Tries divisors 8, 4, 2 in that order.
    Returns the original string if no clean repeat is found.
    """
    n = len(text)
    if n == 0:
        return text
    for div in [8, 4, 2]:
        if n % div == 0:
            chunk = text[:n // div]
            if chunk * div == text:
                return chunk
    return text


def deduplicate_unicode(text):
    """
    Walk through a Unicode string and remove all Nx repetition artifacts.
    Handles joined groups like ပါပါပါပါးးးး by finding each maximal
    repeating block independently and emitting just one copy.

    Example:
        ပါပါပါပါးးးး  →  ပါး
        ကကကက          →  က
        ယကဘိကွျသွဉညျ (x4)  →  ယကဘိကွျသွဉညျ
    """
    text = text.strip()
    if not text:
        return text

    # Fast path: whole string is a clean repeat
    result_fast = deduplicate_block(text)
    if result_fast != text:
        return result_fast

    # Slow path: walk position by position finding maximal repeat blocks
    result = []
    i = 0
    length = len(text)

    while i < length:
        remaining = text[i:]
        rem_len = len(remaining)
        found = False

        # Try treating the entire remaining string as a repeat
        for div in [4, 8, 2]:
            if rem_len % div == 0 and rem_len >= div * 2:
                chunk_len = rem_len // div
                chunk = remaining[:chunk_len]
                if chunk * div == remaining:
                    result.append(chunk)
                    i += rem_len
                    found = True
                    break

        if found:
            continue

        # Try progressively shorter substrings from position i
        for end in range(i + 2, length + 1):
            sub = text[i:end]
            sub_len = len(sub)
            matched = False
            for div in [4, 8, 2]:
                if sub_len % div == 0 and sub_len >= div * 2:
                    chunk_len = sub_len // div
                    chunk = sub[:chunk_len]
                    if chunk * div == sub:
                        result.append(chunk)
                        i = end
                        matched = True
                        found = True
                        break
            if matched:
                break

        if not found:
            # No repeat found — emit this character as-is and advance
            result.append(text[i])
            i += 1

    return ''.join(result)


# ==============================================================================
# KNU → UNICODE CONVERSION
# ==============================================================================

def clean_knu(knu_string):
    """Strip passthrough characters that have no Unicode mapping."""
    return ''.join(ch for ch in knu_string if ch not in PASSTHROUGH_CHARS)


def knu_to_unicode(knu_string):
    """
    Convert a raw KNU-encoded string to Myanmar Unicode.
    Steps:
      1. Strip the 4x repetition artifact from the raw KNU string
      2. Clean out passthrough characters
      3. Map each character through KNU_MAP
    """
    knu_string = deduplicate_block(knu_string.strip())
    knu_string = clean_knu(knu_string)
    result = []
    for ch in knu_string:
        if ch in KNU_MAP:
            result.append(KNU_MAP[ch])
        else:
            result.append(ch)  # kept for unmapped scanner to detect
    return ''.join(result)


# ==============================================================================
# PDF EXTRACTION
# Parses karen_dict.pdf page by page, detects KNU vs non-KNU font runs,
# and builds one JSON entry per KNU word cluster.
# ==============================================================================

def extract_dictionary(pdf_path, output_path):
    entries = []

    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")

        for page_num, page in enumerate(pdf.pages):
            chars = page.chars
            entry_buffer = {'knu_raw': '', 'unicode': '', 'english': '', 'page': 0}
            current_knu = []
            current_other = []
            last_font_was_knu = False

            for ch in chars:
                font = ch['fontname']
                text = ch['text']
                is_knu = 'KNU' in font

                if is_knu:
                    if not last_font_was_knu:
                        if current_other and entry_buffer['knu_raw']:
                            entry_buffer['english'] += ''.join(current_other).strip()
                            current_other = []
                        if entry_buffer['knu_raw']:
                            entries.append(dict(entry_buffer))
                        entry_buffer = {
                            'knu_raw': '',
                            'unicode': '',
                            'english': '',
                            'page': page_num + 1
                        }
                    current_knu.append(text)
                    last_font_was_knu = True
                else:
                    if last_font_was_knu:
                        raw = ''.join(current_knu)
                        entry_buffer['knu_raw'] = raw
                        entry_buffer['unicode'] = knu_to_unicode(raw)
                        current_knu = []
                    current_other.append(text)
                    last_font_was_knu = False

            # Flush last entry on the page
            if current_knu:
                raw = ''.join(current_knu)
                entry_buffer['knu_raw'] = raw
                entry_buffer['unicode'] = knu_to_unicode(raw)
            if current_other:
                entry_buffer['english'] += ''.join(current_other).strip()
            if entry_buffer['knu_raw']:
                entries.append(dict(entry_buffer))

            if (page_num + 1) % 10 == 0:
                print(f"  Page {page_num + 1}/{len(pdf.pages)} — {len(entries)} entries so far")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"\nComplete. {len(entries)} entries saved to {output_path}")
    print("\nSample output (first 5 entries):")
    for entry in entries[:5]:
        print(f"  Page     : {entry['page']}")
        print(f"  KNU raw  : {repr(entry['knu_raw'][:60])}")
        print(f"  Unicode  : {entry['unicode'][:60]}")
        print(f"  English  : {entry['english'][:80]}")
        print()

    # Unmapped character scanner
    print("Checking for remaining unmapped characters in unicode field...")
    allowed = set(' .,;:\'-\t\n0123456789abcdefghijklmnopqrstuvwxyz')
    unmapped = set()
    for entry in entries:
        for ch in entry['unicode']:
            if ord(ch) < 128 and ch not in allowed:
                unmapped.add(ch)
    if unmapped:
        print(f"  Still unmapped: {sorted(unmapped)}")
    else:
        print("  No unmapped characters found. KNU_MAP is complete.")

    return entries


# ==============================================================================
# IN-PLACE JSON REPAIR
# Run this if you already have a karendictdatabase.json and just need to
# fix the unicode field deduplication without re-running the PDF extraction.
# ==============================================================================

def repair_existing_json(json_path):
    """
    Load existing karendictdatabase.json, re-deduplicate every unicode field
    using the full block-walking algorithm, and save back in place.
    """
    print(f"Loading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        entries = json.load(f)

    print(f"Repairing {len(entries)} entries...")
    changed = 0
    for entry in entries:
        original = entry['unicode']
        fixed = deduplicate_unicode(original)
        if fixed != original:
            entry['unicode'] = fixed
            changed += 1

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"Repair complete. {changed} of {len(entries)} entries updated.")
    print("\nFirst 10 unicode values after repair:")
    for entry in entries[:10]:
        print(f"  {repr(entry['unicode'])}")

    return entries


# ==============================================================================
# PARAGRAPH GENERATOR
# Assembles the cleaned Unicode syllables into paragraph-length text blocks
# suitable for rendering into training images.
# ==============================================================================

def generate_paragraphs(json_path, output_path, min_chars=300, num_paragraphs=50):
    """
    Build Karen Unicode paragraphs from the dictionary JSON.
    - Deduplicates each unicode entry one final time at assembly
    - Skips entries that still contain ASCII artifacts
    - Joins syllables without spaces (authentic Karen script layout)
    - Breaks paragraphs at tone marker း boundaries
    """
    print(f"Loading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        entries = json.load(f)

    def is_clean(text):
        for ch in text:
            if ord(ch) < 128 and ch not in " .,;:'-\n":
                return False
        return True

    paragraphs = []
    current = ''

    for entry in entries:
        raw = entry['unicode'].strip()
        if not raw:
            continue

        # Final deduplication pass at assembly time
        syllable = deduplicate_unicode(raw)

        # Skip if ASCII artifacts remain after dedup
        if not is_clean(syllable):
            continue

        current += syllable

        # Break paragraph at a tone marker boundary once long enough
        if len(current) >= min_chars and '\u1038' in current[-20:]:
            paragraphs.append(current.strip())
            current = ''
            if len(paragraphs) >= num_paragraphs:
                break

    # Flush any remainder
    if current.strip() and len(paragraphs) < num_paragraphs:
        paragraphs.append(current.strip())

    with open(output_path, 'w', encoding='utf-8') as f:
        for i, para in enumerate(paragraphs):
            f.write(f"--- Paragraph {i+1} ---\n")
            f.write(para + '\n\n')

    print(f"\n{len(paragraphs)} Karen Unicode paragraphs saved to {output_path}")
    print("\nSample (first 2 paragraphs):")
    for para in paragraphs[:2]:
        print(f"\n{para[:400]}...")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    base_dir  = os.path.dirname(os.path.abspath(__file__))
    pdf_path  = os.path.join(base_dir, 'karen_dict.pdf')
    json_path = os.path.join(base_dir, 'karendictdatabase.json')
    para_path = os.path.join(base_dir, 'karen_paragraphs.txt')

    if os.path.exists(json_path):
        # JSON already built — repair deduplication in place, then generate paragraphs
        print("Existing JSON found. Running in-place repair...\n")
        repair_existing_json(json_path)
        print()
        generate_paragraphs(json_path, para_path)

    elif os.path.exists(pdf_path):
        # Fresh run — extract from PDF, then generate paragraphs
        extract_dictionary(pdf_path, json_path)
        print()
        generate_paragraphs(json_path, para_path)

    else:
        print(f"ERROR: Neither found:")
        print(f"  {json_path}")
        print(f"  {pdf_path}")
        print("Place karen_dict.pdf in the project folder and re-run.")