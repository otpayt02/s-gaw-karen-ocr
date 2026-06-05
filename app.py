# -*- coding: utf-8 -*-
import os
import re
import json
import time
import html
import threading
import traceback
from datetime import datetime
from pathlib import Path

import fitz
from flask import Flask, jsonify, request, render_template_string, send_file
from google import genai
from google.genai import types

app = Flask(__name__)

# =============================================================================
# ERROR HANDLERS
# =============================================================================
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback as _tb
    return jsonify({"ok": False, "error": str(e), "trace": _tb.format_exc()[-1200:]}), 500


@app.errorhandler(404)
def handle_404(e):
    return jsonify({"ok": False, "error": "Route not found: " + str(e)}), 404


# =============================================================================
# GEMINI
# =============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "app_data"
PDF_DIR = DATA_DIR / "pdfs"
IMG_DIR = DATA_DIR / "images"
RENDER_DIR = DATA_DIR / "renders"

DICT_FILE = BASE_DIR / "karen_dict_full.json"
MEMORY_FILE = BASE_DIR / "memory.json"
CONFIG_FILE = BASE_DIR / "batch_config.json"
PROCESSED_FILE = BASE_DIR / "processed.json"
CORRECTIONS_FILE = BASE_DIR / "corrections_log.json"

for d in [DATA_DIR, PDF_DIR, IMG_DIR, RENDER_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "pdf_pages_per_batch": 10,
    "images_per_batch": 20,
    "delay_seconds": 1.5,
    "page_offset": 0,
    "render_dpi": 200,
    "skip_processed": True,
    "auto_import_bootstrap": True,
}

BOOTSTRAP_PATTERNS = ["bootstrap*.json", "bootstrap_ocr*.json"]

KAREN_RULES = """
You are extracting entries from a printed Sgaw Karen-English dictionary.

Critical preservation rules:
- Keep every original definition string intact.
- Do NOT remove examples, compounds, cross-references, part-of-speech clues,
  cognates, grammar notes, or secondary lexical items from the original definition.
- If you detect another possible headword inside a definition, LEAVE IT inside the
  original definition text and only copy it into analysis.headword_terms.
- You may also return a separate possible entry if it is clearly lexical, but never
  cut that text out of the original entry.
- If one headword has numbered senses 1. 2. 3. keep them all in the SAME entry.
- entry_type must be one of: headword, compound, example.
- analysis.examples are copied from the original definition, not removed from it.
- analysis.headword_terms are copied from the original definition, not removed from it.
- analysis.related_items are copied from the original definition, not removed from it.
- analysis.segments.text must be substrings copied exactly from the original definition.
- analysis.sense_labels may infer part of speech for numbered senses.

Return ONLY valid JSON.
"""

FONT_PATH = Path(os.environ.get("PADAUK_FONT", str(BASE_DIR / "padauk_reg.ttf")))

# =============================================================================
# STATE
# =============================================================================
_lock = threading.Lock()
_state = {
    "running": False,
    "cancel": False,
    "mode": "",
    "file": "",
    "page": "",
    "done": 0,
    "total": 0,
    "entries_added": 0,
    "started": "",
    "finished": "",
    "error": "",
    "log": [],
}


# =============================================================================
# HELPERS
# =============================================================================
def _now():
    return datetime.now().isoformat(timespec="seconds")


def parse_ts(s):
    if not s:
        return datetime.min
    try:
        return datetime.fromisoformat(str(s)[:19])
    except Exception:
        return datetime.min


def _snap():
    with _lock:
        return json.loads(json.dumps(_state))


def _reset(mode, total):
    with _lock:
        _state.update(
            {
                "running": True,
                "cancel": False,
                "mode": mode,
                "file": "",
                "page": "",
                "done": 0,
                "total": total,
                "entries_added": 0,
                "started": _now(),
                "finished": "",
                "error": "",
                "log": [],
            }
        )


def _finish(error=""):
    with _lock:
        _state.update({"running": False, "finished": _now(), "error": error})


def _log(msg):
    with _lock:
        _state["log"].append(msg)
        _state["log"] = _state["log"][-500:]


def _bump(done, added):
    with _lock:
        _state["done"] = done
        _state["entries_added"] = added


def jload(path, default):
    p = Path(path)
    if not p.exists():
        return default() if callable(default) else default
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default() if callable(default) else default


def jsave(path, data):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_dict():
    d = jload(DICT_FILE, list)
    return d if isinstance(d, list) else []


def save_dict(d):
    jsave(DICT_FILE, d)


def load_cfg():
    c = jload(CONFIG_FILE, dict)
    out = dict(DEFAULT_CONFIG)
    if isinstance(c, dict):
        out.update(c)
    return out


def save_cfg(c):
    out = dict(DEFAULT_CONFIG)
    out.update(c or {})
    jsave(CONFIG_FILE, out)
    return out


def load_processed():
    d = jload(PROCESSED_FILE, dict)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("images", [])
    d.setdefault("pdf_pages", [])
    d.setdefault("bootstrap_files", [])
    return d


def save_processed(d):
    jsave(PROCESSED_FILE, d)


def load_corrections():
    d = jload(CORRECTIONS_FILE, list)
    return d if isinstance(d, list) else []


def save_corrections(d):
    jsave(CORRECTIONS_FILE, d)


def record_correction(kind, payload=None):
    data = load_corrections()
    row = {"timestamp": _now(), "type": kind}
    if isinstance(payload, dict):
        row.update(payload)
    data.append(row)
    save_corrections(data)


def safe_name(name):
    name = os.path.basename(name)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name.strip("._") or f"f_{int(time.time())}"


