import json
import os

DICT_FILE = "karen_dict_full.json"
BANNED_CHAR = "á€"

if os.path.exists(DICT_FILE):
    with open(DICT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    found_count = 0
    print(f"ðŸ•µï¸ Scanning for illegal character '{BANNED_CHAR}'...\n")

    for index, entry in enumerate(data):
        karen_word = entry.get('karen', '')
        if BANNED_CHAR in karen_word:
            print(f"âš ï¸ Found '{BANNED_CHAR}' in word: {karen_word} (Page {entry.get('page')}) -> Record Index in Hub: {index}")
            found_count += 1

    print(f"\nðŸ” Found {found_count} illegal characters total.")
else:
    print("Dictionary file not found.")
