# ============================================================
# FILE: 1_gen_train_data.py
# PURPOSE: Generates synthetic Karen syllable images for YOLO
#          training. Renders every base consonant + medial +
#          vowel + tone combination using Padauk font, applies
#          augmentations (blur, rotation, noise), and writes
#          YOLO-format bounding box label .txt files.
# PIPELINE POSITION: Dataset generation — runs FIRST before training
# REQUIRES: padauk-regular.ttf in /root/karen_lang_trans/
# PRODUCES: train/images/, train/labels/, valid/images/, valid/labels/
#           classes.txt, data.yaml
# ============================================================

# IMPORT — PIL Image and ImageDraw for rendering Karen Unicode glyphs
from PIL import Image, ImageDraw, ImageFont

# IMPORT — OpenCV for image augmentation (blur, noise, rotation)
import cv2

# IMPORT — NumPy for pixel array manipulation during augmentation
import numpy as np

# IMPORT — os for creating output directories and writing files
import os

# IMPORT — random for selecting augmentation parameters randomly
import random

# IMPORT — json for saving the class index map alongside the dataset
import json

# IMPORT — yaml for writing data.yaml in YOLO-compatible format
import yaml

# VARIABLE DECLARATION — output root directory for the full dataset
OUT_DIR = '/root/karen_dataset_yolov8'

# VARIABLE DECLARATION — path to the Karen-capable Padauk Unicode font
# WHY: standard system fonts do not render Myanmar/Karen Unicode correctly;
#      Padauk is the only reliably Karen-compatible open-source font
FONT_PATH = '/root/karen_lang_trans/padauk-regular.ttf'

# VARIABLE DECLARATION — image size in pixels (square)
# WHY: 320x320 matches YOLO's preferred input resolution for YOLOv8s
IMG_SIZE = 320

# VARIABLE DECLARATION — font rendering size in points
FONT_SIZE = 180

# LIST/DICT/SET — all 25 Sgaw Karen base consonants as Unicode strings
# WHY: every syllable begins with one of these consonants
BASE_CONSONANTS = [
    'က', 'ခ', 'ဂ', 'ဃ', 'င',
    'စ', 'ဆ', 'ဇ', 'ဈ', 'ည',
    'ဋ', 'ဌ', 'ဍ', 'ဎ', 'ဏ',
    'တ', 'ထ', 'ဒ', 'ဓ', 'န',
    'ပ', 'ဖ', 'ဗ', 'ဘ', 'မ',
    'ယ', 'ရ', 'လ', 'ဝ', 'သ',
    'ဟ', 'ဠ', 'အ'
]

# LIST/DICT/SET — Karen medial consonants (optional modifiers after base)
MEDIALS = ['', '\u103c', '\u103d', '\u103e']

# LIST/DICT/SET — Karen vowel markers (diacritics above/below base)
VOWELS = [
    '',       # inherent -uh vowel (no marker needed)
    '\u102c', # -aa
    '\u102d', # -i
    '\u102e', # -ii
    '\u102f', # -u
    '\u1030', # -uu
    '\u1031', # -e (pre-vowel)
    '\u1032', # -ai
    '\u1036', # -an (nasal)
    '\u103a'  # -ah (asat/stop)
]

# LIST/DICT/SET — Karen tone markers (unique to Karen, not Burmese)
TONES = [
    '',       # tone 1 — low level (no marker)
    '\u1037', # tone 2 — low falling
    '\u1038', # tone 3 — high level
    '\u1039', # tone 4 — creaky
    '\u103b', # tone 5 — high falling
    '\u103c'  # tone 6 — mid level
]

# FUNCTION DEFINITION — renders one Karen syllable string to a PIL image
# PARAMETER — syllable: Unicode string combining base+medial+vowel+tone
# PARAMETER — font: pre-loaded ImageFont object for Padauk
def render_syllable(syllable, font):
    # INSTANTIATION — creates a white square image canvas
    img = Image.new('RGB', (IMG_SIZE, IMG_SIZE), color=(255, 255, 255))
    # INSTANTIATION — creates a drawing context on the image
    draw = ImageDraw.Draw(img)
    # METHOD CALL — measures the bounding box of the rendered syllable text
    bbox = draw.textbbox((0, 0), syllable, font=font)
    # VARIABLE DECLARATION — calculates centered X position for the text
    x = (IMG_SIZE - (bbox[2] - bbox[0])) // 2
    # VARIABLE DECLARATION — calculates centered Y position for the text
    y = (IMG_SIZE - (bbox[3] - bbox[1])) // 2
    # METHOD CALL — draws the Karen syllable centered on the white canvas
    draw.text((x, y), syllable, font=font, fill=(0, 0, 0))
    return img

