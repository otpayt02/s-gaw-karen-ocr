import json
import os

BASE_DIR  = r"C:\Users\olive\Projects\karen_lang_trans\Fly_Solo_supervisor"
DICT_FILE = os.path.join(BASE_DIR, "karen_dict_full.json")
BACKUP    = os.path.join(BASE_DIR, "karen_dict_full.BACKUP_before_cleanup.json")

# ── STEP 1: Load ──────────────────────────────────────────────────────────────
with open(DICT_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total entries BEFORE cleanup: {len(data)}")

# ── STEP 2: Backup first — NEVER skip this ────────────────────────────────────
with open(BACKUP, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"✅ Backup saved to: {BACKUP}")

# ── STEP 3: Keep only entries with page <= 518 ────────────────────────────────
# Entries with no page number (None / 0 / missing) are KEPT — don't delete unknowns
kept    = [e for e in data if (e.get('page') or 0) <= 518]
deleted = [e for e in data if (e.get('page') or 0) >= 519]

print(f"Entries KEPT   (page 1–518):  {len(kept)}")
print(f"Entries DELETED (page 519+): {len(deleted)}")

# ── STEP 4: Preview first 5 deleted so you can confirm they look right ─────────
print("\n--- First 5 entries being DELETED (preview) ---")
for e in deleted[:5]:
    print(f"  Page {e.get('page')} | {e.get('karen','?')} | {str(e.get('definitions',''))[:60]}")

# ── STEP 5: Confirm before writing ────────────────────────────────────────────
confirm = input("\nType YES to permanently delete page 519+ entries and save: ")
if confirm.strip().upper() != "YES":
    print("❌ Aborted. Nothing was changed.")
    exit()

# ── STEP 6: Atomic save (same crash-proof method as app.py) ───────────────────
tmp = DICT_FILE + ".tmp"
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(kept, f, ensure_ascii=False, indent=2)
os.replace(tmp, DICT_FILE)

print(f"\n✅ Done. Dictionary now has {len(kept)} entries (pages 1–518 only).")
print(f"   Your backup is safe at: {BACKUP}")