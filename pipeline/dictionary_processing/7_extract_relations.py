import os, json, re

PROJECT_ROOT      = os.path.dirname(os.path.abspath(__file__))
DICT_FILE         = os.path.join(PROJECT_ROOT, "karen_dict_full.json")
PARTS_SPEECH_FILE = os.path.join(PROJECT_ROOT, "parts_speech.json")

# VARIABLE DECLARATION — all relation markers we scan for in definitions
# each key is the output field name, value is the list of trigger strings
RELATION_MARKERS = {
    "etymology":         ["from "],
    "compound_entry":    ["co. ", "comp. "],
    "cross_reference":   ["see ", "cf. "],
    "ditto_of":          ["do. "],
    "analogous_terms":   ["analogous", "analogously", "anal. "],
}

# VARIABLE DECLARATION — regex that pulls Karen Unicode text after a marker
KAREN_RE = re.compile(r'[\u1000-\u109F\uAA60-\uAA7F][\u1000-\u109F\uAA60-\uAA7F\s\u102B-\u1032\u1036-\u1039\u103A-\u103F]*')


def load_json(path, default):
    # FILE OPERATION — loads JSON safely, returns default on missing or corrupt file
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default


def save_json(path, data):
    # FILE OPERATION — atomic write to prevent corruption on crash
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def extract_after_marker(definition_text, marker):
    # FUNCTION DEFINITION — finds a marker string in a definition and extracts
    # the Karen Unicode text that immediately follows it
    # ARGUMENT — definition_text: one definition string from the 'definitions' list
    # ARGUMENT — marker: trigger string like "co. " or "from " or "see "
    lower = definition_text.lower()
    idx   = lower.find(marker.lower())
    if idx == -1:
        return None
    # INDEX/SLICE — grab the text that starts right after the marker
    after = definition_text[idx + len(marker):]
    match = KAREN_RE.search(after)
    if match:
        return match.group(0).strip()
    # CONDITIONAL — if no Karen text follows, grab the next English word instead
    # this handles cases like "see also brightness" where the target is English
    english_match = re.match(r'[A-Za-z][A-Za-z\s\-]{1,40}', after)
    if english_match:
        return english_match.group(0).strip()
    return None


def build_parts_speech():
    # FUNCTION DEFINITION — main builder: iterates every entry in the dictionary,
    # scans all definitions for relation markers, and writes parts_speech.json
    entries = load_json(DICT_FILE, [])
    print(f"📖 Loaded {len(entries)} dictionary entries.")

    # VARIABLE DECLARATION — the output structure we will populate and save
    output = {
        "etymology":       {},   # headword → original form it derived from
        "compound_entry":  {},   # headword → list of compounds it appears in
        "cross_reference": {},   # headword → list of see/cf targets
        "ditto_of":        {},   # headword → the headword it duplicates
        "analogous_terms": {},   # headword → list of analogous headwords
        "part_of_speech":  {},   # headword → v.i. / v.t. / n. / adj. etc.
    }

    # VARIABLE DECLARATION — grammar label patterns to extract part of speech
    POS_RE = re.compile(
        r'\b(v\.i\.|v\.t\.|v\.|n\.|adj\.|adv\.|prep\.|conj\.|pron\.|interj\.|part\.)\b'
    )

    stats = {k: 0 for k in output}

    for entry in entries:
        karen = entry.get("karen", "").strip()
        if not karen:
            continue

        definitions = entry.get("definitions", [])

        for defn in definitions:
            if not isinstance(defn, str):
                continue

            # LOOP — check every relation marker category against this definition
            for field, markers in RELATION_MARKERS.items():
                for marker in markers:
                    result = extract_after_marker(defn, marker)
                    if result:
                        # CONDITIONAL — compound and cross_reference can have multiple
                        if field in ("compound_entry", "cross_reference", "analogous_terms"):
                            output[field].setdefault(karen, [])
                            if result not in output[field][karen]:
                                output[field][karen].append(result)
                        else:
                            # CONDITIONAL — etymology and ditto_of take only one value
                            if karen not in output[field]:
                                output[field][karen] = result
                        stats[field] += 1

            # VARIABLE DECLARATION — extract grammar label from this definition
            pos_match = POS_RE.search(defn)
            if pos_match:
                pos = pos_match.group(1)
                if karen not in output["part_of_speech"]:
                    output["part_of_speech"][karen] = pos
                    stats["part_of_speech"] += 1

        # CONDITIONAL — also check if Gemini already tagged fields directly on entry
        for field in ("etymology", "compound_entry", "cross_reference",
                      "ditto_of", "analogous_terms", "part_of_speech",
                      "interchangeable_with"):
            val = entry.get(field)
            if val:
                mapped = field if field in output else "cross_reference"
                if isinstance(val, list):
                    output[mapped].setdefault(karen, [])
                    for v in val:
                        if v not in output[mapped][karen]:
                            output[mapped][karen].append(v)
                else:
                    if karen not in output[mapped]:
                        output[mapped][karen] = val

    save_json(PARTS_SPEECH_FILE, output)

    print(f"\n✅ parts_speech.json written → {PARTS_SPEECH_FILE}")
    print(f"\n📊 Extraction summary:")
    for field, count in stats.items():
        print(f"   {field:<20} {count} entries")


if __name__ == "__main__":
    build_parts_speech()