# IMPORT â€” re for Unicode codepoint inspection of Karen syllable strings
import re
# IMPORT â€” unicodedata for getting Unicode category and name of a codepoint
import unicodedata

# =============================================================================
# CANONICAL SGAW KAREN DICTIONARY SORT ORDER
# Source: UTN11_4.pdf page 33-34 (Sgaw Karen section)
# "Sorting: Sgaw Karen has four levels: consonant, medial, vowel, tone"
# BUT the actual dictionary sort is: consonant â†’ tone â†’ vowel â†’ medial
# because when -ah vowel is present, the vowel glyph is dropped â€” so
# the tone IS the distinguishing marker at level 2.
# =============================================================================

# LIST â€” The 25 Sgaw Karen consonants in dictionary order
# VARIABLE DECLARATION â€” each entry: (unicode_char, romanized_name)
CONSONANT_ORDER = [
    ("\u1000", "guh"),    ("\u1001", "hkuh"),  ("\u1002", "ghuh"),
    ("\u1003", "hcah"),   ("\u1004", "nguh"),  ("\u1005", "suhchuh"),
    ("\u1006", "shuh"),   ("\u1061", "shuh2"), ("\u100A", "nyuh"),
    ("\u1010", "tuh"),    ("\u1011", "htuh"),  ("\u1012", "duh"),
    ("\u1014", "nuh"),    ("\u1015", "pbuh"),  ("\u1016", "hpuh"),
    ("\u1018", "buh"),    ("\u1019", "muh"),   ("\u101A", "yuh"),
    ("\u101B", "ruh"),    ("\u101C", "luh"),   ("\u101D", "wuh"),
    ("\u101E", "thuh"),   ("\u101F", "huh"),   ("\u1021", "uh"),
    ("\u1027", "uh2"),
]

# LIST â€” Tones in dictionary iteration order
# WHY: After each consonant, the dictionary iterates through ALL tones
# before moving to vowels. The -ah vowel (U+102B) is written at the
# START of the tones section because bare -ah (tone1, no mark) is the
# "default/unmarked" syllable shape for each consonant. Then the 5
# explicit tone marks follow.
# VARIABLE DECLARATION â€” (unicode_codepoint_string, sort_rank, display_name)
TONE_ORDER = [
    ("",         0, "tone1-rise (default, no mark)"),   # bare: á€€, á€€á€¬ with no tone
    ("\u102B",   1, "-ah bare (U+102B, tone1 shape)"),  # â† ah STARTS the tone group
    ("\u1052",   2, "erthee (U+1052)"),
    ("\u1053",   3, "ahthee (U+1053)"),
    ("\u1038",   4, "plerchee / visarga (U+1038)"),
    ("\u1054",   5, "hahthee (U+1054)"),
    ("\u1055",   6, "gehpoh (U+1055)"),
]

# LIST â€” Vowels in dictionary iteration order (after tones are exhausted)
# Source: UTN11_4.pdf Order 3: 102B 1036 1062 102F 1030 1037 1032 102D 102E
# NOTE: U+102B (-ah) appears here in Unicode collation order, but your
# actual 1896 dictionary groups it WITH tones at the beginning of each
# consonant's section. The vowel list below is for NON-ah vowels only.
VOWEL_ORDER = [
    ("\u1036", 0, "ee (U+1036 anusvara dot)"),
    ("\u1062", 1, "er (U+1062 Karen-exclusive)"),
    ("\u102F", 2, "u (U+102F teardrop below)"),
    ("\u1030", 3, "oo (U+1030 double teardrop)"),
    ("\u1037", 4, "ay (U+1037 dot below)"),
    ("\u1032", 5, "eh (U+1032)"),
    ("\u102D", 6, "oh (U+102D circle above)"),
    ("\u102E", 7, "aw (U+102E vowel sign II)"),
]

# LIST â€” Medials in dictionary iteration order (last, after vowels)
# Source: UTN11_4.pdf Order 4: 103E 1060 103B 103C 103D
MEDIAL_ORDER = [
    ("\u103E", 0, "medha (U+103E)"),
    ("\u1060", 1, "medla (U+1060)"),
    ("\u103B", 2, "medya (U+103B)"),
    ("\u103C", 3, "medra (U+103C, pre-medial)"),
    ("\u103D", 4, "medwa (U+103D teardrop)"),
]

# LIST/DICT â€” ASAT contractions â€” sort AFTER their base consonant
# Source: UTN11_4.pdf lines 5-6: á€’(U+1012+U+103A) and á€™(U+1019+U+103A)
ASAT_CONTRACTIONS = {
    "\u1019\u103A": {"label": "muhasatmee", "sort_after": "\u1019"},
    "\u1012\u103A": {"label": "duhasatdee", "sort_after": "\u1012"},
}

# =============================================================================
# SYLLABLE DECOMPOSER
# =============================================================================

