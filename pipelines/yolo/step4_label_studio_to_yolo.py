from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import glob
import json
import os
import re


FIN = str(ROOT / 'yolo' / 'labels' / 'project-1-at-2026-05-13-11-57-c79120dd.json')
IMG_DIR = str(ROOT / 'yolo' / 'images' / 'train_label')
LABEL_DIR = str(ROOT / 'yolo' / 'labels' / 'train_label')

LABEL_MAP = {
    'screen': 0,
    'host': 1,
    'welcome_screen': 2,
}


def normalize_image_name(name):
    name = os.path.basename(name)
    name = re.sub(r'^[0-9a-f]+-', '', name)
    name = name.replace('【', '').replace('】', '')
    return name


def get_image_map():
    out = {}
    for path in glob.glob(f'{IMG_DIR}/*.png'):
        base = os.path.basename(path)
        out[normalize_image_name(base)] = base
    return out


def get_yolo_line(value, class_id):
    x = float(value['x'])
    y = float(value['y'])
    w = float(value['width'])
    h = float(value['height'])

    x_center = (x + w / 2.0) / 100.0
    y_center = (y + h / 2.0) / 100.0
    w = w / 100.0
    h = h / 100.0

    return f'{class_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}'


os.makedirs(LABEL_DIR, exist_ok=True)

with open(FIN, 'r', encoding='utf-8') as ifile:
    tasks = json.load(ifile)

image_map = get_image_map()
written = 0
missing = []
unknown_labels = set()

for task in tasks:
    image = task.get('data', {}).get('image', '')
    norm_name = normalize_image_name(image)
    real_name = image_map.get(norm_name)

    if real_name is None:
        missing.append(norm_name)
        continue

    lines = []
    for ann in task.get('annotations', []):
        for result in ann.get('result', []):
            if result.get('type') != 'rectanglelabels':
                continue

            value = result.get('value', {})
            labels = value.get('rectanglelabels', [])
            if not labels:
                continue

            label = labels[0]
            class_id = LABEL_MAP.get(label)
            if class_id is None:
                unknown_labels.add(label)
                continue

            lines.append(get_yolo_line(value, class_id))

    fout = f'{LABEL_DIR}/{real_name.replace(".png", ".txt")}'
    with open(fout, 'w', encoding='utf-8') as ofile:
        ofile.write('\n'.join(lines))
        if lines:
            ofile.write('\n')

    written += 1

print(f'loaded {len(tasks)} tasks from {FIN}')
print(f'wrote {written} yolo label files into {LABEL_DIR}')

if missing:
    print(f'missing images: {len(missing)}')
    for x in missing[:10]:
        print('missing:', x)

if unknown_labels:
    print('unknown labels:', sorted(unknown_labels))
