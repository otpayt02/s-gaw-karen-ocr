#!/usr/bin/env python3
# FILE: C:\langtrans\agent\correction_logger.py
# PURPOSE: Log corrections from Gemini output, auto-propagate fixes across full JSON
# REQUIRES: karendictfull.json exists at C:\langtrans\karendictfull.json
# PRODUCES: groundtruth_corrections.json updated, karendictfull.json auto-patched

import json
import datetime
import os

# VARIABLE DECLARATION: file paths — adjust if your folder is different
BASE_DIR = r"C:\Users\olive\Projects\karen_lang_trans\Fly_Solo_supervisor"
FULL_DICT_PATH = os.path.join(BASE_DIR, "karen_dict_full.json")
GROUNDTRUTH_PATH = os.path.join(BASE_DIR, "agent", "groundtruth_corrections.json")
MEMORY_PATH = os.path.join(BASE_DIR, "agent", "memory.json")

# FUNCTION DEFINITION: classifies what TYPE of mistake Gemini made
# PARAMETER predicted: the dict entry Gemini returned
# PARAMETER corrected: the dict entry YOU know is correct
# RETURN STATEMENT: a string label naming the error type
def classify_error(predicted, corrected):
    if predicted.get("karen") != corrected.get("karen"):
        return "wrong_headword"
    elif predicted.get("definitions") != corrected.get("definitions"):
        return "wrong_definition"
    else:
        return "formatting_error"