def _mime(path):
    e = Path(path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(e, "image/png")


def is_img(p):
    return Path(p).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def empty_analysis():
    return {
        "examples": [],
        "headword_terms": [],
        "related_items": [],
        "segments": [],
        "sense_labels": [],
    }


def norm_analysis(a):
    out = empty_analysis()
    if not isinstance(a, dict):
        return out
    for k in out:
        out[k] = a.get(k, []) if isinstance(a.get(k, []), list) else []
    return out


def dedupe_values(items):
    out, seen = [], set()
    for item in items or []:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def merge_analysis(a, b):
    aa = norm_analysis(a)
    bb = norm_analysis(b)
    return {k: dedupe_values(aa.get(k, []) + bb.get(k, [])) for k in empty_analysis()}


def norm(entry, src="", page=None):
    if not isinstance(entry, dict):
        entry = {"karen": str(entry), "definitions": []}
    k = str(entry.get("karen", "")).strip()
    ds = entry.get("definitions", [])
    if isinstance(ds, str):
        ds = [ds]
    ds = [str(x) for x in ds if str(x).strip()]
    et = str(entry.get("entry_type", "headword")).strip().lower()
    if et not in {"headword", "compound", "example"}:
        et = "headword"
    ts = _now()
    return {
        "karen": k,
        "definitions": ds,
        "page": entry.get("page", page),
        "flag": bool(entry.get("flag", False)),
        "source": entry.get("source", src),
        "entry_type": et,
        "promoted": bool(entry.get("promoted", False)),
        "analysis": norm_analysis(entry.get("analysis", {})),
        "created_at": entry.get("created_at", ts),
        "updated_at": entry.get("updated_at", ts),
    }


def add_entries(new_entries):
    d = load_dict()
    d.extend(new_entries)
    save_dict(d)
    return len(d)


def parse_json_array(raw):
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw.strip())
    try:
        p = json.loads(raw)
        if isinstance(p, list):
            return p
        if isinstance(p, dict) and isinstance(p.get("entries"), list):
            return p["entries"]
    except Exception:
        pass
    s, e = raw.find("["), raw.rfind("]")
    if s != -1 and e > s:
        p = json.loads(raw[s : e + 1])
        if isinstance(p, list):
            return p
    raise ValueError(f"No JSON array in model output: {raw[:400]}")


def build_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
    return genai.Client(api_key=GEMINI_API_KEY)


def normalize_segment_kind(kind):
    kind = str(kind or "").strip().lower()
    return {
        "example sentence": "example",
        "examples": "example",
        "xref": "cross_reference",
        "cross reference": "cross_reference",
        "cross-reference": "cross_reference",
        "cf": "cross_reference",
        "cognate term": "cognate",
        "analogous term": "analogous",
        "grammar principle": "grammar",
        "grammar note": "grammar",
        "headword term": "headword",
    }.get(kind, kind or "other")


def inject_pos_labels(text, sense_labels):
    text = str(text or "")
    mapping = {
        str(x.get("number", "")).strip(): str(x.get("label", "")).strip()
        for x in (sense_labels or [])
        if isinstance(x, dict)
    }
    if not mapping:
        return text

    def repl(m):
        prefix, num, ws = m.groups()
        label = mapping.get(num)
        return f"{prefix}{num}. ({label}){ws}" if label else m.group(0)

    return re.sub(r"(^|[\s(;])(\d+)\.(\s*)", repl, text)


def decorate_definition(text, segments):
    rendered = html.escape(str(text or ""))
    clean = []
    for seg in (segments or []):
        if not isinstance(seg, dict):
            continue
        st = str(seg.get("text", "")).strip()
        sk = normalize_segment_kind(seg.get("kind", "other"))
        if st:
            clean.append({"text": st, "kind": sk})
    clean.sort(key=lambda x: len(x["text"]), reverse=True)
    for seg in clean:
        raw = html.escape(seg["text"])
        cls = "seg seg-" + seg["kind"]
        wrapped = '<span class="' + cls + '">' + raw + "</span>"
        rendered = rendered.replace(raw, wrapped, 1)
    return rendered.replace("\n", "<br>")


def dedupe_items(items):
    out, seen = [], set()
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, dict) else str(item)
        if key not in seen:
            seen.add(key)
            out.append(item if isinstance(item, dict) else {"text": str(item)})
    return out


def build_headword_lookup(entries):
    prioritized = sorted(
        entries,
        key=lambda x: (
            0 if x.get("promoted") or x.get("entry_type") == "headword" else 1,
            x.get("index", 0),
        ),
    )
    out = {}
    for e in prioritized:
        k = str(e.get("karen", "")).strip()
        idx = e.get("index")
        if k and idx is not None and k not in out:
            out[k] = idx
    return out


def link_headword_terms(rendered_html, terms, lookup):
    out = str(rendered_html or "")
    for item in dedupe_items(terms or []):
        txt = str(item.get("text", "")).strip()
        target = lookup.get(txt)
        if txt and target is not None:
            esc = html.escape(txt)
            link = f'<a href="#entry-{target}" class="hw-link karen" data-idx="{target}">{esc}</a>'
            out = out.replace(esc, link, 1)
    return out


def build_view_entry(entry, lookup):
    e = dict(entry)
    analysis = norm_analysis(e.get("analysis", {}))
    e["analysis"] = analysis
    display_defs, linked_defs = [], []
    for d in e.get("definitions", []):
        labeled = inject_pos_labels(d, analysis.get("sense_labels", []))
        display_defs.append(labeled)
        rendered = decorate_definition(labeled, analysis.get("segments", []))
        rendered = link_headword_terms(rendered, analysis.get("headword_terms", []), lookup)
        linked_defs.append(rendered)
    e["display_definitions"] = display_defs
    e["linked_definitions"] = linked_defs
    e["tab_examples"] = dedupe_items(analysis.get("examples", []))
    e["tab_headwords"] = dedupe_items(analysis.get("headword_terms", []))
    e["tab_related"] = dedupe_items(analysis.get("related_items", []))
    return e


def search_blob(entry):
    a = norm_analysis(entry.get("analysis", {}))
    return " ".join(
        [
            str(entry.get("karen", "")),
            " ".join(entry.get("definitions", [])),
            str(entry.get("source", "")),
            json.dumps(a, ensure_ascii=False),
        ]
    ).lower()


def maybe_auto_import_bootstrap(force=False):
    cfg = load_cfg()
    if not force and not cfg.get("auto_import_bootstrap", True):
        return 0
    proc = load_processed()
    added = 0
    paths = []
    for pat in BOOTSTRAP_PATTERNS:
        paths.extend(BASE_DIR.glob(pat))
    for p in sorted(set(paths)):
        key = str(p.resolve())
        if key in proc["bootstrap_files"]:
            continue
        data = jload(p, list)
        if not isinstance(data, list) or not data:
            proc["bootstrap_files"].append(key)
            continue
        batch = [
            norm(x, src=f"bootstrap:{p.name}", page=(x.get("page") if isinstance(x, dict) else None))
            for x in data
        ]
        add_entries(batch)
        added += len(batch)
        proc["bootstrap_files"].append(key)
        record_correction("import_bootstrap", {"file": p.name, "added": len(batch)})
    save_processed(proc)
    return added


