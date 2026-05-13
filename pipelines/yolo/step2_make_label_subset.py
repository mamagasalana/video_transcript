from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import glob
import os
import random
import re
import shutil


SEED = 1234
N_IMAGES = 75

SRC_IMG_DIR = str(ROOT / 'yolo' / 'images' / 'train')
SRC_LABEL_DIR = str(ROOT / 'yolo' / 'labels' / 'train')
BATCH_IMG_ROOT = str(ROOT / 'yolo' / 'images' / 'batches')
BATCH_LABEL_ROOT = str(ROOT / 'yolo' / 'labels' / 'batches')

random.seed(SEED)


def list_existing_batches():
    paths = sorted(glob.glob(f'{BATCH_IMG_ROOT}/batch_*'))
    return [p for p in paths if os.path.isdir(p)]


def next_batch_name():
    existing = list_existing_batches()
    if not existing:
        return 'batch_001'

    nums = []
    for path in existing:
        m = re.search(r'batch_(\d+)$', os.path.basename(path))
        if m:
            nums.append(int(m.group(1)))

    nxt = 1 if not nums else max(nums) + 1
    return f'batch_{nxt:03d}'


def get_used_basenames():
    used = set()
    for batch_dir in list_existing_batches():
        for path in glob.glob(f'{batch_dir}/*.png'):
            used.add(os.path.basename(path))
    return used


os.makedirs(BATCH_IMG_ROOT, exist_ok=True)
os.makedirs(BATCH_LABEL_ROOT, exist_ok=True)

batch_name = next_batch_name()
DST_IMG_DIR = f'{BATCH_IMG_ROOT}/{batch_name}'
DST_LABEL_DIR = f'{BATCH_LABEL_ROOT}/{batch_name}'
os.makedirs(DST_IMG_DIR, exist_ok=True)
os.makedirs(DST_LABEL_DIR, exist_ok=True)

used_basenames = get_used_basenames()
all_images_all = sorted(glob.glob(f'{SRC_IMG_DIR}/*.png'))
all_images = [x for x in all_images_all if os.path.basename(x) not in used_basenames]
random.shuffle(all_images)
picked = all_images[:N_IMAGES]

print(f'existing used images: {len(used_basenames)} / total candidates: {len(all_images_all)}')
print(f'available new images: {len(all_images)}')

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

print(f'created {batch_name}')
print(f'copied {len(picked)} images to {DST_IMG_DIR}')
