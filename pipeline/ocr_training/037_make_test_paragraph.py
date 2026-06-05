import os, random
from PIL import Image, ImageDraw, ImageFont

INDEX_MAP  = "/root/karen_lang_trans/karen_index_map.json"
FONT_PATH  = "/root/karenlangtrans/padauk-regular.ttf"
OUT_IMAGE  = "/root/karenlangtrans/test_paragraph.png"

import json
with open(INDEX_MAP) as f: index_map = json.load(f)

# Pick 40 random syllables to form a fake paragraph
random.seed(42)
syllable_pool = [v for v in index_map.values()]
words = []
for _ in range(20):
    word_len = random.randint(2, 5)
    word = "".join(random.choices(syllable_pool, k=word_len))
    words.append(word)

lines = [" ".join(words[i:i+4]) for i in range(0, len(words), 4)]

try:    font = ImageFont.truetype(FONT_PATH, 36)
except: font = ImageFont.load_default()

img  = Image.new("RGB", (900, 400), (255, 255, 255))
draw = ImageDraw.Draw(img)

y = 30
for line in lines:
    draw.text((30, y), line, font=font, fill=(10, 10, 10))
    y += 70

img.save(OUT_IMAGE)
print(f"[037] Test paragraph saved to {OUT_IMAGE}")
print(f"[037] Lines written: {len(lines)}")
print(f"[037] NEXT: python3 /root/karenlangtrans/038_infer_paragraph.py")