# =============================================================================
# FONT ROUTE
# =============================================================================
@app.route("/fonts/padauk_reg.ttf")
def r_font():
    candidates = [
        FONT_PATH,
        BASE_DIR / "padauk_reg.ttf",
        Path("/root/karenlangtrans/padauk_reg.ttf"),
        BASE_DIR / "padauk-regular.ttf",
        Path("/root/karenlangtrans/padauk-regular.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return send_file(str(p), mimetype="font/ttf")
    return "padauk_reg.ttf not found", 404


# =============================================================================
# GEMINI
# =============================================================================
def gemini_extract(image_bytes, mime_type, source="", page=None):
    client = build_client()
    prompt = (
        f"{KAREN_RULES}\n\n"
        "Return ONLY a valid JSON array. Each item can look like:\n"
        "{\n"
        '  "karen": "Karen text",\n'
        '  "definitions": ["FULL ORIGINAL DEFINITION TEXT VERBATIM"],\n'
        '  "entry_type": "headword",\n'
        f'  "page": {page if page is not None else 0},\n'
        '  "flag": false,\n'
        '  "analysis": {\n'
        '    "examples": [{"text":"example from def","note":""}],\n'
        '    "headword_terms": [{"text":"term from def","kind":"headword"}],\n'
        '    "related_items": [{"text":"compound/cf/cognate from def","kind":"compound"}],\n'
        '    "segments": [{"text":"substring from def","kind":"example"}],\n'
        '    "sense_labels": [{"number":"1","label":"verb"}]\n'
        "  }\n"
        "}\n"
        "Again: never cut extracted pieces out of the original definition text."
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            max_output_tokens=8192,
        ),
    )
    raw = getattr(response, "text", "") or ""
    entries = parse_json_array(raw)
    return [norm(x, src=source, page=page) for x in entries]


def gemini_reanalyze_entry(entry):
    client = build_client()
    prompt = (
        "Re-analyze this Sgaw Karen dictionary entry for UI display.\n"
        "Do NOT change or rewrite definitions.\n"
        "Keep the original definitions intact.\n"
        "Only return entry_type and analysis.\n"
        "Possible extra lexical items found inside a definition must stay in the original definition text.\n"
        "Copy them into analysis.headword_terms; do not cut them out.\n\n"
        "Input:\n"
        + json.dumps(
            {
                "karen": entry.get("karen", ""),
                "definitions": entry.get("definitions", []),
                "entry_type": entry.get("entry_type", "headword"),
            },
            ensure_ascii=False,
        )
        + '\n\nReturn exactly:\n{"entry_type":"headword","analysis":{"examples":[],"headword_terms":[],"related_items":[],"segments":[],"sense_labels":[]}}'
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            max_output_tokens=4096,
        ),
    )
    obj = json.loads(getattr(response, "text", "") or "{}")
    et = str(obj.get("entry_type", entry.get("entry_type", "headword"))).strip().lower()
    if et not in {"headword", "compound", "example"}:
        et = "headword"
    return {"entry_type": et, "analysis": norm_analysis(obj.get("analysis", {}))}


def extract_file(path, source="", page=None):
    with open(path, "rb") as f:
        b = f.read()
    return gemini_extract(b, _mime(path), source=source, page=page)


# =============================================================================
# PDF RENDER
# =============================================================================
def render_pdf(pdf_path, start, end, dpi=200):
    doc = fitz.open(pdf_path)
    out = []
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        stem = safe_name(Path(pdf_path).stem)
        for pn in range(max(1, start), min(len(doc), end) + 1):
            px = doc.load_page(pn - 1).get_pixmap(matrix=mat, alpha=False)
            dest = RENDER_DIR / f"{stem}_p{pn:04d}.png"
            px.save(str(dest))
            out.append((pn, dest))
    finally:
        doc.close()
    return out


# =============================================================================
# WORKERS
# =============================================================================
def worker_images(paths, cfg, label):
    proc = load_processed()
    skip = cfg.get("skip_processed", True)
    delay = float(cfg.get("delay_seconds", 1.5))
    off = int(cfg.get("page_offset", 0))
    added = 0
    for i, p in enumerate(paths, 1):
        with _lock:
            if _state["cancel"]:
                _log("❌ Cancelled")
                _finish()
                return
            _state["file"] = Path(p).name
            _state["page"] = ""
        key = str(Path(p).resolve())
        if skip and key in proc["images"]:
            _log(f"⏭ skip {Path(p).name}")
            _bump(i, added)
            continue
        m = re.search(r"(\d+)", Path(p).name)
        pg = int(m.group(1)) + off if m else None
        try:
            entries = extract_file(p, source=f"{label}:{Path(p).name}", page=pg)
            if entries:
                add_entries(entries)
                added += len(entries)
                proc["images"].append(key)
                save_processed(proc)
                _log(f"✅ [{i}/{len(paths)}] {Path(p).name} → {len(entries)} entries")
            else:
                _log(f"⚠ [{i}/{len(paths)}] {Path(p).name} → 0 entries")
        except Exception as e:
            _log(f"⚠ [{i}/{len(paths)}] {Path(p).name} ERROR: {e}")
            _log(traceback.format_exc()[-1000:])
        _bump(i, added)
        time.sleep(delay)
    _log(f"🎉 Done — {added} entries from {len(paths)} images")
    _finish()


def worker_pdf(pdf_path, start, end, cfg):
    delay = float(cfg.get("delay_seconds", 1.5))
    off = int(cfg.get("page_offset", 0))
    dpi = int(cfg.get("render_dpi", 200))
    proc = load_processed()
    skip = cfg.get("skip_processed", True)
    added = 0
    try:
        pages = render_pdf(pdf_path, start, end, dpi=dpi)
    except Exception as e:
        _log(f"⚠ PDF render failed: {e}")
        _finish(str(e))
        return
    for i, (pn, img) in enumerate(pages, 1):
        with _lock:
            if _state["cancel"]:
                _log("❌ Cancelled")
                _finish()
                return
            _state["file"] = Path(pdf_path).name
            _state["page"] = str(pn)
        key = f"{Path(pdf_path).resolve()}::p::{pn}"
        if skip and key in proc["pdf_pages"]:
            _log(f"⏭ skip page {pn}")
            _bump(i, added)
            continue
        try:
            entries = extract_file(img, source=f"pdf:{Path(pdf_path).name}:p{pn}", page=pn + off)
            if entries:
                add_entries(entries)
                added += len(entries)
                proc["pdf_pages"].append(key)
                save_processed(proc)
                _log(f"✅ [{i}/{len(pages)}] page {pn} → {len(entries)} entries")
            else:
                _log(f"⚠ [{i}/{len(pages)}] page {pn} → 0 entries")
        except Exception as e:
            _log(f"⚠ [{i}/{len(pages)}] page {pn} ERROR: {e}")
            _log(traceback.format_exc()[-1000:])
        _bump(i, added)
        time.sleep(delay)
    _log(f"🎉 Done — {added} entries from {len(pages)} pages")
    _finish()