# LIST/DICT â€” fast lookup sets for each category
_CONSONANT_SET  = {c for c, _ in CONSONANT_ORDER}
_TONE_SET       = {t for t, _, _ in TONE_ORDER if t}
_VOWEL_SET      = {v for v, _, _ in VOWEL_ORDER}
_MEDIAL_SET     = {m for m, _, _ in MEDIAL_ORDER}
_CONSONANT_RANK = {c: i for i, (c, _) in enumerate(CONSONANT_ORDER)}
_TONE_RANK      = {t: r for t, r, _ in TONE_ORDER}
_VOWEL_RANK     = {v: r for v, r, _ in VOWEL_ORDER}
_MEDIAL_RANK    = {m: r for m, r, _ in MEDIAL_ORDER}

def decompose_syllable(unicode_str: str) -> dict:
    """
    FUNCTION DEFINITION â€” decompose_syllable
    Breaks a Karen Unicode syllable string into its structural parts.
    PARAMETER unicode_str: a Karen syllable like '\u1000\u102B\u1052'
    RETURN STATEMENT: dict with keys 'consonant', 'medials', 'vowel', 'tone'
    WHY: This is the analysis step before sorting. Every entry in the dictionary
    must be decomposed so we know which consonant section it belongs to, which
    tone group within that section, and which vowel sub-group.
    """
    result = {
        "consonant": "",
        "medials":   [],
        "vowel":     "",
        "tone":      "",
        "raw":       unicode_str,
    }

    # LOOP â€” iterate character by character through the syllable
    i = 0
    while i < len(unicode_str):
        # INDEX/SLICE â€” check for 2-char ASAT contraction first
        two = unicode_str[i:i+2]
        if two in ASAT_CONTRACTIONS:
            result["tone"] = two
            i += 2
            continue

        char = unicode_str[i]

        # CONDITIONAL â€” assign each character to its structural bucket
        if char in _CONSONANT_SET:
            result["consonant"] = char
        elif char in _MEDIAL_SET:
            result["medials"].append(char)
        elif char in _VOWEL_SET:
            result["vowel"] = char
        elif char in _TONE_SET:
            result["tone"] = char
        # CONDITIONAL â€” U+102B -ah vowel belongs to TONE group per your spec
        elif char == "\u102B":
            result["tone"] = char
        i += 1

    return result

def karen_sort_key(entry: dict) -> tuple:
    """
    FUNCTION DEFINITION â€” karen_sort_key
    Generates a (consonant_rank, tone_rank, vowel_rank, medial_rank) tuple
    that, when sorted, produces authentic Karen dictionary order.
    PARAMETER entry: a dict with at minimum a 'karen' key containing Unicode text
    RETURN STATEMENT: 4-tuple of ints for Python's sort() to compare
    WHY: Python's sort() needs numbers to compare. This function translates
    Karen linguistic structure into ranks so the list sorts in the same order
    as the physical 1896 printed dictionary.
    """
    parts = decompose_syllable(entry.get("karen", ""))

    # VARIABLE DECLARATION â€” rank each component, defaulting to 99 if unknown
    c_rank = _CONSONANT_RANK.get(parts["consonant"], 99)
    t_rank = _TONE_RANK.get(parts["tone"], 99)
    v_rank = _VOWEL_RANK.get(parts["vowel"], 99)

    # VARIABLE DECLARATION â€” for medials, use the rank of the FIRST medial present
    m_rank = min((_MEDIAL_RANK.get(m, 99) for m in parts["medials"]), default=99)

    return (c_rank, t_rank, v_rank, m_rank)

# =============================================================================
# SMART AUTO-CORRECTION GUARD
# Prevents propagating a correction to entries where the "same" string is
# actually a REAL WORD in a different consonant/vowel context.
# =============================================================================

def is_same_error_context(candidate_entry: dict, original_str: str,
                           error_type: str) -> bool:
    """
    FUNCTION DEFINITION â€” is_same_error_context
    Determines whether a given OCR entry is a REAL candidate for auto-correction
    or whether the match is a coincidental occurrence of the same characters.
    PARAMETER candidate_entry: the OCR entry being evaluated for auto-fix
    PARAMETER original_str: the wrong string the human just corrected
    PARAMETER error_type: 'tone_error', 'medial_error', or 'consonant_error'
    RETURN STATEMENT: True if safe to auto-correct, False if potentially a real word
    WHY: This is the critical guard. A tone error on á€€ (guh) should not
    auto-propagate to a totally different entry where the same tone sequence
    happens to appear on á€™ (muh). Each correction should only spread within
    the SAME consonant + vowel context.
    """
    candidate_karen = candidate_entry.get("karen", "")

    # CONDITIONAL â€” original string must actually appear in this entry at all
    if original_str not in candidate_karen:
        return False

    # EXCEPTION HANDLER â€” decompose both; if decomposition fails, skip
    try:
        orig_parts  = decompose_syllable(original_str)
        cand_parts  = decompose_syllable(candidate_karen)
    except Exception:
        return False

    # CONDITIONAL â€” for tone errors: only auto-fix if SAME consonant + vowel
    # A tone error on (guh + ee + wrong_tone) must NOT affect (muh + ee + same_tone)
    if error_type == "tone_error":
        return (orig_parts["consonant"] == cand_parts["consonant"] and
                orig_parts["vowel"]     == cand_parts["vowel"])

    # CONDITIONAL â€” for medial errors: only auto-fix if same consonant + vowel + tone
    if error_type == "medial_error":
        return (orig_parts["consonant"] == cand_parts["consonant"] and
                orig_parts["vowel"]     == cand_parts["vowel"] and
                orig_parts["tone"]      == cand_parts["tone"])

    # CONDITIONAL â€” for consonant errors: require vowel + tone + medials to match
    # A consonant swap could easily be a different real word
    if error_type == "consonant_error":
        return (orig_parts["vowel"]   == cand_parts["vowel"] and
                orig_parts["tone"]    == cand_parts["tone"] and
                orig_parts["medials"] == cand_parts["medials"])

    # CONDITIONAL â€” unknown error type â€” do NOT auto-propagate, be safe
    return False

