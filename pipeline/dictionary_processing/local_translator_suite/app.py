from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from flask import Flask, Response, jsonify, render_template, request, stream_with_context


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SAMPLES_DIR = ROOT / "samples"
CACHE_FILE = DATA_DIR / "karen_reverse_cache.json"
ATTEMPTS_FILE = DATA_DIR / "lookup_attempts.json"
SEED_PLAN_FILE = DATA_DIR / "sgaw_mini_lm_seed_plan.json"
BATCH_OUTPUT_FILE = ROOT / "translations_updated.txt"

DATA_DIR.mkdir(exist_ok=True)
ATTEMPTS_FILE.touch(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
    )
}

SCRAPE_DELAY_SECONDS = float(os.environ.get("KAREN_SCRAPE_DELAY_SECONDS", "1"))
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("KAREN_REQUEST_TIMEOUT_SECONDS", "15"))

KAREN_RE = re.compile(r"[\u1000-\u109F]")
ENGLISH_RE = re.compile(r"[A-Za-z]")
LEADING_KAREN_LINE_RE = re.compile(r"^\s*[\u1000-\u109F]", re.MULTILINE)

KAREN_CONSONANTS = set("ကခဂဃငစဆၡညယရလဝသမဘဖပနဒထတဟအဧ")
KAREN_NUMERALS = set("0123456789၀၁၂၃၄၅၆၇၈၉")

PARTICLE_RULES: dict[str, dict[str, Any]] = {
    "တၢ်": {
        "gloss": "thing/action/nominalizer/the/a",
        "roles": ["nominalizer", "abstract noun maker", "article-like marker"],
        "placement": "before verbs/adjectives to make a noun phrase",
        "english_triggers": ["thing", "action", "process", "the", "a", "item", "field", "setting"],
    },
    "အ": {
        "gloss": "its/of/possessive/adjectival link",
        "roles": ["possessive", "genitive", "modifier linker"],
        "placement": "before possessed noun or property; often after the head concept in grammarized English",
        "english_triggers": ["its", "of", "property", "attribute", "belonging", "has"],
    },
    "လၢ": {
        "gloss": "of/for/to/in/at/as/regarding",
        "roles": ["preposition", "purpose", "location", "topic", "relative linker"],
        "placement": "before purpose/location/topic phrase",
        "english_triggers": ["of", "for", "to", "in", "at", "as", "regarding", "about", "on"],
    },
    "လၢအ": {
        "gloss": "that/which/who",
        "roles": ["relative clause linker"],
        "placement": "before a descriptive clause",
        "english_triggers": ["that", "which", "who", "where", "whose"],
    },
    "ဒီး": {
        "gloss": "and/with/then",
        "roles": ["coordination", "instrument/accompaniment", "sequence"],
        "placement": "between joined words or clauses",
        "english_triggers": ["and", "with", "plus", "then", "together"],
    },
    "ဆူ": {
        "gloss": "to/toward",
        "roles": ["direction", "destination"],
        "placement": "before destination",
        "english_triggers": ["to", "toward", "into", "onto", "go"],
    },
    "ဖဲ": {
        "gloss": "at/when/where",
        "roles": ["time", "place", "event location"],
        "placement": "before time/place clause",
        "english_triggers": ["at", "when", "where", "during"],
    },
    "ဒ်": {
        "gloss": "as/like/according to",
        "roles": ["comparison", "manner"],
        "placement": "before comparison/manner phrase",
        "english_triggers": ["as", "like", "according", "same"],
    },
    "ဒ်သိး": {
        "gloss": "so that/in order to/like",
        "roles": ["purpose", "comparison"],
        "placement": "before purpose clause",
        "english_triggers": ["so", "so that", "in order to", "like"],
    },
    "ခီဖျိ": {
        "gloss": "through/by means of/because of",
        "roles": ["means", "cause"],
        "placement": "before cause or method",
        "english_triggers": ["through", "via", "because", "by"],
    },
    "ဘၣ်ဃး": {
        "gloss": "about/concerning/related to",
        "roles": ["topic", "relationship"],
        "placement": "before topic phrase or after thing being related",
        "english_triggers": ["about", "concerning", "related", "regarding"],
    },
    "အဂ့ၢ်": {
        "gloss": "about/its matter/its reason",
        "roles": ["topic", "reason"],
        "placement": "after a noun phrase to say its matter/about it",
        "english_triggers": ["about", "matter", "reason", "story"],
    },
    "တဖၣ်": {
        "gloss": "plural",
        "roles": ["plural marker"],
        "placement": "after noun phrase",
        "english_triggers": ["plural", "many", "items", "files", "songs", "records"],
    },
    "အံၤ": {
        "gloss": "this",
        "roles": ["demonstrative"],
        "placement": "after noun phrase",
        "english_triggers": ["this", "these", "current"],
    },
    "န့ၣ်": {
        "gloss": "that/topic marker",
        "roles": ["demonstrative", "topic marker"],
        "placement": "after noun/topic phrase",
        "english_triggers": ["that", "those", "then"],
    },
    "မ့တမ့ၢ်": {
        "gloss": "or/otherwise",
        "roles": ["alternative"],
        "placement": "between alternatives",
        "english_triggers": ["or", "otherwise", "else"],
    },
    "မ့ၢ်": {
        "gloss": "is/be/true",
        "roles": ["copula", "identity"],
        "placement": "before predicate or identity phrase",
        "english_triggers": ["is", "are", "be", "being"],
    },
    "မ့ၢ်လၢ": {
        "gloss": "because/because of",
        "roles": ["cause"],
        "placement": "before reason clause",
        "english_triggers": ["because", "since", "due"],
    },
    "ထဲ": {
        "gloss": "only/just",
        "roles": ["limiter"],
        "placement": "before limited phrase",
        "english_triggers": ["only", "just", "single"],
    },
    "ခဲလၢာ်": {
        "gloss": "all/every",
        "roles": ["quantifier"],
        "placement": "after or before group phrase depending context",
        "english_triggers": ["all", "every", "whole"],
    },
    "ဒံး": {
        "gloss": "still/yet",
        "roles": ["aspect"],
        "placement": "near verb/adjective phrase",
        "english_triggers": ["still", "yet"],
    },
    "လံ": {
        "gloss": "already/completed",
        "roles": ["aspect", "completion"],
        "placement": "after verb clause",
        "english_triggers": ["already", "done", "completed", "saved"],
    },
    "တ": {
        "gloss": "not/no negative opener",
        "roles": ["negation"],
        "placement": "before negated word, often closed by ဘၣ်",
        "english_triggers": ["not", "no", "none", "without"],
    },
    "ဘၣ်": {
        "gloss": "must/right/negative closer",
        "roles": ["obligation", "negative closer"],
        "placement": "after negated clause or before required action",
        "english_triggers": ["must", "need", "right", "not"],
    },
    "အသီ": {
        "gloss": "new",
        "roles": ["modifier"],
        "placement": "after the noun it modifies",
        "english_triggers": ["new", "fresh", "recent"],
    },
    "အဂၤ": {
        "gloss": "other/another",
        "roles": ["modifier"],
        "placement": "after the noun it modifies",
        "english_triggers": ["other", "another", "alternate", "different"],
    },
}

CONNECTORS: dict[str, str] = {particle: rule["gloss"] for particle, rule in PARTICLE_RULES.items()}

ENGLISH_CONNECTORS: dict[str, str] = {}
for particle, rule in PARTICLE_RULES.items():
    for trigger in rule["english_triggers"]:
        ENGLISH_CONNECTORS.setdefault(trigger, particle)
ENGLISH_CONNECTORS.update(
    {
        "a": "တၢ်",
        "the": "တၢ်",
        "of": "အ",
        "for": "လၢ",
        "to": "ဆူ",
        "that": "လၢအ",
        "which": "လၢအ",
        "with": "ဒီး",
    }
)

