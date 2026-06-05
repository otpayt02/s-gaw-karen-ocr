# Local Translator Suite Provenance

Source repo: `otpayt02/S-gaw-Karen-Dictionary-Builder`

Audited commit: `a8fb7999e7e5532b5cbe77b97b90d5686b62a094`

This folder preserves the most useful imported dictionary-builder work as a secondary reference app. It is intentionally separate from the main OCR review workbench at the repository root.

## Why This Was Kept

- It is a runnable Flask app rather than a static note.
- It supports local JSON/cache lookup, website scraping, reverse Sgaw Karen parsing, batch text processing, and an attempt/history UI.
- It adds a credible "beyond OCR" proof path: OCR output can be audited against dictionary sources and phrase-level parsing logic.
- `data/sgaw_mini_lm_seed_plan.json` is useful portfolio evidence because it shows a concrete seed plan for expanding Sgaw Karen language data.

## What Was Not Imported

- `data/lookup_attempts.json` and `data/lookup_attempts.json.bad-*` because they are generated run logs.
- `data/karen_reverse_cache.json` because it is generated cache data and may contain stale private run artifacts.
- `samples/song_library.json` and large copied website samples because they are not core implementation code.
- Root run outputs such as `translations_updated.txt`; `samples/translations_website.txt` is a tiny clean input fixture for demos.

## Run

```powershell
cd pipeline\dictionary_processing\local_translator_suite
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5057`.