def launch(mode, fn, *args):
    if _snap()["running"]:
        raise RuntimeError("Batch already running — click force reset if stuck")
    total = len(args[0]) if mode == "images" else (args[2] - args[1] + 1 if mode == "pdf" else 1)
    _reset(mode, total)
    threading.Thread(target=fn, args=args, daemon=True).start()


# =============================================================================
# HTML
# =============================================================================
HTML_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Karen Dictionary Workbench</title>
<style>
@font-face{
  font-family:'PadaukKaren';
  src:url('/fonts/padauk_reg.ttf') format('truetype');
  font-display:swap;
}
:root{
  --bg:#0b1020;
  --panel:#121a2b;
  --panel2:#0f1726;
  --line:#273246;
  --text:#e7ecf6;
  --muted:#9ca8bc;
  --blue:#3b82f6;
  --green:#10b981;
  --yellow:#f59e0b;
  --red:#ef4444;
  --purple:#8b5cf6;
}
*{box-sizing:border-box}
html,body,input,textarea,button,select,option,[contenteditable="true"],.karen{
  font-family:'PadaukKaren','Padauk','Myanmar Text',sans-serif !important;
}
body{
  margin:0;
  background:linear-gradient(180deg,#0b1020 0%,#0a0f1c 100%);
  color:var(--text);
}
a{color:#93c5fd;text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1500px;margin:0 auto;padding:18px}
.topbar{
  display:flex;justify-content:space-between;align-items:center;gap:12px;
  margin-bottom:16px;flex-wrap:wrap
}
.title{font-size:28px;font-weight:800;letter-spacing:.2px}
.badges{display:flex;gap:8px;flex-wrap:wrap}
.badge{
  background:#122033;border:1px solid var(--line);border-radius:999px;
  padding:6px 10px;font-size:12px;color:#b8c6da
}
.layout{
  display:grid;grid-template-columns:340px 1fr;gap:16px
}
@media (max-width:1080px){.layout{grid-template-columns:1fr}}
.panel{
  background:rgba(18,26,43,.92);
  border:1px solid var(--line);
  border-radius:18px;
  padding:16px;
  box-shadow:0 18px 60px rgba(0,0,0,.25)
}
.panel h3{margin:0 0 12px 0;font-size:16px}
label{display:block;font-size:12px;color:var(--muted);margin:10px 0 6px}
input, textarea, button, select{
  width:100%;
  border-radius:12px;
  border:1px solid var(--line);
  background:#0c1322;
  color:var(--text);
  padding:10px 12px;
  font-size:14px;
}
textarea{min-height:100px;resize:vertical}
button{cursor:pointer;font-weight:700}
button:hover{filter:brightness(1.06)}
.btn-row{display:flex;gap:8px;flex-wrap:wrap}
.btn-row > *{flex:1}
.btn-blue{background:#14315f}
.btn-green{background:#0f4f41}
.btn-yellow{background:#5f450d}
.btn-red{background:#5a1b25}
.btn-gray{background:#1a2436}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.meta{
  display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;
  margin-bottom:12px
}
.search-row{
  display:grid;grid-template-columns:1fr 120px 120px;gap:10px
}
@media (max-width:860px){.search-row{grid-template-columns:1fr}}
.entries{display:grid;gap:12px}
.card{
  background:rgba(15,23,38,.96);
  border:1px solid var(--line);
  border-radius:18px;
  padding:14px;
}
.card.flagged{border-color:#7f1d1d;box-shadow:0 0 0 1px rgba(239,68,68,.22) inset}
.card-head{
  display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap
}
.id-box{
  display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap
}
.id-pill{
  background:#15243a;border:1px solid #2f4767;border-radius:999px;
  padding:4px 10px;font-weight:800;color:#d8e6ff
}
.tag{
  border-radius:999px;padding:3px 9px;font-size:11px;border:1px solid var(--line);
  color:#cbd5e1;background:#101a2c
}
.tag.flag{background:#3d1015;border-color:#7f1d1d}
.tag.headword{background:#10271f}
.tag.compound{background:#35270b}
.tag.example{background:#261748}
.karen-head{
  font-size:28px;line-height:1.2;color:#8ee0b8;word-break:break-word
}
.source{
  color:var(--muted);font-size:12px;margin-top:4px
}
.defs{margin-top:12px;display:grid;gap:10px}
.def{
  background:#0c1322;border:1px solid #22304a;border-radius:14px;padding:12px;line-height:1.6
}
.seg{padding:0 2px;border-radius:4px}
.seg-example{background:rgba(59,130,246,.15)}
.seg-cross_reference{background:rgba(168,85,247,.16)}
.seg-cognate{background:rgba(16,185,129,.16)}
.seg-analogous{background:rgba(244,114,182,.14)}
.seg-grammar{background:rgba(250,204,21,.16)}
.seg-headword{background:rgba(34,197,94,.16)}
.card-actions{
  display:flex;gap:8px;flex-wrap:wrap;margin-top:12px
}
.card-actions button{width:auto;padding:9px 12px}
.small{
  font-size:12px;color:var(--muted)
}
.info-grid{
  display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:12px
}
@media (max-width:900px){.info-grid{grid-template-columns:1fr}}
.subpanel{
  background:#0b1220;border:1px solid #22304a;border-radius:14px;padding:10px
}
.subpanel h4{margin:0 0 8px 0;font-size:13px;color:#cbd5e1}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{
  display:inline-flex;align-items:center;gap:6px;
  background:#101c31;border:1px solid #253652;border-radius:999px;
  padding:6px 10px;font-size:13px
}
.karen-link{color:#93c5fd}
.toast{
  position:fixed;right:18px;top:18px;z-index:10020;
  background:#10253d;border:1px solid #214870;border-radius:14px;
  padding:12px 14px;display:none;max-width:420px
}
.statusbox, .logbox{
  background:#09101d;border:1px solid #22304a;border-radius:14px;padding:12px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;white-space:pre-wrap
}
.logbox{min-height:180px;max-height:280px;overflow:auto}
.modal-backdrop{
  position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;
  align-items:center;justify-content:center;padding:18px;z-index:10010
}
.modal{
  width:min(980px,100%);
  background:#0f1726;border:1px solid var(--line);border-radius:20px;padding:18px
}
.modal h3{margin-top:0}
.merge-results{display:grid;gap:10px;max-height:320px;overflow:auto;margin-top:12px}
.merge-item{
  background:#0b1322;border:1px solid #24314a;border-radius:14px;padding:12px
}
.merge-item .pick{width:auto;margin-top:10px}
.footer-note{margin-top:8px;color:var(--muted);font-size:12px}
#kb-launcher{
  position:fixed;right:18px;bottom:18px;z-index:10030;border:0;border-radius:999px;
  padding:12px 16px;background:#2563eb;color:#fff;cursor:pointer;
  box-shadow:0 12px 30px rgba(0,0,0,.35);width:auto
}
#kb-backdrop[hidden]{display:none !important}
#kb-backdrop{
  position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:10040;
  display:grid;place-items:end center;padding:18px;
}
#kb-modal{
  width:min(920px,100%);background:#101623;color:#fff;border-radius:18px;
  border:1px solid rgba(255,255,255,.12);box-shadow:0 24px 60px rgba(0,0,0,.45);padding:16px;
}
#kb-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
#kb-grid{display:grid;grid-template-columns:repeat(10,1fr);gap:8px}
.kb-key{
  border:0;border-radius:12px;padding:12px 8px;background:#1f2937;color:#fff;font-size:24px;cursor:pointer;width:100%
}
.kb-wide{grid-column:span 2;font-size:14px}
#kb-target-hint{opacity:.78;font-size:13px;margin-bottom:10px}
</style>
</head>
<body>
<div class="toast" id="toast"></div>

<div class="wrap">
  <div class="topbar">
    <div>
      <div class="title">Karen Dictionary Workbench</div>
      <div class="small">Merge, delete, reanalyze, copy candidate headwords, and keep original definitions intact.</div>
    </div>
    <div class="badges">
      <div class="badge" id="healthBadge">Health: ...</div>
      <div class="badge" id="entryCountBadge">Entries: 0</div>
      <div class="badge" id="correctionBadge">Corrections: 0</div>
    </div>
  </div>

  <div class="layout">
    <div>
      <div class="panel">
        <h3>Batch run</h3>
        <label>Upload PDF</label>
        <input id="pdfFile" type="file" accept=".pdf">
        <div class="grid2">
          <div>
            <label>Start page</label>
            <input id="pdfStart" type="number" value="1" min="1">
          </div>
          <div>
            <label>End page</label>
            <input id="pdfEnd" type="number" value="10" min="1">
          </div>
        </div>
        <div class="btn-row" style="margin-top:10px">
          <button class="btn-blue" onclick="runPdf()">Run PDF</button>
        </div>

        <label>Image folder path on server</label>
        <input id="folderPath" type="text" placeholder="/root/karenlangtrans/some_folder">
        <div class="grid2">
          <div>
            <label>Start image</label>
            <input id="folderStart" type="number" value="1" min="1">
          </div>
          <div>
            <label>Count</label>
            <input id="folderCount" type="number" placeholder="blank = config default" min="1">
          </div>
        </div>
        <div class="btn-row" style="margin-top:10px">
          <button class="btn-blue" onclick="runFolder()">Run folder</button>
        </div>

        <label>Upload images</label>
        <input id="imageFiles" type="file" multiple accept=".png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff">
        <div class="btn-row" style="margin-top:10px">
          <button class="btn-blue" onclick="runImages()">Run images</button>
        </div>

        <div class="btn-row" style="margin-top:12px">
          <button class="btn-green" onclick="importBootstrap()">Import bootstrap</button>
          <button class="btn-yellow" onclick="cancelBatch()">Cancel batch</button>
          <button class="btn-red" onclick="forceReset()">Force reset</button>
        </div>
      </div>

      <div class="panel">
        <h3>Status</h3>
        <div class="statusbox" id="statusBox">Loading...</div>
        <div class="footer-note">Live extraction status from the Flask worker.</div>
      </div>

      <div class="panel">
        <h3>Log</h3>
        <div class="logbox" id="logBox">Waiting...</div>
      </div>
    </div>

    <div>
      <div class="panel">
        <div class="meta">
          <div>
            <h3 style="margin-bottom:4px">Entries</h3>
            <div class="small" id="entriesMeta">Loading...</div>
          </div>
          <div class="btn-row" style="width:auto">
            <button class="btn-gray" onclick="loadEntries()">Refresh</button>
          </div>
        </div>

        <div class="search-row">
          <input id="q" type="text" placeholder="Search Karen, English, source, or type #12">
          <input id="page" type="number" placeholder="page">
          <label style="display:flex;align-items:center;gap:8px;margin:0;border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:#0c1322">
            <input id="flaggedOnly" type="checkbox" style="width:auto;margin:0">
            Flagged
          </label>
        </div>

        <div class="btn-row" style="margin-top:10px">
          <button class="btn-blue" onclick="loadEntries()">Search</button>
          <button class="btn-gray" onclick="clearSearch()">Clear</button>
        </div>

        <div class="entries" id="entries"></div>
      </div>
    </div>
  </div>
</div>

<div class="modal-backdrop" id="mergeBackdrop">
  <div class="modal">
    <h3>Merge entries</h3>
    <div class="small" id="mergeSummary">Choose another entry to merge into the current card.</div>
    <label>Search another entry by Karen, English, or #number</label>
    <input id="mergeQuery" type="text" placeholder="Type Karen text or #number">
    <div class="btn-row" style="margin-top:10px">
      <button class="btn-blue" onclick="searchMergeTargets()">Search</button>
      <button class="btn-gray" onclick="closeMerge()">Close</button>
    </div>
    <div class="merge-results" id="mergeResults"></div>
    <div class="btn-row" style="margin-top:12px">
      <button class="btn-green" onclick="confirmMerge()">Merge selected into current entry</button>
    </div>
  </div>
</div>

<button id="kb-launcher" type="button">Karen Keyboard</button>
<div id="kb-backdrop" hidden>
  <div id="kb-modal">
    <div id="kb-title">
      <strong>Karen Unicode Keyboard</strong>
      <button id="kb-close" class="kb-key kb-wide" type="button">Close</button>
    </div>
    <div id="kb-target-hint">Click into any input or textarea, then use the keyboard.</div>
    <div id="kb-grid"></div>
  </div>
</div>

<script>
const KB_ROWS = [
  ["က","ခ","ဂ","ဃ","င","စ","ဆ","ည","တ","ထ"],
  ["ဒ","န","ပ","ဖ","ဘ","မ","ယ","ရ","လ","ဝ"],
  ["သ","ဟ","အ","ၡ","ါ","ာ","ဲ","ိ","ီ","ံ"],
  ["ု","ူ","့","း","္","ျ","ြ","ွ","ှ","ၢ"]
];

const STATE = {
  entries: [],
  editIndex: null,
  merge: { open: false, current: null, target: null, results: [] },
  targetField: null
};

function esc(s){
  return String(s == null ? "" : s)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#39;");
}

function showToast(msg){
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => t.style.display = "none", 2800);
}

async function api(url, options){
  const res = await fetch(url, options || {});
  const data = await res.json().catch(() => ({}));
  if(!res.ok || data.ok === false){
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function currentEditValue(idx, type){
  const el = document.getElementById(type + "-" + idx);
  return el ? el.value : "";
}

async function loadHealth(){
  try{
    const data = await api("/api/health");
    document.getElementById("healthBadge").textContent =
      "Health: " + (data.key_ok ? "Gemini key present" : "No Gemini key");
  }catch(e){
    document.getElementById("healthBadge").textContent = "Health: error";
  }
}

async function pollStatus(){
  try{
    const data = await api("/api/status");
    const s = data.status || {};
    document.getElementById("statusBox").textContent =
      "running: " + !!s.running + "\\n" +
      "mode: " + (s.mode || "") + "\\n" +
      "file: " + (s.file || "") + "\\n" +
      "page: " + (s.page || "") + "\\n" +
      "done: " + (s.done || 0) + " / " + (s.total || 0) + "\\n" +
      "entries_added: " + (s.entries_added || 0) + "\\n" +
      "started: " + (s.started || "") + "\\n" +
      "finished: " + (s.finished || "") + "\\n" +
      "error: " + (s.error || "");
    document.getElementById("logBox").textContent = (s.log || []).join("\\n");
    if(!s.running){ loadEntries(false); }
  }catch(e){
    document.getElementById("statusBox").textContent = "Status error: " + e.message;
  }
}

async function loadEntries(keepHash=true){
  const params = new URLSearchParams();
  const q = document.getElementById("q").value.trim();
  const page = document.getElementById("page").value.trim();
  const flagged = document.getElementById("flaggedOnly").checked;
  if(q) params.set("q", q);
  if(page) params.set("page", page);
  if(flagged) params.set("flagged", "1");
  const url = "/api/entries" + (params.toString() ? "?" + params.toString() : "");
  const data = await api(url);
  STATE.entries = data.entries || [];
  document.getElementById("entriesMeta").textContent =
    (STATE.entries.length || 0) + " shown / " + (data.total || 0) + " total";
  document.getElementById("entryCountBadge").textContent = "Entries: " + (data.total || 0);
  document.getElementById("correctionBadge").textContent = "Corrections: " + (data.correction_count || 0);
  renderEntries();
  if(keepHash && location.hash){
    const el = document.querySelector(location.hash);
    if(el){ el.scrollIntoView({behavior:"smooth", block:"center"}); }
  }
}

function clearSearch(){
  document.getElementById("q").value = "";
  document.getElementById("page").value = "";
  document.getElementById("flaggedOnly").checked = false;
  loadEntries(false);
}

function renderChip(text, extraBtnHtml){
  return '<span class="chip"><span class="karen">' + esc(text || "") + '</span>' + (extraBtnHtml || "") + '</span>';
}

function renderEntry(e){
  const editing = STATE.editIndex === e.index;
  const defsView = (e.linked_definitions || []).map(d => '<div class="def">' + d + '</div>').join("");
  const defsEdit = esc((e.definitions || []).join("\\n"));
  const examples = (e.tab_examples || []).map(x => renderChip(x.text || "")).join("") || '<span class="small">None</span>';
  const related = (e.tab_related || []).map(x => renderChip((x.kind ? x.kind + ": " : "") + (x.text || ""))).join("") || '<span class="small">None</span>';
  const headTerms = (e.tab_headwords || []).map(x => {
    const term = x.text || "";
    const btn = '<button class="btn-gray" style="width:auto;padding:4px 8px;font-size:11px" onclick="spawnCandidate(' + e.index + ',' + JSON.stringify(term) + ')">Copy</button>';
    return renderChip(term, btn);
  }).join("") || '<span class="small">None</span>';

  return `
    <div class="card ${e.flag ? "flagged" : ""}" id="entry-${e.index}">
      <div class="card-head">
        <div>
          <div class="id-box">
            <span class="id-pill">#${e.index}</span>
            <span class="tag ${e.entry_type || "headword"}">${esc(e.entry_type || "headword")}</span>
            ${e.flag ? '<span class="tag flag">flagged</span>' : ''}
            ${e.promoted ? '<span class="tag headword">promoted</span>' : ''}
          </div>
          ${editing
            ? `<input id="karen-${e.index}" class="karen" value="${esc(e.karen || "")}" style="margin-top:10px;font-size:26px">`
            : `<div class="karen-head karen">${esc(e.karen || "")}</div>`
          }
          <div class="source">page ${esc(e.page || "")} • ${esc(e.source || "")}</div>
        </div>

        <div class="card-actions">
          ${editing
            ? `
              <button class="btn-green" onclick="saveEntry(${e.index})">Save</button>
              <button class="btn-gray" onclick="cancelEdit()">Cancel</button>
            `
            : `
              <button class="btn-blue" onclick="startEdit(${e.index})">Edit</button>
              <button class="btn-gray" onclick="reanalyze(${e.index})">Re-analyze</button>
              <button class="btn-yellow" onclick="openMerge(${e.index})">Merge</button>
              <button class="btn-gray" onclick="promote(${e.index})">Promote</button>
            `
          }
        </div>
      </div>

      <div class="defs">
        ${editing
          ? `<textarea id="defs-${e.index}">${defsEdit}</textarea>`
          : defsView
        }
      </div>

      <div class="info-grid">
        <div class="subpanel">
          <h4>Extracted examples</h4>
          <div class="chips">${examples}</div>
        </div>
        <div class="subpanel">
          <h4>Potential headwords (copy, do not cut)</h4>
          <div class="chips">${headTerms}</div>
        </div>
        <div class="subpanel">
          <h4>Related items</h4>
          <div class="chips">${related}</div>
        </div>
      </div>

      <div class="card-actions" style="justify-content:flex-end">
        <button class="btn-red" onclick="deleteEntry(${e.index})">Delete</button>
      </div>
    </div>
  `;
}

function renderEntries(){
  const host = document.getElementById("entries");
  if(!STATE.entries.length){
    host.innerHTML = '<div class="small">No entries found.</div>';
    return;
  }
  host.innerHTML = STATE.entries.map(renderEntry).join("");
  bindHeadwordLinks();
}

function bindHeadwordLinks(){
  document.querySelectorAll(".hw-link").forEach(a => {
    a.onclick = async (ev) => {
      ev.preventDefault();
      const idx = parseInt(a.dataset.idx, 10);
      await gotoEntry(idx);
      return false;
    };
  });
}

async function gotoEntry(idx){
  location.hash = "entry-" + idx;
  let el = document.getElementById("entry-" + idx);
  if(el){
    el.scrollIntoView({behavior:"smooth", block:"center"});
    return;
  }
  document.getElementById("q").value = "#" + idx;
  await loadEntries(true);
  el = document.getElementById("entry-" + idx);
  if(el){ el.scrollIntoView({behavior:"smooth", block:"center"}); }
}

function startEdit(idx){
  STATE.editIndex = idx;
  renderEntries();
}

function cancelEdit(){
  STATE.editIndex = null;
  renderEntries();
}

async function saveEntry(idx){
  const karen = currentEditValue(idx, "karen").trim();
  const defs = currentEditValue(idx, "defs").split("\\n").map(x => x.trim()).filter(Boolean);
  await api("/api/entry/" + idx, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({karen, definitions: defs})
  });
  STATE.editIndex = null;
  showToast("Entry saved.");
  await loadEntries(false);
  await gotoEntry(idx);
}

async function reanalyze(idx){
  await api("/api/reanalyze/" + idx, {method: "POST"});
  showToast("Entry re-analyzed.");
  await loadEntries(false);
  await gotoEntry(idx);
}

async function promote(idx){
  await api("/api/promote/" + idx, {method: "POST"});
  showToast("Entry promoted to headword.");
  await loadEntries(false);
  await gotoEntry(idx);
}

async function deleteEntry(idx){
  if(!confirm("Delete entry #" + idx + "?")) return;
  await api("/api/entry/" + idx, {method: "DELETE"});
  showToast("Entry deleted.");
  await loadEntries(false);
}

function openMerge(idx){
  const current = STATE.entries.find(x => x.index === idx);
  STATE.merge.open = true;
  STATE.merge.current = current;
  STATE.merge.target = null;
  STATE.merge.results = [];
  document.getElementById("mergeBackdrop").style.display = "flex";
  document.getElementById("mergeSummary").textContent =
    "Current entry: #" + idx + " " + (current ? current.karen : "");
  document.getElementById("mergeQuery").value = current && current.karen ? current.karen : "";
  searchMergeTargets();
}

function closeMerge(){
  STATE.merge.open = false;
  STATE.merge.current = null;
  STATE.merge.target = null;
  STATE.merge.results = [];
  document.getElementById("mergeBackdrop").style.display = "none";
  document.getElementById("mergeResults").innerHTML = "";
}

async function searchMergeTargets(){
  const q = document.getElementById("mergeQuery").value.trim();
  const data = await api("/api/entries" + (q ? ("?q=" + encodeURIComponent(q)) : ""));
  let items = (data.entries || []);
  if(STATE.merge.current){
    items = items.filter(x => x.index !== STATE.merge.current.index);
  } """


# =============================================================================
# VERIFIED ROUTES
# =============================================================================
PORTFOLIO_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sgaw Karen OCR Dictionary Workbench</title>
<style>
body{margin:0;background:#10131a;color:#eef2f7;font-family:Arial,Helvetica,sans-serif}
main{max-width:1120px;margin:0 auto;padding:28px}
.top{display:flex;gap:16px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
.panel{border:1px solid #283241;background:#171d27;border-radius:10px;padding:16px;margin:14px 0}
.muted{color:#a8b3c4;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
input,button,textarea{font:inherit;border-radius:8px;border:1px solid #374151;padding:10px;background:#0f1722;color:#eef2f7}
button{background:#2563eb;border-color:#2563eb;cursor:pointer}
button.secondary{background:#263041;border-color:#3b4658}
.entry{border-top:1px solid #2b3545;padding:14px 0}
.karen{font-family:'PadaukKaren','Myanmar Text',serif;font-size:26px}
pre{white-space:pre-wrap;background:#0f1722;border:1px solid #283241;border-radius:8px;padding:12px}
</style>
</head>
<body>
<main>
  <div class="top">
    <div>
      <h1>Sgaw Karen OCR Dictionary Workbench</h1>
      <p class="muted">Search, review, and batch-process extracted entries from the Sgaw Karen dictionary pipeline.</p>
    </div>
    <button class="secondary" onclick="refresh()">Refresh</button>
  </div>

  <div class="grid">
    <section class="panel">
      <h3>Status</h3>
      <pre id="status">Loading...</pre>
    </section>
    <section class="panel">
      <h3>Search</h3>
      <input id="q" placeholder="Karen, English, source, or #12" style="width:100%">
      <div style="margin-top:10px;display:flex;gap:8px">
        <button onclick="loadEntries()">Search</button>
        <button class="secondary" onclick="document.getElementById('q').value='';loadEntries()">Clear</button>
      </div>
    </section>
  </div>

  <section class="panel">
    <h3>Batch OCR</h3>
    <p class="muted">Requires GEMINI_API_KEY. Upload image files or a PDF, then watch status above.</p>
    <input id="images" type="file" accept="image/*" multiple>
    <button onclick="runImages()">Run Images</button>
    <br><br>
    <input id="pdf" type="file" accept=".pdf">
    <input id="start" type="number" value="1" min="1" style="width:80px">
    <input id="end" type="number" value="10" min="1" style="width:80px">
    <button onclick="runPdf()">Run PDF</button>
    <button class="secondary" onclick="post('/api/cancel')">Cancel</button>
  </section>

  <section class="panel">
    <h3>Entries</h3>
    <p class="muted" id="meta"></p>
    <div id="entries"></div>
  </section>
</main>
<script>
async function api(url, options){
  const res = await fetch(url, options || {});
  const data = await res.json().catch(() => ({}));
  if(!res.ok || data.ok === false) throw new Error(data.error || 'Request failed');
  return data;
}
async function post(url){
  await api(url, {method:'POST'});
  refresh();
}
async function refresh(){
  const h = await api('/api/health');
  const s = await api('/api/status');
  document.getElementById('status').textContent = JSON.stringify({health:h,status:s.status}, null, 2);
  loadEntries();
}
async function loadEntries(){
  const q = document.getElementById('q').value.trim();
  const data = await api('/api/entries' + (q ? '?q=' + encodeURIComponent(q) : ''));
  document.getElementById('meta').textContent = data.entries.length + ' shown / ' + data.total + ' total';
  document.getElementById('entries').innerHTML = data.entries.map(e => `
    <div class="entry" id="entry-${e.index}">
      <div class="karen">${escapeHtml(e.karen || '')}</div>
      <div class="muted">#${e.index} | page ${e.page || ''} | ${escapeHtml(e.entry_type || '')} | ${escapeHtml(e.source || '')}</div>
      <ul>${(e.display_definitions || e.definitions || []).map(d => `<li>${escapeHtml(d)}</li>`).join('')}</ul>
      <button class="secondary" onclick="post('/api/promote/${e.index}')">Promote</button>
      <button class="secondary" onclick="post('/api/reanalyze/${e.index}')">Re-analyze</button>
    </div>`).join('');
}
async function runImages(){
  const fd = new FormData();
  for(const f of document.getElementById('images').files) fd.append('images', f);
  await api('/api/run-images', {method:'POST', body:fd});
  refresh();
}
async function runPdf(){
  const file = document.getElementById('pdf').files[0];
  if(!file) return;
  const fd = new FormData();
  fd.append('pdf', file);
  fd.append('start', document.getElementById('start').value || '1');
  fd.append('end', document.getElementById('end').value || '10');
  await api('/api/run-pdf', {method:'POST', body:fd});
  refresh();
}
function escapeHtml(s){
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


def indexed_entries():
    entries = []
    for idx, entry in enumerate(load_dict()):
        e = norm(entry)
        e["index"] = idx
        entries.append(e)
    return entries


def entry_at(index):
    entries = load_dict()
    if index < 0 or index >= len(entries):
        raise IndexError("Entry index out of range")
    return entries, entries[index]


@app.route("/")
def index():
    return render_template_string(PORTFOLIO_PAGE)


@app.route("/api/health")
def api_health():
    return jsonify(
        {
            "ok": True,
            "key_ok": bool(GEMINI_API_KEY),
            "model": GEMINI_MODEL,
            "entries": len(load_dict()),
            "dictionary_file": str(DICT_FILE.name),
        }
    )


@app.route("/api/status")
def api_status():
    return jsonify({"ok": True, "status": _snap()})


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        return jsonify({"ok": True, "config": save_cfg(request.get_json(silent=True) or {})})
    return jsonify({"ok": True, "config": load_cfg()})


@app.route("/api/entries")
def api_entries():
    entries = indexed_entries()
    lookup = build_headword_lookup(entries)
    q = str(request.args.get("q", "")).strip().lower()
    page = str(request.args.get("page", "")).strip()
    flagged = request.args.get("flagged") == "1"

    if q.startswith("#") and q[1:].isdigit():
        target = int(q[1:])
        entries = [e for e in entries if e.get("index") == target]
    elif q:
        entries = [e for e in entries if q in search_blob(e)]
    if page:
        entries = [e for e in entries if str(e.get("page", "")) == page]
    if flagged:
        entries = [e for e in entries if e.get("flag")]

    view = [build_view_entry(e, lookup) for e in entries[:200]]
    return jsonify(
        {
            "ok": True,
            "entries": view,
            "total": len(load_dict()),
            "shown": len(view),
            "correction_count": len(load_corrections()),
        }
    )


@app.route("/api/entry/<int:index>", methods=["POST", "DELETE"])
def api_entry(index):
    entries, entry = entry_at(index)
    if request.method == "DELETE":
        removed = entries.pop(index)
        save_dict(entries)
        record_correction("delete_entry", {"index": index, "entry": removed})
        return jsonify({"ok": True, "deleted": index})

    data = request.get_json(silent=True) or {}
    updated = norm({**entry, **data})
    updated["updated_at"] = _now()
    entries[index] = updated
    save_dict(entries)
    record_correction("edit_entry", {"index": index})
    return jsonify({"ok": True, "entry": {**updated, "index": index}})


@app.route("/api/promote/<int:index>", methods=["POST"])
def api_promote(index):
    entries, entry = entry_at(index)
    entry["promoted"] = True
    entry["entry_type"] = "headword"
    entry["updated_at"] = _now()
    entries[index] = entry
    save_dict(entries)
    record_correction("promote_entry", {"index": index})
    return jsonify({"ok": True, "index": index})


@app.route("/api/reanalyze/<int:index>", methods=["POST"])
def api_reanalyze(index):
    entries, entry = entry_at(index)
    result = gemini_reanalyze_entry(entry)
    entry["entry_type"] = result["entry_type"]
    entry["analysis"] = result["analysis"]
    entry["updated_at"] = _now()
    entries[index] = entry
    save_dict(entries)
    record_correction("reanalyze_entry", {"index": index})
    return jsonify({"ok": True, "entry": {**entry, "index": index}})


@app.route("/api/import-bootstrap", methods=["POST"])
def api_import_bootstrap():
    return jsonify({"ok": True, "added": maybe_auto_import_bootstrap(force=True)})


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    with _lock:
        _state["cancel"] = True
    return jsonify({"ok": True})


@app.route("/api/force-reset", methods=["POST"])
def api_force_reset():
    _finish()
    return jsonify({"ok": True})


@app.route("/api/run-images", methods=["POST"])
def api_run_images():
    files = request.files.getlist("images")
    saved = []
    for f in files:
        if not f.filename:
            continue
        name = safe_name(f.filename)
        dest = IMG_DIR / name
        f.save(str(dest))
        saved.append(dest)
    if not saved:
        return jsonify({"ok": False, "error": "No image files uploaded"}), 400
    launch("images", worker_images, saved, load_cfg(), "upload")
    return jsonify({"ok": True, "queued": len(saved)})


@app.route("/api/run-pdf", methods=["POST"])
def api_run_pdf():
    f = request.files.get("pdf")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "No PDF uploaded"}), 400
    start = int(request.form.get("start", 1))
    end = int(request.form.get("end", start))
    dest = PDF_DIR / safe_name(f.filename)
    f.save(str(dest))
    launch("pdf", worker_pdf, dest, start, end, load_cfg())
    return jsonify({"ok": True, "queued": {"pdf": dest.name, "start": start, "end": end}})


if __name__ == "__main__":
    maybe_auto_import_bootstrap()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=True)