CORE_TERMS: dict[str, str] = {
    "add": "ထၢနုာ်",
    "attribute": "တၢ်အိၣ်သး",
    "beat": "တၢ်ဒ့အခီၣ်",
    "button": "တၢ်ဆီၣ်အလီၢ်",
    "cancel": "မၤကတၢၢ်",
    "chart": "တၢ်သီၣ်အပနီၣ်စရီ",
    "choice": "တၢ်ဃုထၢ",
    "clear": "မၤကဆှီ",
    "close": "ကး",
    "database": "တၢ်အမံၤအသၣ်စရီ",
    "direct": "ဆှၢ",
    "editor": "တၢ်ကွဲးကျိၥ်အလီၢ်",
    "file": "လံာ်ဖိ",
    "folder": "တၢ်ပာ်ကီၤအလီၢ်",
    "guide": "တၢ်ဆှၢ",
    "keyboard": "ကီးဘိၣ်",
    "language": "တၢ်ကျိၥ်",
    "lyrics": "တၢ်သးဝံၣ်အလံၥ်မဲၥ်ဖျၢၣ်",
    "metadata": "တၢ်ဂ့ၢ်ပိၥ်ထွဲ",
    "modal": "တၢ်အိးထီၣ်လၢအဖီခိၣ်",
    "new": "အသီ",
    "note": "တၢ်သီၣ်",
    "open": "အိးထီၣ်",
    "panel": "တၢ်အလီၢ်",
    "property": "တၢ်အိၣ်သး",
    "search": "ဃု",
    "section": "အဆၢ",
    "select": "ဃုထၢ",
    "selection": "တၢ်ဃုထၢ",
    "settings": "တၢ်ပာ်လီၤ",
    "sidebar": "တၢ်အလီၢ်လၢကပၤ",
    "song": "တၢ်သးဝံၣ်",
    "switch": "ဆီတလဲ",
    "toggle": "အိးဒီးကး",
    "translation": "တၢ်ကွဲးကျိၥ်ထံ",
    "wizard": "တၢ်ဆှၢ",
    "definition": "တၢ်အခီပညီ",
    "display": "တၢ်ပၥ်ဖျါ",
    "interface": "တၢ်ပၥ်ဖျါအလီၢ်",
    "key": "ပျံၤ",
    "meaning": "တၢ်အခီပညီ",
    "name": "အမံၤ",
    "related": "ဘၣ်ဃး",
    "text": "လံၥ်",
    "thing": "တၢ်",
    "ui": "တၢ်ပၥ်ဖျါအလီၢ်",
    "user": "ၦၤသူတၢ်",
    "value": "တၢ်လုၢ်တၢ်ပှ့ၤ",
    "web": "ကွဲၤလ့လိၤ",
    "website": "ကွဲၤလ့လိၤအလီၢ်",
    "word": "တၢ်ကတိၤ",
}

GENERIC_UI_FALLBACK = "တၢ်လၢအဘၣ်ဃးဒီးတၢ်ပၥ်ဖျါအလီၢ်"

ACTION_WORDS = {
    "add",
    "apply",
    "browse",
    "cancel",
    "change",
    "clear",
    "close",
    "copy",
    "create",
    "delete",
    "direct",
    "download",
    "edit",
    "filter",
    "find",
    "guide",
    "help",
    "load",
    "move",
    "open",
    "parse",
    "play",
    "process",
    "remove",
    "run",
    "save",
    "search",
    "select",
    "set",
    "show",
    "switch",
    "toggle",
    "translate",
    "upload",
    "view",
}

PROPERTY_WORDS = {
    "attribute",
    "category",
    "count",
    "date",
    "field",
    "format",
    "key",
    "label",
    "metadata",
    "mode",
    "name",
    "property",
    "setting",
    "status",
    "style",
    "title",
    "type",
    "value",
}

MUSIC_WORDS = {
    "audio",
    "beat",
    "chart",
    "chord",
    "choir",
    "guitar",
    "hymn",
    "key",
    "lyrics",
    "measure",
    "melody",
    "music",
    "note",
    "performance",
    "piano",
    "song",
    "tempo",
    "verse",
    "video",
}

UI_WORDS = {
    "button",
    "database",
    "dialog",
    "display",
    "editor",
    "file",
    "folder",
    "interface",
    "keyboard",
    "menu",
    "modal",
    "overlay",
    "page",
    "panel",
    "screen",
    "search",
    "section",
    "sidebar",
    "tab",
    "text",
    "ui",
    "web",
    "website",
    "wizard",
}

COMPOSED_FALLBACKS: dict[str, dict[str, str]] = {
    "new song wizard": {
        "karen": "တၢ်ဆှၢလၢဃုထၢတၢ်သးဝံၣ်အသီအတၢ်အိၣ်သး",
        "description": "a guide that helps select new song properties",
        "grammarized": "guide that select song new its properties",
    },
    "guided new song wizard": {
        "karen": "တၢ်ဆှၢလၢဃုထၢတၢ်သးဝံၣ်အသီအတၢ်အိၣ်သး",
        "description": "a guide that helps select new song properties",
        "grammarized": "guide that select song new its properties",
    },
    "sidebar": {
        "karen": "တၢ်အလီၢ်လၢကပၤ",
        "description": "the side area",
        "grammarized": "area of side",
    },
    "toggle sidebar": {
        "karen": "အိးဒီးကးတၢ်အလီၢ်လၢကပၤ",
        "description": "open and close the side area",
        "grammarized": "open and close area of side",
    },
    "search files and song metadata": {
        "karen": "ဃုလံာ်ဖိတဖၣ်ဒီးတၢ်သးဝံၣ်အတၢ်ဂ့ၢ်ပိၥ်ထွဲ",
        "description": "search files and song metadata",
        "grammarized": "search files plural and song its following facts",
    },
}

BAD_RESULT_MARKERS = (
    "no translation",
    "no exact",
    "sorry, no results",
    "fatal error",
    "not found",
    "failed",
)

BAD_EXACT_RESULTS = {
    "about glosbe",
    "about us",
    "add examples in batch",
    "add translations in batch",
    "all dictionaries",
    "contact us",
    "dictionary",
    "dictionary builder",
    "downloads",
    "feedback",
    "home",
    "partners",
    "privacy policy",
    "pronunciation recorder",
    "transliteration",
    "version",
}

ENGLISH_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "has",
    "have",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
    "you",
    "your",
}

Emit = Callable[[str, str], None]
emit_lock = threading.Lock()
json_lock = threading.Lock()
live_state_lock = threading.Lock()
live_stop_event = threading.Event()

LIVE_STATE: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "updated_at": None,
    "source_file": str(SAMPLES_DIR / "translations_website.txt"),
    "output_file": str(BATCH_OUTPUT_FILE),
    "total_lines": 0,
    "processed_lines": 0,
    "changed_count": 0,
    "parsed_count": 0,
    "current": None,
    "rows": [],
    "output_tail": "",
    "message": "Idle.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_json_load(path: Path, default: Any) -> Any:
    if not path.exists() or path.stat().st_size == 0:
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + f".bad-{int(time.time())}")
        path.replace(backup)
        return default


