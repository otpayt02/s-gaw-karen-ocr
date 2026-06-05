# S'gaw Karen Local Translator Suite

Local web interface for building S'gaw Karen translations for the Karen music website. The pipeline does not use Gemini, OpenAI, or any LLM/API fallback. It uses local JSON/cache data plus website scraping.

## Features

- Manual search editor with Auto, English to Karen, and Karen to English routing.
- Unicode-aware detection for Karen text in either side of `=` and for bare lines starting with Karen Unicode.
- Required scrape order for web lookups: Glosbe first, then KarenDictionary.org; Drum Publications is checked when the second source gives no usable result.
- English inputs first run a no-key internet context search over DuckDuckGo's HTML page, then use extracted keywords to help compose a short Karen definition when dictionaries do not have the phrase.
- English lookups now force a non-empty Karen fallback definition when dictionaries miss, using known component terms or a generic website-interface definition.
- Lookup details expose per-word English reasoning, Karen connector choices, and Karen syllable combinations already tried.
- Grammar particle rules define roles, placement, and English trigger words for connectors such as `တၢ်`, `အ`, `လၢ`, `လၢအ`, `ဒီး`, `ဆူ`, `ဖဲ`, `ဒ်`, `ခီဖျိ`, `ဘၣ်ဃး`, negation, aspect, plural, and demonstratives.
- `data/sgaw_mini_lm_seed_plan.json` lays out the first 2,000 seed concepts to collect for a S'gaw Karen mini language model.
- One-second delay before each website scrape by default.
- Connector-aware Karen reverse parser with whole-word, connector-boundary, segment, and contiguous-combination attempts.
- Persistent attempt metadata in `data/lookup_attempts.json`.
- Batch processor that fills empty Karen values and appends `# --- REVERSE TRANSLATION ANALYSIS ---` notes.
- Writes processed batch output to `translations_updated.txt`.
- Live `translations_website.txt` runner with 0.5-second UI refresh, per-line source/target/status/dictionary/guess display, and continuous output writes.

## Run

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5057`.

## Data

- `samples/` contains copied seed files from the Karen music website workspace.
- `data/karen_reverse_cache.json` is the local lookup cache.
- `data/lookup_attempts.json` stores every lookup/cache/scrape/parser attempt with metadata.

## Scraping Notes

KarenDictionary.org is a client-rendered site. This app only scrapes website HTML and does not call the site's Supabase JSON/API endpoints. If the HTML scrape yields no usable result, that failure is logged and Drum Publications is checked as a secondary fallback.
