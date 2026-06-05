import json, re, os

PROJECT_DIR = os.path.join(os.path.expanduser("~"), "Projects", "karen_lang_trans")
DICT_PDF    = os.path.join(PROJECT_DIR, "karen_dict.pdf")
GRAMMAR_PDF = os.path.join(PROJECT_DIR, "karen_grammar.pdf")
OUTPUT_JSON = os.path.join(PROJECT_DIR, "karen_dict_database.json")

CONSONANT_MAP = {
    "u":  ("\u1000", "guh"),
    "c":  ("\u1001", "hkuh"),
    "C":  ("\u1002", "ghuh"),
    "*":  ("\u1003", "hcah"),
    "i":  ("\u1004", "nguh"),
    "p":  ("\u1005", "suh_chuh"),   # á€…
    "q":  ("\u1006", "hsuh_shuh"),  # á€†
    "%S": ("\u1061", "shuh2"),
    "n":  ("\u100A", "nyuh"),
    "w":  ("\u1010", "tuh"),
    "x":  ("\u1011", "htuh"),
    "'":  ("\u1012", "duh"),
    "e":  ("\u1014", "nuh"),
    "y":  ("\u1015", "pbuh"),
    "z":  ("\u1016", "hpuh"),
    "b":  ("\u1018", "buh"),
    "r":  ("\u1019", "muh"),
    ",":  ("\u101A", "yuh"),
    "&":  ("\u101B", "ruh"),
    "v":  ("\u101C", "luh"),
    "0":  ("\u101D", "wuh"),
    "o":  ("\u101E", "thuh"),
    "[":  ("\u101F", "huh"),
    "t":  ("\u1021", "uh"),   # NO medials
    "{":  ("\u1027", "uh2"),  # NO medials
}
NO_MEDIAL = {"t", "{"}

VOWEL_MAP = {
    "g": ("\u102B", "ah"),
    "R": ("\u1036", "ee"),
    "X": ("\u1062", "er"),
    "m": ("\u1037", "ay"),
    "L": ("\u102E", "aw"),
    "H": ("\u102D", "oh"),
    "J": ("\u1032", "eh"),
    "l": ("\u1030", "oo"),
    "k": ("\u102F", "u"),
}

TONE_MAP = {
    "I": ("\u1052", "tone2_er_thee"),
    "P": ("\u1053", "tone3_ah_thee"),
    ">": ("\u1038", "tone4_pler_chee"),
    "O": ("\u1054", "tone5_hah_thee"),
    ":": ("\u1055", "tone6_geh_poh"),
}

MEDIAL_MAP = {
    "F":  ("\u103B", "med_ya"),
    "-":  ("\u103C", "med_ra"),
    "G":  ("\u103D", "med_wa"),
    "s":  ("\u1060", "med_la"),
    "H2": ("\u103E", "med_gha"),
}

ASAT_MAP = {
    "r~": {
        "karen_unicode": "\u1019\u103A",
        "english":       "maw",
        "romanized":     "maw",
        "label":         "muh_asat_maw",
    },
    "'~": {
        "karen_unicode": "\u1012\u103A",
        "english":       "dee",
        "romanized":     "dee",
        "label":         "duh_asat_dee",
    },
}


def decode(word: str) -> str:
    out, no_med, i = "", False, 0
    while i < len(word):
        two = word[i:i+2]
        if two == "%S":
            out += "\u1061"
            no_med = False
            i += 2
            continue
        if two in ASAT_MAP:
            out += ASAT_MAP[two]["karen_unicode"]
            i += 2
            continue
        ch = word[i]
        if ch in CONSONANT_MAP:
            out += CONSONANT_MAP[ch][0]
            no_med = ch in NO_MEDIAL
        elif ch in MEDIAL_MAP and not no_med:
            out += MEDIAL_MAP[ch][0]
        elif ch in TONE_MAP:
            out += TONE_MAP[ch][0]
        elif ch in VOWEL_MAP:
            out += VOWEL_MAP[ch][0]
        else:
            out += ch
        i += 1
    return out


def romanize(word: str) -> str:
    out, i = "", 0
    while i < len(word):
        two = word[i:i+2]
        if two == "%S":
            out += "shuh2"
            i += 2
            continue
        if two in ASAT_MAP:
            out += ASAT_MAP[two]["romanized"]
            i += 2
            continue
        ch = word[i]
        if ch in CONSONANT_MAP:
            out += CONSONANT_MAP[ch][1]
        elif ch in VOWEL_MAP:
            out += VOWEL_MAP[ch][1]
        elif ch in TONE_MAP:
            out += TONE_MAP[ch][1]
        elif ch in MEDIAL_MAP:
            out += MEDIAL_MAP[ch][1]
        i += 1
    return out or word


def build_karen_database():
    import pdfplumber

    db = {
        "metadata": {
            "tones": "6 â€” default_rise, er_thee(U+1052), ah_thee(U+1053), "
                     "pler_chee(U+1038), hah_thee(U+1054), geh_poh(U+1055)",
            "no_medial_consonants": ["uh (U+1021)", "uh2 (U+1027)"],
            "medial_wa_note": "Medial WA (U+103D) is a teardrop below; OH vowel (U+102D) is a circle above",
            "dot_vowel_note": "ay (U+1037) and ee (U+1036) dots are LEFT of any bottom medials",
        },
        "entries": {},
        "unicode_index": {},
        "english_index": {},
        "asat_contractions": ASAT_MAP,
    }

    for k, v in ASAT_MAP.items():
        db["entries"][k] = v
        db["unicode_index"][v["karen_unicode"]] = v

    pages = []
    for path in [DICT_PDF, GRAMMAR_PDF]:
        if not os.path.exists(path):
            print(f"WARNING: {path} not found")
            continue
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for pg in pdf.pages:
                t = pg.extract_text()
                if t:
                    pages.append(t)

    parsed = skipped = 0
    for page in pages:
        for line in page.split("\n"):
            line = line.strip()
            if not line:
                skipped += 1
                continue
            parts = re.split(r"\s{2,}", line, maxsplit=1)
            if len(parts) != 2:
                skipped += 1
                continue
            leg, eng = parts[0].strip(), parts[1].strip()
            if not leg or not eng:
                skipped += 1
                continue
            uni = decode(leg)
            entry = {
                "legacy_key":    leg,
                "karen_unicode": uni,
                "english":       eng,
                "romanized":     romanize(leg),
            }
            db["entries"][leg] = entry
            db["unicode_index"][uni] = entry
            for w in eng.lower().split()[:3]:
                cw = re.sub(r"[^a-z]", "", w)
                if len(cw) > 2:
                    db["english_index"].setdefault(cw, []).append(leg)
            parsed += 1

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print(f"Parsed: {parsed}  Skipped: {skipped}  Saved: {OUTPUT_JSON}")
    return db


if __name__ == "__main__":
    build_karen_database()