# FUNCTION DEFINITION — applies random augmentations to a PIL image
# PARAMETER — img: the clean rendered syllable image
# RETURN STATEMENT — returns the augmented image as a NumPy array
def augment(img):
    # METHOD CALL — converts PIL image to OpenCV BGR NumPy array
    arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    # CONDITIONAL — randomly applies Gaussian blur to simulate ink spread
    if random.random() < 0.5:
        k = random.choice([3, 5])
        arr = cv2.GaussianBlur(arr, (k, k), 0)
    # CONDITIONAL — randomly adds pixel noise to simulate paper texture
    if random.random() < 0.3:
        noise = np.random.randint(0, 25, arr.shape, dtype=np.uint8)
        arr = cv2.add(arr, noise)
    return arr

# FUNCTION CALL — loads the Padauk font at the specified size
font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

# FUNCTION CALL — creates all required output subdirectories
for split in ['train', 'valid']:
    os.makedirs(f'{OUT_DIR}/{split}/images', exist_ok=True)
    os.makedirs(f'{OUT_DIR}/{split}/labels', exist_ok=True)

# VARIABLE DECLARATION — list that accumulates all class name strings
# WHY: this becomes the 'names' list in data.yaml and classes.txt
class_names = []

# VARIABLE DECLARATION — class index counter incremented for each new syllable
class_idx = 0

# LOOP — iterates over every base consonant
for base in BASE_CONSONANTS:
    # LOOP — iterates over every medial (including empty string = no medial)
    for medial in MEDIALS:
        # LOOP — iterates over every vowel marker
        for vowel in VOWELS:
            # LOOP — iterates over every tone marker
            for tone in TONES:
                # VARIABLE DECLARATION — the full Unicode syllable string
                syllable = base + medial + vowel + tone

                # VARIABLE DECLARATION — romanized class name for this syllable
                # WHY: class names are stored as numeric strings matching Roboflow convention
                cls_name = str(class_idx)
                class_names.append(cls_name)

                # VARIABLE DECLARATION — train/valid split (80/20)
                split = 'train' if random.random() < 0.8 else 'valid'

                # FUNCTION CALL — renders the syllable to a clean image
                img = render_syllable(syllable, font)

                # FUNCTION CALL — applies random augmentations
                aug = augment(img)

                # VARIABLE DECLARATION — output image filename
                img_name = f'{cls_name}.jpg'

                # FILE OPERATION — saves the augmented image to the correct split folder
                cv2.imwrite(f'{OUT_DIR}/{split}/images/{img_name}', aug)

                # VARIABLE DECLARATION — YOLO bounding box (full image, centered)
                # WHY: since the syllable is centered, bbox covers 80% of the image
                yolo_line = f'{class_idx} 0.5 0.5 0.8 0.8\n'

                # FILE OPERATION — writes the YOLO annotation .txt file
                with open(f'{OUT_DIR}/{split}/labels/{cls_name}.txt', 'w') as lf:
                    lf.write(yolo_line)

                # VARIABLE DECLARATION — increments to next class index
                class_idx += 1

# FILE OPERATION — saves classes.txt listing all class names in order
with open(f'{OUT_DIR}/classes.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(class_names))

# VARIABLE DECLARATION — builds the data.yaml dictionary
data_yaml = {
    'path': OUT_DIR,
    'train': 'train/images',
    'val':   'valid/images',
    'nc':    len(class_names),
    'names': class_names
}

# FILE OPERATION — saves data.yaml for YOLO training
with open(f'{OUT_DIR}/data.yaml', 'w') as f:
    yaml.dump(data_yaml, f, allow_unicode=True)

# OUTPUT/PRINT — confirms dataset generation is complete
print(f"Generated {class_idx} syllable classes")
print(f"data.yaml saved with nc={len(class_names)}")
