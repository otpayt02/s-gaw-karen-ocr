import json, os
from PIL import Image, ImageDraw, ImageFont

INDEX_MAP  = "/root/karen_lang_trans/karen_index_map.json"
GAP_REPORT = "/root/karenlangtrans/032_true_gap_report.json"
FONT_PATH  = "/root/karenlangtrans/padauk-regular.ttf"
OUT_DIR    = "/root/karenlangtrans/glyph_check"

os.makedirs(OUT_DIR, exist_ok=True)

with open(INDEX_MAP)  as f: index_map = json.load(f)
with open(GAP_REPORT) as f: report = json.load(f)

stuck = [e for e in report["missed_classes"] if e.get("val_instances", 0) >= 10][:20]

print(f"[035] Rendering {len(stuck)} stuck syllable glyphs to {OUT_DIR}")

try:    font = ImageFont.truetype(FONT_PATH, 64)
except: font = ImageFont.load_default()

for e in stuck:
    idx      = e["class_idx"]
    syllable = index_map.get(str(idx), str(idx))
    img      = Image.new("RGB", (300, 120), (255, 255, 255))
    draw     = ImageDraw.Draw(img)
    draw.text((20, 20), syllable, font=font, fill=(0, 0, 0))
    draw.text((20, 85), f"idx={idx}", font=ImageFont.load_default(), fill=(150, 150, 150))
    fname    = f"{OUT_DIR}/idx{idx:04d}_{syllable}.png"
    img.save(fname)
    print(f"  idx={idx:5d}  syllable={syllable:20s}  val_inst={e['val_instances']}  → {fname}")

print(f"\n[035] Done. Download with:")
print(f'  scp -P 8998 -r root@146.115.17.156:/root/karenlangtrans/glyph_check "C:\\Users\\olive\\Projects\\karen_lang_trans\\glyph_check"')