def smart_propagate(original: str, corrected: str, all_entries: list,
                    error_type: str) -> tuple:
    """
    FUNCTION DEFINITION â€” smart_propagate
    The safe version of propagate_correction. Only applies the correction
    to entries that pass the is_same_error_context guard.
    PARAMETER original: wrong string
    PARAMETER corrected: human-verified correct string
    PARAMETER all_entries: full OCR results list
    PARAMETER error_type: from classify_error()
    RETURN STATEMENT: (updated_entries, auto_fixed_count, skipped_count)
    WHY: This is what makes the system smarter than brute-force find-and-replace.
    The guard preserves real words that happen to share characters with the
    error pattern, so you only get the corrections that are genuinely the same
    mistake repeated by the vision model.
    """
    import copy
    updated  = copy.deepcopy(all_entries)
    fixed    = 0
    skipped  = 0

    for entry in updated:
        # CONDITIONAL â€” check if this entry has the original error string at all
        if original not in entry.get("karen", ""):
            continue

        # FUNCTION CALL â€” run the context guard before touching anything
        if is_same_error_context(entry, original, error_type):
            entry["karen"] = entry["karen"].replace(original, corrected)
            fixed += 1
        else:
            # VARIABLE DECLARATION â€” count entries skipped because they might be real words
            skipped += 1

    return updated, fixed, skipped

# =============================================================================
# SORT REFERENCE PRINTER (useful for debug / UI display)
# =============================================================================

def print_sort_reference():
    """
    FUNCTION DEFINITION â€” print_sort_reference
    Prints the full 4-level sort reference to the terminal so you can
    visually verify the ordering matches the physical dictionary.
    WHY: When corrections shift entries around in the sorted view, you need
    a printed reference to confirm the app's order matches the real book.
    """
    print("=" * 60)
    print("SGAW KAREN DICTIONARY SORT ORDER REFERENCE")
    print("Source: UTN11_4.pdf pp.33-34")
    print("=" * 60)
    print("\nLEVEL 1 â€” CONSONANTS (25 total):")
    for i, (c, rom) in enumerate(CONSONANT_ORDER):
        print(f"  {i+1:02d}. {c}  ({rom})  U+{ord(c):04X}")

    print("\nLEVEL 2 â€” TONES (within each consonant section):")
    print("  NOTE: -ah vowel (U+102B) OPENS the tone group â€” it is NOT")
    print("  iterated with vowels. It is the bare/unmarked syllable shape.")
    for t, rank, name in TONE_ORDER:
        mark = f"U+{ord(t):04X}" if t else "no mark"
        print(f"  rank {rank}: {t or 'âˆ…'}  {mark}  â€” {name}")

    print("\nLEVEL 3 â€” VOWELS (after tones exhausted for each consonant):")
    for v, rank, name in VOWEL_ORDER:
        print(f"  rank {rank}: {v}  U+{ord(v):04X}  â€” {name}")

    print("\nLEVEL 4 â€” MEDIALS (innermost, after vowels):")
    for m, rank, name in MEDIAL_ORDER:
        print(f"  rank {rank}: {m}  U+{ord(m):04X}  â€” {name}")

    print("\nASAT CONTRACTIONS (sort after their base consonant):")
    for seq, info in ASAT_CONTRACTIONS.items():
        print(f"  {info['label']}: sorts after U+{ord(info['sort_after']):04X}")
    print("=" * 60)

if __name__ == "__main__":
    print_sort_reference()

    # VARIABLE DECLARATION â€” small test: sort 3 example syllables
    test_entries = [
        {"karen": "\u1000\u1052",    "definitions": ["test1"]},  # á€€ + erthee tone
        {"karen": "\u1000\u102B",    "definitions": ["test2"]},  # á€€ + ah (opens tones)
        {"karen": "\u1000\u1036",    "definitions": ["test3"]},  # á€€ + ee vowel
        {"karen": "\u1000\u1030\u1052", "definitions": ["test4"]},  # á€€ + oo + erthee
    ]

    # METHOD CALL â€” sort using our key function
    test_entries.sort(key=karen_sort_key)

    print("\nTest sort result (should match dictionary page order):")
    for e in test_entries:
        k = e["karen"]
        key = karen_sort_key(e)
        print(f"  {k}  sort_key={key}  â†’  {e['definitions']}")
