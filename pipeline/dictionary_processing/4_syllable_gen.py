import json, csv, os

PROJECT_DIR = os.path.join(os.path.expanduser("~"), "Projects", "karen_lang_trans")

CONSONANTS = [
    ("u",  "\u1000", "guh",       True),
    ("c",  "\u1001", "hkuh",      True),
    ("C",  "\u1002", "ghuh",      True),
    ("*",  "\u1003", "hcah",      True),
    ("i",  "\u1004", "nguh",      True),
    ("p",  "\u1005", "suh_chuh",  True),   # စ
    ("q",  "\u1006", "hsuh_shuh", True),   # ဆ
    ("%S", "\u1061", "shuh2",     True),
    ("n",  "\u100A", "nyuh",      True),
    ("w",  "\u1010", "tuh",       True),
    ("x",  "\u1011", "htuh",      True),
    ("'",  "\u1012", "duh",       True),
    ("e",  "\u1014", "nuh",       True),
    ("y",  "\u1015", "pbuh",      True),
    ("z",  "\u1016", "hpuh",      True),
    ("b",  "\u1018", "buh",       True),
    ("r",  "\u1019", "muh",       True),
    (",",  "\u101A", "yuh",       True),
    ("&",  "\u101B", "ruh",       True),
    ("v",  "\u101C", "luh",       True),
    ("0",  "\u101D", "wuh",       True),
    ("o",  "\u101E", "thuh",      True),
    ("[",  "\u101F", "huh",       True),
    ("t",  "\u1021", "uh",        False),  # NO medials
    ("{",  "\u1027", "uh2",       False),  # NO medials
]

VOWELS = [
    ("",  "",       "a",  "bare default"),
    ("g", "\u102B", "ah", "TALL AA"),
    ("R", "\u1036", "ee", "anusvara dot — LEFT of bottom medials"),
    ("X", "\u1062", "er", "Karen-exclusive U+1062"),
    ("m", "\u1037", "ay", "dot below — LEFT of bottom medials"),
    ("L", "\u102E", "aw", "vowel sign II"),
    ("H", "\u102D", "oh", "circle ABOVE consonant"),
    ("J", "\u1032", "eh", "eh"),
    ("l", "\u1030", "oo", "oo"),
    ("k", "\u102F", "u",  "u short"),
]

TONES = [
    ("",  "",       "tone1_rise",       "default rising, no mark"),
    ("I", "\u1052", "tone2_er_thee",    "er thee — U+1052"),
    ("P", "\u1053", "tone3_ah_thee",    "ah thee — U+1053"),
    (">", "\u1038", "tone4_pler_chee", "pler chee — VISARGA U+1038"),
    ("O", "\u1054", "tone5_hah_thee",   "hah thee — U+1054"),
    (":", "\u1055", "tone6_geh_poh",   "geh poh — U+1055"),
]

MEDIALS = [
    ("F",  "\u103B", "med_ya",  "attaches below base"),
    ("-",  "\u103C", "med_ra",  "only premedial — wraps around base; dots inside ring"),
    ("G",  "\u103D", "med_wa",  "teardrop BELOW base in Karen"),
    ("s",  "\u1060", "med_la",  "Mon medial LA, attaches below"),
    ("H2", "\u103E", "med_gha", "attaches below base"),
]

ASAT_CONTRACTIONS = [
    ("\u1019", "\u103A", "muh_asat_maw", "maw", "muh + asat ligature"),
    ("\u1012", "\u103A", "duh_asat_dee", "dee", "duh + asat ligature"),
]


def gen_base():
    rows, cid = [], 0
    for asc, uni, rom, can in CONSONANTS:
        for vasc, vuni, vrom, vnote in VOWELS:
            for tasc, tuni, tname, tdesc in TONES:
                rows.append({
                    "class_id":        cid,
                    "label":           f"{rom}_{vrom}_{tname}",
                    "legacy_ascii":    asc + vasc + tasc,
                    "full_unicode":    uni + vuni + tuni,
                    "romanized":       f"{rom}-{vrom}",
                    "can_take_medial": can,
                    "vowel_note":      vnote,
                    "tone_desc":       tdesc,
                })
                cid += 1
    return rows, cid


def gen_medials(start):
    rows, cid = [], start
    eligible = [(asc, uni, rom) for asc, uni, rom, can in CONSONANTS if can]
    for asc, uni, rom in eligible:
        for masc, muni, mname, mnote in MEDIALS:
            for vasc, vuni, vrom, vnote in VOWELS[:5]:
                for tasc, tuni, tname, tdesc in TONES[:3]:
                    rows.append({
                        "class_id":     cid,
                        "label":        f"{rom}_{mname}_{vrom}_{tname}",
                        "legacy_ascii": asc + masc + vasc + tasc,
                        "full_unicode": uni + muni + vuni + tuni,
                        "romanized":    f"{rom}-{mname}-{vrom}",
                        "medial_note":  mnote,
                    })
                    cid += 1
    return rows, cid


def gen_asat(start):
    rows, cid = [], start
    for cuni, auni, label, rom, note in ASAT_CONTRACTIONS:
        rows.append({
            "class_id":     cid,
            "label":        label,
            "full_unicode": cuni + auni,
            "romanized":    rom,
            "note":         note,
        })
        cid += 1
    return rows


def write_csv(data, name):
    if not data:
        return
    p = os.path.join(PROJECT_DIR, name)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=data[0].keys())
        w.writeheader()
        w.writerows(data)
    print(f"  {name} ({len(data):,} rows)")


def write_json(data, name):
    p = os.path.join(PROJECT_DIR, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  {name} ({len(data):,} entries)")


def write_roboflow_classes(base, medial, asat):
    p = os.path.join(PROJECT_DIR, "roboflow_classes.txt")
    with open(p, "w", encoding="utf-8") as f:
        for row in base + medial + asat:
            f.write(row["label"] + "\n")
    total = len(base) + len(medial) + len(asat)
    print(f"  roboflow_classes.txt ({total:,} classes)")


if __name__ == "__main__":
    os.makedirs(PROJECT_DIR, exist_ok=True)

    base, nxt   = gen_base()           # 25×10×6 = 1,500
    medial, nxt = gen_medials(nxt)     # 23×5×5×3 = 1,725
    asat        = gen_asat(nxt)        # 2

    print(f"\n{'='*50}")
    print("  SGAW KAREN — SYLLABLE STATS")
    print(f"{'='*50}")
    print(f"  Base syllables   : {len(base):,}")
    print(f"  Medial syllables : {len(medial):,}")
    print(f"  ASAT classes     : {len(asat)}")
    print(f"  TOTAL classes    : {len(base)+len(medial)+len(asat):,}")
    print(f"{'='*50}\n")

    print(f"Writing files to: {PROJECT_DIR}")
    write_csv(base,   "karen_base_syllables.csv")
    write_csv(medial, "karen_medial_syllables.csv")
    write_csv(asat,   "karen_asat_contractions.csv")
    write_json(base + medial + asat, "karen_all_syllables.json")
    write_roboflow_classes(base, medial, asat)

    print("\nDone!")
