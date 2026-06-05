import random
from pathlib import Path
from playwright.sync_api import sync_playwright

FONT_PATH = Path("/root/karenlangtrans/padauk_reg.ttf").resolve()
OUT_IMAGE = "/root/karenlangtrans/test_paragraph.png"

CONSONANTS = ["\u1000","\u1001","\u1002","\u1003","\u1004","\u1005","\u1006","\u1061","\u100A","\u1010","\u1011","\u1012","\u1014","\u1015","\u1016","\u1018","\u1019","\u101A","\u101B","\u101C","\u101D","\u101E","\u101F","\u1021","\u1027"]
VOWELS     = ["","\u102B","\u1036","\u1062","\u1037","\u102E","\u102D","\u1032","\u1030","\u102F"]
TONES      = ["","\u1038","\u1064","\u1063\u103A","\u1062\u103A","\u102C\u103A"]

random.seed(99)
def random_syllable():
    return random.choice(CONSONANTS) + random.choice(VOWELS) + random.choice(TONES)

# Wrap every syllable in a span so CSS margin controls spacing — not HTML spaces
def make_line(n=10):
    return "".join(f"<span>{random_syllable()}</span>" for _ in range(n))

lines = [make_line(10) for _ in range(6)]
paragraph_html = "<br>".join(lines)

html = (
    "<html><head><style>"
    "@font-face { font-family: 'Padauk'; src: url('file://" + str(FONT_PATH) + "'); }"
    "body { background: white; margin: 50px; font-family: 'Padauk'; font-size: 40px; "
    "line-height: 4.0; color: black; }"
    "span { display: inline-block; margin-right: 40px; margin-top: 22px; margin-bottom: 22px; }"
    "</style></head><body>"
    + paragraph_html +
    "</body></html>"
)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page    = browser.new_page(viewport={"width": 1200, "height": 700}, device_scale_factor=3)
    page.set_content(html)
    page.wait_for_timeout(600)
    page.screenshot(path=OUT_IMAGE, full_page=True)
    browser.close()

print(f"[039] Saved to {OUT_IMAGE}")
print(f"[039] {len(lines)} lines, span-spaced, 3x retina")
print("[039] NEXT: python3 /root/karenlangtrans/038_infer_paragraph.py")