from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import glob
import os
import random
import shutil


SEED = 1234
N_IMAGES = 75

SRC_IMG_DIR = 'yolo/images/train'
SRC_LABEL_DIR = 'yolo/labels/train'

DST_IMG_DIR = 'yolo/images/train_label'
DST_LABEL_DIR = 'yolo/labels/train_label'

if os.path.isdir(DST_IMG_DIR):
    shutil.rmtree(DST_IMG_DIR)
if os.path.isdir(DST_LABEL_DIR):
    shutil.rmtree(DST_LABEL_DIR)

os.makedirs(DST_IMG_DIR, exist_ok=True)
os.makedirs(DST_LABEL_DIR, exist_ok=True)

random.seed(SEED)

all_images = sorted(glob.glob(f'{SRC_IMG_DIR}/*.png'))
random.shuffle(all_images)
picked = all_images[:N_IMAGES]

for path in picked:
    base = os.path.basename(path)
    dst_img = f'{DST_IMG_DIR}/{base}'
    dst_label = f'{DST_LABEL_DIR}/{base.replace(".png", ".txt")}'

    shutil.copy2(path, dst_img)

    src_label = f'{SRC_LABEL_DIR}/{base.replace(".png", ".txt")}'
    if os.path.exists(src_label):
        shutil.copy2(src_label, dst_label)
    else:
        with open(dst_label, 'w') as ofile:
            ofile.write('')

print(f'copied {len(picked)} images to {DST_IMG_DIR}')
