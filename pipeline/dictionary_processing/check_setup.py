# save as check_setup.py in karen_lang_trans folder
import os, json, fitz

# VARIABLE DECLARATION — all the paths bootstrap_ocr.py depends on
PROJECT_ROOT  = os.path.dirname(os.path.abspath(__file__))
PDF_PATH      = os.path.join(PROJECT_ROOT, "karen_dict.pdf")
OUTPUT_FILE   = os.path.join(PROJECT_ROOT, "karen_dict_full.json")
PROGRESS_FILE = os.path.join(PROJECT_ROOT, "progress.json")
MEMORY_PATH   = os.path.join(PROJECT_ROOT, "memory.json")

print("=" * 50)

# CONDITIONAL — checks karen_dict.pdf exists and is readable
if os.path.exists(PDF_PATH):
    doc = fitz.open(PDF_PATH)
    print(f"✅ karen_dict.pdf     — FOUND ({len(doc)} pages)")
    doc.close()
else:
    print(f"❌ karen_dict.pdf     — NOT FOUND at {PDF_PATH}")

# CONDITIONAL — checks memory.json is valid JSON with lessons
if os.path.exists(MEMORY_PATH):
    with open(MEMORY_PATH, encoding="utf-8") as f:
        mem = json.load(f)
    lessons = mem.get("lessons", [])
    print(f"✅ memory.json        — FOUND ({len(lessons)} lessons loaded)")
    print(f"   Last lesson: {lessons[-1]['lesson'][:80]}...")
else:
    print(f"❌ memory.json        — NOT FOUND")

# CONDITIONAL — checks progress.json has only strings, no corrupt integers
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, encoding="utf-8") as f:
        prog = json.load(f)
    bad = [x for x in prog if not isinstance(x, str)]
    good = [x for x in prog if isinstance(x, str)]
    print(f"✅ progress.json      — FOUND ({len(good)} pages done)")
    if bad:
        print(f"⚠️  WARNING: {len(bad)} corrupt integer entries still present — delete progress.json and restart")
    else:
        print(f"   No corrupt entries detected ✓")
else:
    print(f"ℹ️  progress.json      — NOT FOUND (fresh run, that's fine)")

# CONDITIONAL — checks existing dictionary entry count
if os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    empty = [e for e in data if not e.get("definitions")]
    print(f"✅ karen_dict_full.json — FOUND ({len(data)} entries, {len(empty)} missing definitions)")
else:
    print(f"ℹ️  karen_dict_full.json — NOT FOUND (will be created on first run)")

# CONDITIONAL — checks API key is set
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    print(f"✅ GEMINI_API_KEY     — SET (ends in ...{api_key[-6:]})")
else:
    print(f"❌ GEMINI_API_KEY     — NOT SET")
    print(f"   Fix: set GEMINI_API_KEY=your_key_here  (in terminal before running)")

print("=" * 50)