# FUNCTION DEFINITION: logs one correction event to groundtruth_corrections.json
# PARAMETER image_source: filename of the crop this correction came from (e.g. "page_0011_top.jpg")
# PARAMETER gemini_output: the dict entry Gemini predicted — paste from its JSON output
# PARAMETER human_correction: the correct entry YOU verified — what it should have said
# PARAMETER note: plain English reason why Gemini was wrong (optional but very useful)
def log_correction(image_source, gemini_output, human_correction, note=""):
    # FILE OPERATION: load existing corrections or start fresh
    if os.path.exists(GROUNDTRUTH_PATH):
        with open(GROUNDTRUTH_PATH, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"totalCorrections": 0, "corrections": []}

    # VARIABLE DECLARATION: build one correction record with all metadata
    error_type = classify_error(gemini_output, human_correction)
    record = {
        "timestamp": datetime.datetime.now().isoformat(),
        "image_source": image_source,
        "gemini_predicted": gemini_output,
        "human_verified": human_correction,
        "correction_type": error_type,
        "note": note
    }

    # METHOD CALL: add to list and increment counter
    data["corrections"].append(record)
    data["totalCorrections"] += 1

    # FILE OPERATION: write back to disk immediately — never lose a correction
    with open(GROUNDTRUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Correction #{data['totalCorrections']} logged. Type: {error_type}")

    # FUNCTION CALL: immediately scan full dictionary for same error pattern
    auto_propagate(record)


# FUNCTION DEFINITION: THE AUTO-PROPAGATION ENGINE
# This is the answer to your core question — finds every similar mistake across ALL entries
# PARAMETER correction_record: the correction you just logged — used as the pattern to search for
def auto_propagate(correction_record):
    if not os.path.exists(FULL_DICT_PATH):
        print("⚠️  karendictfull.json not found — skipping auto-propagation.")
        return

    # FILE OPERATION: load the full dictionary JSON
    with open(FULL_DICT_PATH, encoding="utf-8") as f:
        full_dict = json.load(f)

    error_type = correction_record["correction_type"]
    predicted = correction_record["gemini_predicted"]
    corrected = correction_record["human_verified"]
    fix_count = 0

    # LOOP: scan every entry in the full dictionary for the same error pattern
    for entry in full_dict:
        changed = False

        # CONDITIONAL: wrong_headword — find all entries with the same wrong Karen headword
        if error_type == "wrong_headword":
            if entry.get("karen") == predicted.get("karen"):
                # VARIABLE DECLARATION: mark this entry as needing human review
                # We flag it rather than auto-change headwords — Karen script is too critical to guess
                entry["_needs_review"] = True
                entry["_review_reason"] = f"Headword matches known Gemini error: {predicted.get('karen')}"
                changed = True

        # CONDITIONAL: wrong_definition — find all entries with the same truncated/wrong definition
        elif error_type == "wrong_definition":
            if entry.get("karen") == corrected.get("karen"):
                # We have the verified correct entry — apply the fix directly
                entry["definitions"] = corrected.get("definitions")
                entry["_auto_corrected"] = True
                changed = True

        # CONDITIONAL: formatting_error — find all entries missing 'co.' compounds
        elif error_type == "formatting_error":
            if entry.get("definitions"):
                for i, defn in enumerate(entry["definitions"]):
                    # CONDITIONAL: if a definition ends mid-sentence without period, flag it
                    if isinstance(defn, str) and len(defn) > 5 and not defn.strip().endswith("."):
                        entry["_needs_review"] = True
                        entry["_review_reason"] = "Definition may be truncated — check for co. compounds"
                        changed = True
                        break

        if changed:
            fix_count += 1

    # FILE OPERATION: save the patched dictionary back to disk
    with open(FULL_DICT_PATH, "w", encoding="utf-8") as f:
        json.dump(full_dict, f, ensure_ascii=False, indent=2)

    print(f"🔍 Auto-propagation complete: {fix_count} entries flagged or corrected in karendictfull.json")


# FUNCTION DEFINITION: builds a Gemini prompt injected with your last 10 corrections as examples
# This makes Gemini smarter on every new crop without any retraining
# RETURN STATEMENT: a string to paste as the system prompt before each new Gemini crop
def build_smart_prompt():
    examples = ""
    if os.path.exists(GROUNDTRUTH_PATH):
        with open(GROUNDTRUTH_PATH, encoding="utf-8") as f:
            data = json.load(f)
        recent = data["corrections"][-10:]
        # LOOP: build example text from your most recent corrections
        for ex in recent:
            if ex["correction_type"] == "wrong_definition":
                examples += (
                    f"\nEXAMPLE: Gemini said: {json.dumps(ex['gemini_predicted'], ensure_ascii=False)}\n"
                    f"CORRECT answer: {json.dumps(ex['human_verified'], ensure_ascii=False)}\n"
                    f"REASON: {ex['note']}\n"
                )

    return (
        "You are reading a Sgaw Karen–English dictionary (1896). "
        "Extract every entry as JSON: {\"karen\": \"headword\", \"definitions\": [...]}. "
        "Include ALL sub-entries, compound words (co.), alternate spellings. "
        "Do NOT truncate definitions. Return ONLY the JSON array.\n"
        + (f"\nLearn from these past corrections before you extract:\n{examples}" if examples else "")
    )


# FUNCTION DEFINITION: reviews and prints all flagged entries needing human review
def show_flagged():
    if not os.path.exists(FULL_DICT_PATH):
        print("karendictfull.json not found.")
        return
    with open(FULL_DICT_PATH, encoding="utf-8") as f:
        full_dict = json.load(f)
    flagged = [e for e in full_dict if e.get("_needs_review")]
    print(f"\n📋 {len(flagged)} entries flagged for review:")
    for entry in flagged[:20]:
        print(f"  Karen: {entry.get('karen')} | Reason: {entry.get('_review_reason')}")


# --- MAIN: example usage you can uncomment and run ---
if __name__ == "__main__":
    # EXAMPLE: Run this after you catch Gemini making a mistake on a crop
    # log_correction(
    #     image_source="page_0011_top.jpg",
    #     gemini_output={"karen": "မ", "definitions": ["elephant"]},
    #     human_correction={"karen": "မ", "definitions": ["co. elephant, see ည...", "pacify the crying child"]},
    #     note="Gemini truncated the full compound definition — dropped 'co.' chain"
    # )

    # EXAMPLE: Print all entries that need your review
    show_flagged()

    # EXAMPLE: Generate a smart prompt to paste into Gemini for next crop
    print("\n--- PASTE THIS INTO GEMINI FOR YOUR NEXT CROP ---")
    print(build_smart_prompt())