def safe_json_write(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def contains_karen(text: str) -> bool:
    return bool(KAREN_RE.search(text or ""))


def contains_english(text: str) -> bool:
    return bool(ENGLISH_RE.search(text or ""))


def normalize_english(text: str) -> str:
    text = (text or "").replace("_", " ").replace("-", " ").replace("&", " and ")
    text = re.sub(r"[^A-Za-z0-9' ]+", " ", text)
    return " ".join(text.lower().split())


def clean_visible_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_useful_result(value: str, query: str, direction: str) -> bool:
    text = clean_visible_text(value)
    if not text or len(text) > 180:
        return False
    lowered = text.lower()
    if lowered in BAD_EXACT_RESULTS:
        return False
    if any(marker in lowered for marker in BAD_RESULT_MARKERS):
        return False
    if direction == "en-to-ksw":
        return contains_karen(text)
    return contains_english(text)


def make_emit(events: list[dict[str, Any]] | None = None, q: queue.Queue | None = None) -> Callable[..., None]:
    def emit(stage: str, message: str, **details: Any) -> None:
        payload = {
            "id": str(uuid.uuid4()),
            "time": utc_now(),
            "stage": stage,
            "message": message,
            "details": details,
        }
        if events is not None:
            events.append(payload)
        if q is not None:
            q.put(payload)

    return emit


def record_attempt(
    *,
    direction: str,
    query: str,
    stage: str,
    source: str,
    status: str,
    results: list[str] | None = None,
    url: str | None = None,
    elapsed_ms: int | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    record = {
        "id": str(uuid.uuid4()),
        "timestamp": utc_now(),
        "direction": direction,
        "query": query,
        "stage": stage,
        "source": source,
        "status": status,
        "results": results or [],
        "url": url,
        "elapsed_ms": elapsed_ms,
        "error": error,
        "metadata": metadata or {},
    }
    with json_lock:
        attempts = safe_json_load(ATTEMPTS_FILE, [])
        attempts.append(record)
        safe_json_write(ATTEMPTS_FILE, attempts)


def load_cache() -> dict[str, Any]:
    return safe_json_load(CACHE_FILE, {})


def save_cache(cache: dict[str, Any]) -> None:
    safe_json_write(CACHE_FILE, cache)


def cache_key(direction: str, query: str) -> str:
    return f"{direction}::{query.strip()}"


def cache_get(direction: str, query: str) -> str | None:
    cache = load_cache()
    key = cache_key(direction, query)
    value = cache.get(key)
    if isinstance(value, dict):
        result = value.get("result")
        return result if isinstance(result, str) and result else None
    if isinstance(value, str) and value:
        return value
    # Legacy reverse cache format: {"ကစၢၢ်": "mountain"}.
    if direction == "ksw-to-en":
        legacy = cache.get(query)
        if isinstance(legacy, str) and legacy:
            return legacy
    return None


def cache_set(direction: str, query: str, result: str, source: str) -> None:
    with json_lock:
        cache = load_cache()
        cache[cache_key(direction, query)] = {
            "result": result,
            "source": source,
            "updated_at": utc_now(),
        }
        save_cache(cache)


def load_seed_translations() -> dict[str, str]:
    seeds: dict[str, str] = {}
    for path in (SAMPLES_DIR / "translations_website.txt", SAMPLES_DIR / "translations_updated.txt"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" not in raw or raw.lstrip().startswith("#"):
                continue
            left, right = [part.strip() for part in raw.split("=", 1)]
            if contains_english(left) and contains_karen(right):
                seeds[normalize_english(left)] = right
            if contains_english(right) and contains_karen(left):
                seeds[normalize_english(right)] = left
    return seeds


def detect_direction(text: str, forced_mode: str, emit: Callable[..., None]) -> str:
    mode = (forced_mode or "auto").strip()
    emit(
        "detect",
        "Scanning Unicode and manual mode.",
        forced_mode=mode,
        has_karen=contains_karen(text),
        has_english=contains_english(text),
        starts_with_karen_line=bool(LEADING_KAREN_LINE_RE.search(text or "")),
    )
    if mode in {"en-to-ksw", "ksw-to-en"}:
        emit("route", "Manual routing selected.", direction=mode)
        return mode
    if LEADING_KAREN_LINE_RE.search(text or "") or contains_karen(text):
        emit("route", "Karen Unicode detected; routing to reverse parser.", direction="ksw-to-en")
        return "ksw-to-en"
    if contains_english(text):
        emit("route", "English letters detected; routing to English-to-Karen.", direction="en-to-ksw")
        return "en-to-ksw"
    emit("route", "No strong script signal; defaulting to English-to-Karen.", direction="en-to-ksw")
    return "en-to-ksw"


def scrape_get(url: str, source: str, query: str, emit: Callable[..., None]) -> requests.Response:
    emit("scrape_wait", "Rate-limit delay before website scrape.", source=source, seconds=SCRAPE_DELAY_SECONDS)
    time.sleep(SCRAPE_DELAY_SECONDS)
    started = time.perf_counter()
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        emit("scrape_response", "Website responded.", source=source, status=response.status_code, elapsed_ms=elapsed_ms)
        return response
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        record_attempt(
            direction="unknown",
            query=query,
            stage="web",
            source=source,
            status="error",
            url=url,
            elapsed_ms=elapsed_ms,
            error=str(exc),
        )
        emit("scrape_error", "Website request failed.", source=source, error=str(exc), elapsed_ms=elapsed_ms)
        raise


def extract_candidates_from_html(html: str, query: str, direction: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    summary = soup.find(id="content-summary")
    if summary:
        for strong in summary.find_all("strong"):
            text = clean_visible_text(strong.get_text(" ", strip=True))
            if text and text.lower() != query.lower():
                candidates.append(text)

    for selector in (
        "span.translation__snippet",
        "[data-element='phraseTranslation']",
        ".translation",
        "li",
        "p",
        "h2",
        "h3",
    ):
        for node in soup.select(selector):
            text = clean_visible_text(node.get_text(" ", strip=True))
            if text:
                candidates.append(text)

    if len(candidates) < 3:
        for line in soup.get_text("\n", strip=True).splitlines():
            text = clean_visible_text(line)
            if text:
                candidates.append(text)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        item = item.strip(" -*•|")
        if direction == "ksw-to-en" and contains_karen(item) and contains_english(item):
            item = clean_visible_text(KAREN_RE.sub(" ", item).strip(" -*•|·,;:"))
        if not item or item in seen:
            continue
        if is_useful_result(item, query, direction):
            seen.add(item)
            deduped.append(item)
    return deduped[:8]


def scrape_glosbe(query: str, direction: str, emit: Callable[..., None]) -> dict[str, Any]:
    source_lang, target_lang = ("en", "ksw") if direction == "en-to-ksw" else ("ksw", "en")
    url = f"https://glosbe.com/{source_lang}/{target_lang}/{quote_plus(query)}"
    started = time.perf_counter()
    try:
        response = scrape_get(url, "glosbe", query, emit)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        html = response.text if response.status_code in {200, 404} else ""
        results = extract_candidates_from_html(html, query, direction) if html else []
        status = "found" if results else "empty"
        record_attempt(
            direction=direction,
            query=query,
            stage="web",
            source="glosbe",
            status=status,
            results=results,
            url=url,
            elapsed_ms=elapsed_ms,
            metadata={"http_status": response.status_code},
        )
        emit("dictionary", "Glosbe lookup finished.", source="glosbe", query=query, status=status, results=results[:3])
        return {"source": "glosbe", "url": url, "status": status, "results": results}
    except Exception as exc:
        return {"source": "glosbe", "url": url, "status": "error", "results": [], "error": str(exc)}


def scrape_karen_dictionary(query: str, direction: str, emit: Callable[..., None]) -> dict[str, Any]:
    url = f"https://www.karendictionary.org/?q={quote_plus(query)}"
    started = time.perf_counter()
    try:
        response = scrape_get(url, "karendictionary.org", query, emit)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        html = response.text if response.status_code in {200, 404} else ""
        results = extract_candidates_from_html(html, query, direction) if html else []
        status = "found" if results else "empty"
        record_attempt(
            direction=direction,
            query=query,
            stage="web",
            source="karendictionary.org",
            status=status,
            results=results,
            url=url,
            elapsed_ms=elapsed_ms,
            metadata={"http_status": response.status_code, "note": "HTML scrape only; no Supabase/API calls"},
        )
        emit(
            "dictionary",
            "KarenDictionary.org lookup finished.",
            source="karendictionary.org",
            query=query,
            status=status,
            results=results[:3],
        )
        return {"source": "karendictionary.org", "url": url, "status": status, "results": results}
    except Exception as exc:
        return {"source": "karendictionary.org", "url": url, "status": "error", "results": [], "error": str(exc)}


def scrape_drum(query: str, direction: str, emit: Callable[..., None]) -> dict[str, Any]:
    url = f"https://www.drumpublications.org/dictionarynew.php?look4e={quote_plus(query)}"
    if direction == "ksw-to-en":
        url = f"https://www.drumpublications.org/dictionarynew.php?look4k={quote_plus(query)}"
    started = time.perf_counter()
    try:
        response = scrape_get(url, "drumpublications.org", query, emit)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        html = response.text if response.status_code in {200, 404, 500} else ""
        results = extract_candidates_from_html(html, query, direction) if html else []
        status = "found" if results else "empty"
        record_attempt(
            direction=direction,
            query=query,
            stage="web",
            source="drumpublications.org",
            status=status,
            results=results,
            url=url,
            elapsed_ms=elapsed_ms,
            metadata={"http_status": response.status_code},
        )
        emit("dictionary", "Drum Publications fallback finished.", source="drumpublications.org", status=status)
        return {"source": "drumpublications.org", "url": url, "status": status, "results": results}
    except Exception as exc:
        return {"source": "drumpublications.org", "url": url, "status": "error", "results": [], "error": str(exc)}


def lookup_web(query: str, direction: str, emit: Callable[..., None]) -> dict[str, Any]:
    emit("dictionary", "Starting required dual-source lookup.", query=query, direction=direction)
    glosbe = scrape_glosbe(query, direction, emit)
    karen_dictionary = scrape_karen_dictionary(query, direction, emit)
    drum = {"source": "drumpublications.org", "status": "skipped", "results": []}
    if not karen_dictionary["results"]:
        emit("fallback", "KarenDictionary.org returned no usable result; checking Drum Publications.", query=query)
        drum = scrape_drum(query, direction, emit)

    chosen_source = None
    chosen_result = None
    for source_result in (glosbe, karen_dictionary, drum):
        if source_result.get("results"):
            chosen_source = source_result["source"]
            chosen_result = source_result["results"][0]
            break

    if chosen_result:
        cache_set(direction, query, chosen_result, chosen_source or "web")
        emit("match", "Dictionary match selected.", query=query, result=chosen_result, source=chosen_source)
    else:
        emit("fallback", "No web dictionary result selected.", query=query)

    return {
        "query": query,
        "direction": direction,
        "result": chosen_result,
        "source": chosen_source,
        "sources": [glosbe, karen_dictionary, drum],
    }


def extract_internet_keywords(query: str, results: list[dict[str, str]]) -> list[str]:
    scores: dict[str, int] = {}
    query_tokens = split_english_tokens(query)
    text = " ".join(
        [query, *[item.get("title", "") for item in results], *[item.get("snippet", "") for item in results]]
    )
    for token in split_english_tokens(text):
        if len(token) < 3 or token in ENGLISH_STOPWORDS or token.isdigit():
            continue
        scores[token] = scores.get(token, 0) + 1
        if token in query_tokens:
            scores[token] += 4
        if token in CORE_TERMS:
            scores[token] += 6
    return [token for token, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:14]]


def search_internet_context(query: str, emit: Callable[..., None]) -> dict[str, Any]:
    search_query = f"{normalize_english(query)} definition meaning music website user interface"
    url = f"https://duckduckgo.com/html/?q={quote_plus(search_query)}"
    started = time.perf_counter()
    try:
        response = scrape_get(url, "internet-search", query, emit)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        results: list[dict[str, str]] = []
        if response.status_code in {200, 202}:
            soup = BeautifulSoup(response.text, "html.parser")
            for node in soup.select(".result"):
                title_node = node.select_one(".result__a")
                snippet_node = node.select_one(".result__snippet")
                title = clean_visible_text(title_node.get_text(" ", strip=True) if title_node else "")
                snippet = clean_visible_text(snippet_node.get_text(" ", strip=True) if snippet_node else "")
                href = title_node.get("href", "") if title_node else ""
                if title or snippet:
                    results.append({"title": title, "snippet": snippet, "url": href})
                if len(results) >= 5:
                    break
        keywords = extract_internet_keywords(query, results)
        status = "found" if results else "empty"
        readable = [
            clean_visible_text(f"{item.get('title', '')}: {item.get('snippet', '')}")[:220]
            for item in results
        ]
        record_attempt(
            direction="en-to-ksw",
            query=query,
            stage="internet_search",
            source="duckduckgo-html",
            status=status,
            results=readable,
            url=url,
            elapsed_ms=elapsed_ms,
            metadata={"keywords": keywords, "http_status": response.status_code},
        )
        emit(
            "internet_search",
            "Internet context search finished.",
            source="duckduckgo-html",
            query=query,
            status=status,
            results=readable,
            keywords=keywords,
        )
        return {"source": "duckduckgo-html", "status": status, "results": results, "keywords": keywords, "url": url}
    except Exception as exc:
        record_attempt(
            direction="en-to-ksw",
            query=query,
            stage="internet_search",
            source="duckduckgo-html",
            status="error",
            url=url,
            error=str(exc),
        )
        emit("internet_search", "Internet context search failed.", source="duckduckgo-html", query=query, status="error", error=str(exc))
        return {"source": "duckduckgo-html", "status": "error", "results": [], "keywords": [], "url": url, "error": str(exc)}


def lookup_local(query: str, direction: str, emit: Callable[..., None]) -> dict[str, Any] | None:
    if direction == "ksw-to-en" and query in CONNECTORS:
        meaning = CONNECTORS[query]
        record_attempt(
            direction=direction,
            query=query,
            stage="connector",
            source="hardcoded-connectors",
            status="found",
            results=[meaning],
        )
        emit("connector", "Grammar connector matched.", chunk=query, meaning=meaning)
        return {"result": meaning, "source": "connector", "query": query}

    cached = cache_get(direction, query)
    if cached:
        record_attempt(direction=direction, query=query, stage="cache", source="json-cache", status="found", results=[cached])
        emit("cache", "Local JSON cache hit.", query=query, result=cached)
        return {"result": cached, "source": "cache", "query": query}

    record_attempt(direction=direction, query=query, stage="cache", source="json-cache", status="miss")
    emit("cache", "Local JSON cache miss.", query=query)
    return None


def split_english_tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^A-Za-z0-9']+", normalize_english(text)) if token]


def classify_english_token(token: str) -> list[str]:
    roles: list[str] = []
    if token in ENGLISH_CONNECTORS:
        roles.append("connector")
    if token in ACTION_WORDS or token.endswith("ing") or token.endswith("ed"):
        roles.append("action")
    if token in PROPERTY_WORDS:
        roles.append("property")
    if token in MUSIC_WORDS:
        roles.append("music")
    if token in UI_WORDS:
        roles.append("interface")
    if token in CORE_TERMS:
        roles.append("known-karen-term")
    if not roles and token not in ENGLISH_STOPWORDS:
        roles.append("content-word")
    return roles or ["function-word"]


def choose_particle_for_english_word(token: str, roles: list[str]) -> dict[str, str]:
    if token in ENGLISH_CONNECTORS:
        particle = ENGLISH_CONNECTORS[token]
        rule = PARTICLE_RULES.get(particle, {})
        return {
            "particle": particle,
            "why": f"`{token}` directly triggers {particle}: {rule.get('gloss', '')}",
            "placement": rule.get("placement", ""),
        }
    if "property" in roles:
        return {
            "particle": "အ",
            "why": "property words usually connect as `its/of` using အ",
            "placement": PARTICLE_RULES["အ"]["placement"],
        }
    if "action" in roles:
        return {
            "particle": "တၢ်",
            "why": "actions often become noun-like UI labels with တၢ်",
            "placement": PARTICLE_RULES["တၢ်"]["placement"],
        }
    if "interface" in roles:
        return {
            "particle": "လၢ",
            "why": "interface/location words often need `for/in/regarding` linkage",
            "placement": PARTICLE_RULES["လၢ"]["placement"],
        }
    return {
        "particle": "",
        "why": "no connector needed unless neighboring words require a relation",
        "placement": "",
    }


def mini_lm_analyze_english(query: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    tokens = split_english_tokens(query)
    context_keywords = [word for word in (context or {}).get("keywords", []) if word not in tokens]
    all_words = [*tokens, *context_keywords[:12]]
    word_roles = []
    for token in all_words:
        roles = classify_english_token(token)
        connector = choose_particle_for_english_word(token, roles)
        word_roles.append(
            {
                "word": token,
                "source": "input" if token in tokens else "internet-context",
                "roles": roles,
                "suggested_particle": connector["particle"],
                "particle_reason": connector["why"],
                "placement": connector["placement"],
                "known_karen": CORE_TERMS.get(token) or ENGLISH_CONNECTORS.get(token) or "",
            }
        )

    thought = " ".join(tokens)
    if any(item["word"] == "song" for item in word_roles) and any(item["word"] == "new" for item in word_roles):
        grammarized = " ".join("song new" if word == "song" else word for word in tokens)
    else:
        grammarized = thought

    full_description = (
        f"Define `{query}` as a short website/music-interface phrase. "
        "Prefer known Karen content words, then connect them with nominalizers, possession, purpose, topic, and coordination particles."
    )
    return {
        "input": query,
        "tokens": tokens,
        "context_keywords": context_keywords,
        "word_roles": word_roles,
        "full_description_goal": full_description,
        "grammarized_english_goal": grammarized,
    }


def compose_english_to_karen(query: str, emit: Callable[..., None], context: dict[str, Any] | None = None) -> dict[str, str] | None:
    normalized = normalize_english(query)
    if normalized in COMPOSED_FALLBACKS:
        data = COMPOSED_FALLBACKS[normalized]
        emit("compose", "Known UI/music definition composed from Karen words.", **data)
        return data

    tokens = split_english_tokens(query)
    context_keywords = [token for token in (context or {}).get("keywords", []) if token not in tokens]
    keyword_tokens = [token for token in [*tokens, *context_keywords] if token in CORE_TERMS or token in ENGLISH_CONNECTORS]
    if not tokens:
        return None

    if "song" in tokens and "new" in tokens and ("wizard" in tokens or "guide" in tokens):
        data = COMPOSED_FALLBACKS["new song wizard"]
        emit("compose", "Music app wizard phrase inferred from component words.", **data)
        return data

    pieces: list[str] = []
    missing: list[str] = []
    for token in keyword_tokens or tokens:
        karen = CORE_TERMS.get(token) or ENGLISH_CONNECTORS.get(token)
        if karen:
            pieces.append(karen)
        else:
            missing.append(token)

    if not pieces:
        return None

    chosen_tokens = keyword_tokens or tokens
    if "song" in chosen_tokens and "new" in chosen_tokens:
        grammarized = " ".join("song new" if token == "song" else token for token in chosen_tokens)
    else:
        grammarized = " ".join(chosen_tokens)

    description = " ".join(chosen_tokens)
    if missing:
        description += f" (missing direct Karen terms: {', '.join(missing)})"
    if context and context.get("keywords"):
        description += f" [internet keywords: {', '.join(context['keywords'][:8])}]"

    data = {
        "karen": "".join(pieces),
        "description": description,
        "grammarized": grammarized,
    }
    emit("compose", "Composed shortest available Karen definition from known terms.", **data)
    return data


def build_english_word_thoughts(query: str, context: dict[str, Any], emit: Callable[..., None]) -> list[dict[str, Any]]:
    mini_lm = mini_lm_analyze_english(query, context)
    emit("mini_lm", "Mini grammar model analyzed English structure.", **mini_lm)
    role_by_word = {item["word"]: item for item in mini_lm["word_roles"]}
    tokens = split_english_tokens(query)
    context_keywords = [word for word in context.get("keywords", []) if word not in tokens]
    candidates = []
    seen: set[str] = set()
    for token in [*tokens, *context_keywords]:
        if token in seen or token in ENGLISH_STOPWORDS or len(token) < 2:
            continue
        seen.add(token)
        candidates.append(token)

    thoughts: list[dict[str, Any]] = []
    for token in candidates[:18]:
        known = CORE_TERMS.get(token) or ENGLISH_CONNECTORS.get(token)
        role_info = role_by_word.get(token, {})
        thought: dict[str, Any] = {
            "word": token,
            "role": "original key token" if token in tokens else "internet related keyword",
            "roles": role_info.get("roles", classify_english_token(token)),
            "suggested_particle": role_info.get("suggested_particle", ""),
            "particle_reason": role_info.get("particle_reason", ""),
            "placement": role_info.get("placement", ""),
            "known_karen": known,
            "dictionary_result": "",
            "source": "",
            "decision": "",
        }
        if known:
            thought["decision"] = "Used local Karen term for this component."
        else:
            emit("word_thought", "Trying component word because whole phrase did not resolve.", word=token)
            local = lookup_local(token, "en-to-ksw", emit)
            if local:
                thought["dictionary_result"] = local["result"]
                thought["source"] = local["source"]
                thought["decision"] = "Used component result from cache/local lookup."
            else:
                web = lookup_web(token, "en-to-ksw", emit)
                if web.get("result"):
                    thought["dictionary_result"] = web["result"]
                    thought["source"] = web["source"]
                    thought["decision"] = "Used component result from dictionary lookup."
                else:
                    thought["decision"] = "No component translation found; kept only as semantic context."
        record_attempt(
            direction="en-to-ksw",
            query=token,
            stage="word_thought",
            source=thought.get("source") or ("local-core-terms" if known else "component-analysis"),
            status="found" if (thought.get("known_karen") or thought.get("dictionary_result")) else "context-only",
            results=[item for item in [thought.get("known_karen"), thought.get("dictionary_result"), thought.get("decision")] if item],
            metadata={"role": thought["role"], "decision": thought["decision"]},
        )
        thoughts.append(thought)
    emit("thought_process", "English component thought pass complete.", thoughts=thoughts)
    return thoughts


def compose_from_word_thoughts(
    query: str,
    context: dict[str, Any],
    thoughts: list[dict[str, Any]],
    emit: Callable[..., None],
) -> dict[str, str]:
    pieces: list[str] = []
    used_words: list[str] = []
    for thought in thoughts:
        karen = thought.get("known_karen") or thought.get("dictionary_result")
        if karen and contains_karen(str(karen)):
            pieces.append(str(karen))
            used_words.append(str(thought.get("word")))

    if pieces:
        karen = "".join(pieces)
        description = f"definition using available component words: {', '.join(used_words)}"
        grammarized = " ".join(used_words)
    else:
        karen = GENERIC_UI_FALLBACK
        description = "generic website-interface thing because no component Karen terms were found"
        grammarized = "thing that is regarding website interface"

    if context.get("keywords"):
        description += f" [internet related words: {', '.join(context['keywords'][:10])}]"

    data = {"karen": karen, "description": description, "grammarized": grammarized}
    emit("compose", "Forced non-empty Karen definition fallback selected.", **data)
    return data


def translate_english_to_karen(query: str, emit: Callable[..., None]) -> dict[str, Any]:
    normalized = normalize_english(query)
    emit("normalize", "English key normalized.", original=query, normalized=normalized)
    internet_context = search_internet_context(normalized, emit) if normalized else {"keywords": [], "results": []}
    mini_lm = mini_lm_analyze_english(normalized, internet_context)
    emit("mini_lm", "Mini grammar model prepared connector plan.", **mini_lm)

    seeds = load_seed_translations()
    if normalized in seeds:
        result = seeds[normalized]
        emit("cache", "Seed translation file match.", query=normalized, result=result)
        return {
            "direction": "en-to-ksw",
            "input": query,
            "output": result,
            "source": "seed-translations",
            "description": "existing translation from sample translation files",
            "grammarized": normalized,
            "internet_context": internet_context,
            "mini_lm": mini_lm,
        }

    local = lookup_local(normalized, "en-to-ksw", emit)
    if local:
        return {
            "direction": "en-to-ksw",
            "input": query,
            "output": local["result"],
            "source": local["source"],
            "description": "local cached direct translation",
            "grammarized": normalized,
            "internet_context": internet_context,
            "mini_lm": mini_lm,
        }

    web = lookup_web(normalized, "en-to-ksw", emit)
    if web["result"]:
        return {
            "direction": "en-to-ksw",
            "input": query,
            "output": web["result"],
            "source": web["source"],
            "description": "direct dictionary translation",
            "grammarized": normalized,
            "sources": web["sources"],
            "internet_context": internet_context,
            "mini_lm": mini_lm,
        }

    word_thoughts = build_english_word_thoughts(normalized, internet_context, emit)
    composed = compose_english_to_karen(normalized, emit, internet_context)
    if not composed:
        composed = compose_from_word_thoughts(normalized, internet_context, word_thoughts, emit)
    if composed:
        cache_set("en-to-ksw", normalized, composed["karen"], "composed-definition")
        return {
            "direction": "en-to-ksw",
            "input": query,
            "output": composed["karen"],
            "source": "composed-definition",
            "description": composed["description"],
            "grammarized": composed["grammarized"],
            "internet_context": internet_context,
            "mini_lm": mini_lm,
            "word_thoughts": word_thoughts,
        }

    # Defensive only: compose_from_word_thoughts always returns a non-empty
    # Karen fallback, because blank translations are not useful in batch work.
    fallback = compose_from_word_thoughts(normalized, internet_context, word_thoughts, emit)
    return {
        "direction": "en-to-ksw",
        "input": query,
        "output": fallback["karen"],
        "source": "forced-generic-definition",
        "description": fallback["description"],
        "grammarized": fallback["grammarized"],
        "internet_context": internet_context,
        "mini_lm": mini_lm,
        "word_thoughts": word_thoughts,
    }


def split_karen_syllables(text: str) -> list[str]:
    syllables: list[str] = []
    current = ""
    for ch in text or "":
        if ch in KAREN_NUMERALS or ch.isspace():
            if current:
                syllables.append(current)
                current = ""
            continue
        if not contains_karen(ch):
            if current:
                syllables.append(current)
                current = ""
            continue
        if ch in KAREN_CONSONANTS:
            if current:
                syllables.append(current)
            current = ch
        else:
            current += ch
    if current:
        syllables.append(current)
    return syllables


def join_syllables(syllables: list[str], start: int, end: int) -> str:
    return "".join(syllables[start:end])


def find_connector_spans(syllables: list[str]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    connector_syllables = sorted(
        ((split_karen_syllables(connector), connector) for connector in CONNECTORS),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    for i in range(len(syllables)):
        for parts, connector in connector_syllables:
            end = i + len(parts)
            if end <= len(syllables) and syllables[i:end] == parts:
                spans.append((i, end, connector))
    return spans


def add_candidate(candidates: list[tuple[int, str, str]], seen: set[tuple[int, str]], end: int, chunk: str, reason: str) -> None:
    if not chunk:
        return
    key = (end, chunk)
    if key in seen:
        return
    seen.add(key)
    candidates.append((end, chunk, reason))


def prioritized_karen_chunks(syllables: list[str], start: int) -> list[tuple[int, str, str]]:
    n = len(syllables)
    spans = find_connector_spans(syllables)
    candidates: list[tuple[int, str, str]] = []
    seen: set[tuple[int, str]] = set()

    add_candidate(candidates, seen, n, join_syllables(syllables, start, n), "whole remaining word")

    for span_start, span_end, connector in spans:
        if span_end <= start:
            continue
        if span_start > start:
            add_candidate(
                candidates,
                seen,
                span_start,
                join_syllables(syllables, start, span_start),
                "before connector",
            )
        add_candidate(
            candidates,
            seen,
            span_end,
            join_syllables(syllables, start, span_end),
            "through connector",
        )
        if span_start == start:
            next_starts = [s for s, _, _ in spans if s > span_end]
            stop = min(next_starts) if next_starts else n
            add_candidate(
                candidates,
                seen,
                stop,
                join_syllables(syllables, start, stop),
                "connector plus following segment",
            )
        if span_end > start:
            next_starts = [s for s, _, _ in spans if s > span_end]
            stop = min(next_starts) if next_starts else n
            if span_end < stop:
                add_candidate(
                    candidates,
                    seen,
                    stop,
                    join_syllables(syllables, span_end, stop),
                    "between connectors excluding connector",
                )

    for end in range(n, start, -1):
        add_candidate(
            candidates,
            seen,
            end,
            join_syllables(syllables, start, end),
            "all contiguous combinations longest-first",
        )

    return candidates


def lookup_karen_chunk(chunk: str, direction: str, emit: Callable[..., None]) -> dict[str, Any] | None:
    local = lookup_local(chunk, direction, emit)
    if local:
        return local
    web = lookup_web(chunk, direction, emit)
    if web["result"]:
        return {"query": chunk, "result": web["result"], "source": web["source"], "sources": web["sources"]}
    return None


def reverse_parse_karen(text: str, emit: Callable[..., None]) -> dict[str, Any]:
    syllables = split_karen_syllables(text)
    emit("parse", "Karen syllables split by consonant anchors.", syllables=syllables, count=len(syllables))
    connector_spans = [
        {"start": start, "end": end, "connector": connector, "meaning": CONNECTORS.get(connector, "")}
        for start, end, connector in find_connector_spans(syllables)
    ]
    emit("connector", "Connector scan complete.", connectors=connector_spans)

    whole = "".join(syllables)
    whole_match = None
    parse_attempts: list[dict[str, Any]] = []
    if whole:
        emit("parse", "Trying whole string before connector or syllable splitting.", chunk=whole)
        whole_match = lookup_karen_chunk(whole, "ksw-to-en", emit)
        parse_attempts.append(
            {
                "index": 0,
                "end": len(syllables),
                "chunk": whole,
                "reason": "whole string first",
                "status": "matched" if whole_match else "miss",
                "result": whole_match.get("result") if whole_match else "",
                "source": whole_match.get("source") if whole_match else "",
            }
        )

    parts: list[dict[str, Any]] = []
    i = 0
    while i < len(syllables):
        emit("parse", "Starting forward-match loop.", index=i, remaining=join_syllables(syllables, i, len(syllables)))
        matched = None
        for end, chunk, reason in prioritized_karen_chunks(syllables, i):
            if end <= i:
                continue
            emit("parse_candidate", "Testing candidate chunk.", index=i, end=end, chunk=chunk, reason=reason)
            match = lookup_karen_chunk(chunk, "ksw-to-en", emit)
            attempt = {
                "index": i,
                "end": end,
                "chunk": chunk,
                "reason": reason,
                "status": "matched" if match else "miss",
                "result": match.get("result") if match else "",
                "source": match.get("source") if match else "",
            }
            if len(parse_attempts) < 800:
                parse_attempts.append(attempt)
            if match:
                matched = {"chunk": chunk, "meaning": match["result"], "source": match["source"], "end": end, "reason": reason}
                break
        if matched:
            parts.append({key: matched[key] for key in ("chunk", "meaning", "source", "reason")})
            emit("match", "Forward-match chunk accepted.", chunk=matched["chunk"], meaning=matched["meaning"], source=matched["source"])
            i = matched["end"]
        else:
            stuck = syllables[i]
            record_attempt(direction="ksw-to-en", query=stuck, stage="stuck", source="parser", status="unresolved")
            parts.append({"chunk": stuck, "meaning": "??", "source": "unresolved", "reason": "stuck single syllable"})
            if len(parse_attempts) < 800:
                parse_attempts.append(
                    {
                        "index": i,
                        "end": i + 1,
                        "chunk": stuck,
                        "reason": "stuck single syllable",
                        "status": "unresolved",
                        "result": "??",
                        "source": "parser",
                    }
                )
            emit("stuck", "No candidate matched; advancing by one syllable.", syllable=stuck, index=i)
            i += 1

    inferred = infer_english_from_parts(parts)
    emit("infer", "Shortest English guess assembled from matched chunks.", inferred=inferred)
    return {
        "direction": "ksw-to-en",
        "input": text,
        "output": inferred,
        "whole_match": whole_match,
        "syllables": syllables,
        "connectors": connector_spans,
        "parse_attempts": parse_attempts,
        "parts": parts,
        "breakdown": format_breakdown(parts),
        "source": "reverse-parser",
    }


def infer_english_from_parts(parts: list[dict[str, Any]]) -> str:
    words: list[str] = []
    for part in parts:
        meaning = str(part.get("meaning") or "").strip()
        if not meaning or meaning == "??":
            continue
        words.append(meaning.split("/")[0].split(",")[0].strip())
    return " ".join(words) if words else "unresolved"


def format_breakdown(parts: list[dict[str, Any]]) -> str:
    return " + ".join(f"({part['chunk']}: {part['meaning']})" for part in parts)


def lookup_text(text: str, mode: str, emit: Callable[..., None]) -> dict[str, Any]:
    direction = detect_direction(text, mode, emit)
    if direction == "en-to-ksw":
        return translate_english_to_karen(text, emit)
    return reverse_parse_karen(text, emit)


def reset_live_state(source_file: str, output_file: str, total_lines: int) -> None:
    with live_state_lock:
        LIVE_STATE.update(
            {
                "running": True,
                "started_at": utc_now(),
                "updated_at": utc_now(),
                "source_file": source_file,
                "output_file": output_file,
                "total_lines": total_lines,
                "processed_lines": 0,
                "changed_count": 0,
                "parsed_count": 0,
                "current": None,
                "rows": [],
                "output_tail": "",
                "message": "Running.",
            }
        )


def update_live_state(**updates: Any) -> None:
    with live_state_lock:
        LIVE_STATE.update(updates)
        LIVE_STATE["updated_at"] = utc_now()


def append_live_row(row: dict[str, Any], output_lines: list[str], analysis_lines: list[str]) -> None:
    output_snapshot = output_lines[:]
    if analysis_lines:
        output_snapshot.extend(["", "# --- REVERSE TRANSLATION ANALYSIS ---", *analysis_lines])
    output_tail = "\n".join(output_snapshot[-80:])
    with live_state_lock:
        rows = [*LIVE_STATE.get("rows", []), row]
        LIVE_STATE["rows"] = rows[-300:]
        LIVE_STATE["current"] = row
        LIVE_STATE["processed_lines"] = row.get("line_no", LIVE_STATE.get("processed_lines", 0))
        LIVE_STATE["output_tail"] = output_tail
        LIVE_STATE["updated_at"] = utc_now()


def public_live_state() -> dict[str, Any]:
    with live_state_lock:
        return json.loads(json.dumps(LIVE_STATE, ensure_ascii=False))


def dictionary_summary(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for event in events:
        if event.get("stage") not in {"cache", "connector", "internet_search", "dictionary", "match", "fallback", "parse_candidate", "word_thought", "thought_process", "mini_lm"}:
            continue
        details = event.get("details", {})
        source = details.get("source") or ("parser" if event.get("stage") == "parse_candidate" else event.get("stage"))
        results = details.get("results", [])
        if event.get("stage") == "parse_candidate":
            results = [f"{details.get('chunk', '')} ({details.get('reason', '')})"]
        if event.get("stage") == "word_thought":
            results = [f"{details.get('word', '')}: {event.get('message', '')}"]
        if event.get("stage") == "thought_process":
            results = [
                f"{item.get('word')}: {item.get('decision')}"
                for item in details.get("thoughts", [])[:12]
            ]
        if event.get("stage") == "mini_lm":
            results = [
                f"{item.get('word')}: {','.join(item.get('roles', []))} -> {item.get('suggested_particle') or 'no connector'}"
                for item in details.get("word_roles", [])[:12]
            ]
        if event.get("stage") == "internet_search" and details.get("keywords"):
            results = [*results, f"keywords: {', '.join(details.get('keywords', [])[:12])}"]
        if not results and details.get("result"):
            results = [details.get("result")]
        if not results and details.get("meaning"):
            results = [details.get("meaning")]
        if not results:
            results = [event.get("message", "")]
        summary.append(
            {
                "source": source,
                "query": details.get("query"),
                "status": details.get("status") or event.get("stage"),
                "results": results,
            }
        )
    return summary[:80]


def row_status(events: list[dict[str, Any]], default: str) -> str:
    for event in reversed(events):
        if event.get("stage") == "match":
            return "matched"
        if event.get("stage") == "fallback":
            return "fallback"
        if event.get("stage") == "stuck":
            return "unresolved"
    return default


def write_live_output(output_lines: list[str], analysis_lines: list[str]) -> str:
    snapshot = output_lines[:]
    if analysis_lines:
        snapshot.extend(["", "# --- REVERSE TRANSLATION ANALYSIS ---", *analysis_lines])
    text = "\n".join(snapshot) + "\n"
    BATCH_OUTPUT_FILE.write_text(text, encoding="utf-8")
    sample_updated = SAMPLES_DIR / "translations_updated.txt"
    sample_updated.write_text(text, encoding="utf-8")
    return text


def emit_batch_row(emit: Callable[..., None], row: dict[str, Any], output_lines: list[str], analysis_lines: list[str]) -> None:
    append_live_row(row, output_lines, analysis_lines)
    emit("batch_row", "Line status updated.", **row)


def process_batch_text(
    content: str,
    mode: str,
    emit: Callable[..., None],
    *,
    source_file: str = "uploaded text",
    live_write: bool = False,
) -> dict[str, Any]:
    output_lines: list[str] = []
    analysis_lines: list[str] = []
    changed_count = 0
    parsed_count = 0
    lines = content.splitlines()
    last_live_write = 0.0

    if live_write:
        reset_live_state(source_file, str(BATCH_OUTPUT_FILE), len(lines))

    for line_no, raw in enumerate(lines, start=1):
        if live_write and live_stop_event.is_set():
            emit("batch_done", "Live file run stopped by user.", processed_lines=line_no - 1)
            break

        line = raw.rstrip("\n")
        stripped = line.strip()
        line_events: list[dict[str, Any]] = []

        def line_emit(stage: str, message: str, **details: Any) -> None:
            payload = {
                "id": str(uuid.uuid4()),
                "time": utc_now(),
                "stage": stage,
                "message": message,
                "details": details,
            }
            line_events.append(payload)
            emit(stage, message, **details)

        line_emit("batch_line", "Processing line.", line=line_no, has_equals="=" in line, starts_karen=bool(LEADING_KAREN_LINE_RE.match(line)))
        row: dict[str, Any] = {
            "line_no": line_no,
            "raw": line,
            "trying": stripped,
            "expected_target": "none",
            "direction": "skip",
            "lookup_status": "skipped",
            "dictionary": [],
            "chosen": "",
            "output_line": line,
            "breakdown": "",
        }

        if not stripped or stripped.startswith("#"):
            output_lines.append(line)
            emit_batch_row(emit, row, output_lines, analysis_lines)
            if live_write and time.time() - last_live_write >= 0.5:
                write_live_output(output_lines, analysis_lines)
                last_live_write = time.time()
            continue

        if "=" in line:
            left, right = [part.strip() for part in line.split("=", 1)]
            left_is_karen = contains_karen(left)
            right_is_karen = contains_karen(right)
            left_is_english = contains_english(left)
            right_is_english = contains_english(right)
            line_emit(
                "batch_detect",
                "Detected sides around equals sign.",
                line=line_no,
                left_is_karen=left_is_karen,
                right_is_karen=right_is_karen,
                left_is_english=left_is_english,
                right_is_english=right_is_english,
            )

            if left_is_english and not right.strip():
                row.update(
                    {
                        "trying": left,
                        "expected_target": "Karen value on right side of =",
                        "direction": "en-to-ksw",
                    }
                )
                translated = translate_english_to_karen(left, line_emit)
                output_line = f"{left} = {translated['output']}"
                output_lines.append(output_line)
                changed_count += 1
                row.update(
                    {
                        "lookup_status": row_status(line_events, translated.get("source", "translated")),
                        "dictionary": dictionary_summary(line_events),
                        "chosen": translated.get("output", ""),
                        "output_line": output_line,
                        "breakdown": f"description: {translated.get('description', '')}; grammarized: {translated.get('grammarized', '')}",
                        "word_thoughts": translated.get("word_thoughts", []),
                    }
                )
                if translated.get("description"):
                    analysis_lines.append(
                        f"# {left} -> {translated['output']} "
                        f"(description: {translated['description']}; grammarized: {translated['grammarized']})"
                    )
                emit_batch_row(emit, row, output_lines, analysis_lines)
                update_live_state(changed_count=changed_count, parsed_count=parsed_count)
                if live_write and time.time() - last_live_write >= 0.5:
                    write_live_output(output_lines, analysis_lines)
                    last_live_write = time.time()
                continue

            if right_is_karen:
                row.update(
                    {
                        "trying": right,
                        "expected_target": f"English explanation for key `{left}`",
                        "direction": "ksw-to-en",
                    }
                )
                parsed = reverse_parse_karen(right, line_emit)
                analysis_lines.append(f"# {left} = {right} -> {parsed['breakdown']} -> guess: {parsed['output']}")
                parsed_count += 1
                row.update(
                    {
                        "lookup_status": row_status(line_events, "parsed"),
                        "dictionary": dictionary_summary(line_events),
                        "chosen": parsed.get("output", ""),
                        "breakdown": parsed.get("breakdown", ""),
                    }
                )
            elif left_is_karen:
                row.update(
                    {
                        "trying": left,
                        "expected_target": f"English value on right side of = `{right}`",
                        "direction": "ksw-to-en",
                    }
                )
                parsed = reverse_parse_karen(left, line_emit)
                key = right if right else "bare-karen-key"
                analysis_lines.append(f"# {key} = {left} -> {parsed['breakdown']} -> guess: {parsed['output']}")
                parsed_count += 1
                row.update(
                    {
                        "lookup_status": row_status(line_events, "parsed"),
                        "dictionary": dictionary_summary(line_events),
                        "chosen": parsed.get("output", ""),
                        "breakdown": parsed.get("breakdown", ""),
                    }
                )
            else:
                row.update(
                    {
                        "trying": left,
                        "expected_target": "existing non-Karen value kept",
                        "direction": "skip",
                        "lookup_status": "kept",
                        "chosen": right,
                    }
                )
            output_lines.append(line)
            row["output_line"] = line
            emit_batch_row(emit, row, output_lines, analysis_lines)
            update_live_state(changed_count=changed_count, parsed_count=parsed_count)
            if live_write and time.time() - last_live_write >= 0.5:
                write_live_output(output_lines, analysis_lines)
                last_live_write = time.time()
            continue

        if LEADING_KAREN_LINE_RE.match(line):
            row.update(
                {
                    "trying": line,
                    "expected_target": "English explanation for bare Karen line",
                    "direction": "ksw-to-en",
                }
            )
            parsed = reverse_parse_karen(line, line_emit)
            analysis_lines.append(f"# bare line {line_no}: {line} -> {parsed['breakdown']} -> guess: {parsed['output']}")
            parsed_count += 1
            output_lines.append(line)
            row.update(
                {
                    "lookup_status": row_status(line_events, "parsed"),
                    "dictionary": dictionary_summary(line_events),
                    "chosen": parsed.get("output", ""),
                    "output_line": line,
                    "breakdown": parsed.get("breakdown", ""),
                }
            )
            emit_batch_row(emit, row, output_lines, analysis_lines)
            update_live_state(changed_count=changed_count, parsed_count=parsed_count)
            if live_write and time.time() - last_live_write >= 0.5:
                write_live_output(output_lines, analysis_lines)
                last_live_write = time.time()
            continue

        output_lines.append(line)
        emit_batch_row(emit, row, output_lines, analysis_lines)
        if live_write and time.time() - last_live_write >= 0.5:
            write_live_output(output_lines, analysis_lines)
            last_live_write = time.time()

    if analysis_lines:
        output_lines.extend(["", "# --- REVERSE TRANSLATION ANALYSIS ---", *analysis_lines])

    processed = "\n".join(output_lines) + "\n"
    BATCH_OUTPUT_FILE.write_text(processed, encoding="utf-8")
    (SAMPLES_DIR / "translations_updated.txt").write_text(processed, encoding="utf-8")
    if live_write:
        update_live_state(
            running=False,
            changed_count=changed_count,
            parsed_count=parsed_count,
            processed_lines=min(len(lines), LIVE_STATE.get("processed_lines", len(lines))),
            output_tail="\n".join(processed.splitlines()[-80:]),
            message="Complete." if not live_stop_event.is_set() else "Stopped.",
        )
    emit(
        "batch_done",
        "Batch processing complete and translations_updated.txt written.",
        changed_count=changed_count,
        parsed_count=parsed_count,
        output_file=str(BATCH_OUTPUT_FILE),
    )
    return {
        "processed_text": processed,
        "changed_count": changed_count,
        "parsed_count": parsed_count,
        "output_file": str(BATCH_OUTPUT_FILE),
        "download_name": "translations_updated.txt",
    }


def sse_payload(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def stream_worker(worker: Callable[[Callable[..., None]], dict[str, Any]]) -> Response:
    q: queue.Queue = queue.Queue()

    def emit(stage: str, message: str, **details: Any) -> None:
        make_emit(q=q)(stage, message, **details)

    def run() -> None:
        try:
            result = worker(emit)
            q.put({"stage": "complete", "message": "Complete.", "result": result, "time": utc_now()})
        except Exception as exc:
            q.put({"stage": "error", "message": str(exc), "time": utc_now(), "details": {}})
        finally:
            q.put(None)

    threading.Thread(target=run, daemon=True).start()

    @stream_with_context
    def generate():
        while True:
            payload = q.get()
            if payload is None:
                break
            yield sse_payload(payload)

    return Response(generate(), mimetype="text/event-stream")


app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
)


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/lookup")
def api_lookup() -> Response:
    payload = request.get_json(force=True, silent=True) or {}
    events: list[dict[str, Any]] = []
    emit = make_emit(events=events)
    result = lookup_text(str(payload.get("text", "")), str(payload.get("mode", "auto")), emit)
    return jsonify({"result": result, "audit": events})


@app.post("/api/lookup-stream")
def api_lookup_stream() -> Response:
    payload = request.get_json(force=True, silent=True) or {}
    text = str(payload.get("text", ""))
    mode = str(payload.get("mode", "auto"))
    return stream_worker(lambda emit: lookup_text(text, mode, emit))


@app.post("/api/batch-stream")
def api_batch_stream() -> Response:
    mode = request.form.get("mode", "auto")
    uploaded = request.files.get("file")
    if uploaded:
        content = uploaded.read().decode("utf-8-sig", errors="replace")
    else:
        content = request.form.get("content", "")
    return stream_worker(lambda emit: process_batch_text(content, mode, emit))


@app.post("/api/live-file-stream")
def api_live_file_stream() -> Response:
    source_path = SAMPLES_DIR / "translations_website.txt"
    payload = request.get_json(force=True, silent=True) or {}
    mode = str(payload.get("mode", request.form.get("mode", "auto")))
    if public_live_state().get("running"):
        return stream_worker(lambda emit: {"error": "A live translations_website.txt run is already active."})
    live_stop_event.clear()
    content = source_path.read_text(encoding="utf-8-sig", errors="replace")
    return stream_worker(
        lambda emit: process_batch_text(
            content,
            mode,
            emit,
            source_file=str(source_path),
            live_write=True,
        )
    )


@app.post("/api/live-stop")
def api_live_stop() -> Response:
    live_stop_event.set()
    update_live_state(message="Stop requested.")
    return jsonify({"ok": True, "state": public_live_state()})


@app.get("/api/live-state")
def api_live_state() -> Response:
    return jsonify(public_live_state())


@app.get("/api/attempts")
def api_attempts() -> Response:
    limit = int(request.args.get("limit", "200"))
    attempts = safe_json_load(ATTEMPTS_FILE, [])
    return jsonify({"attempts": attempts[-limit:], "total": len(attempts)})


@app.get("/api/cache")
def api_cache() -> Response:
    cache = load_cache()
    return jsonify({"count": len(cache), "cache": cache})


@app.get("/api/mini-lm-seed-plan")
def api_mini_lm_seed_plan() -> Response:
    return jsonify(safe_json_load(SEED_PLAN_FILE, {"target_total": 0, "bands": []}))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5057, debug=os.environ.get("FLASK_DEBUG") == "1", threaded=True)
