from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import glob
import json
import os
import re
import shutil
from collections import Counter


IMG_BATCH_ROOT = str(ROOT / 'yolo' / 'images' / 'batches')
LABEL_BATCH_ROOT = str(ROOT / 'yolo' / 'labels' / 'batches')
EXPORT_ARCHIVE_DIR = str(ROOT / 'yolo' / 'labels')
LABEL_STUDIO_HOME = os.getenv('LABEL_STUDIO_HOME', str(ROOT / '.labelstudio_home'))

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


def guess_latest_export():
    patterns = [
        str(ROOT / 'yolo' / 'labels' / 'project-*.json'),
        str(Path(LABEL_STUDIO_HOME) / 'Downloads' / 'project-*.json'),
        str(Path.home() / 'Downloads' / 'project-*.json'),
    ]

    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))

    files = sorted(set(files), key=os.path.getmtime, reverse=True)
    if not files:
        raise FileNotFoundError(
            'cannot find Label Studio export json. '
            'Expected something like project-*.json in '
            f'{Path(LABEL_STUDIO_HOME) / "Downloads"}'
        )
    return files[0]


def build_global_image_map():
    out = {}
    duplicates = []

    for batch_img_dir in sorted(glob.glob(f'{IMG_BATCH_ROOT}/batch_*')):
        batch_name = os.path.basename(batch_img_dir)
        batch_label_dir = f'{LABEL_BATCH_ROOT}/{batch_name}'
        os.makedirs(batch_label_dir, exist_ok=True)

        for path in glob.glob(f'{batch_img_dir}/*.png'):
            base = os.path.basename(path)
            norm = normalize_image_name(base)
            row = {
                'batch_name': batch_name,
                'image_path': path,
                'image_base': base,
                'label_path': f'{batch_label_dir}/{base.replace(".png", ".txt")}',
            }
            if norm in out:
                duplicates.append(norm)
            else:
                out[norm] = row

    return out, duplicates


def summarize_batches():
    rows = []
    for batch_img_dir in sorted(glob.glob(f'{IMG_BATCH_ROOT}/batch_*')):
        batch_name = os.path.basename(batch_img_dir)
        batch_label_dir = f'{LABEL_BATCH_ROOT}/{batch_name}'
        img_files = sorted(glob.glob(f'{batch_img_dir}/*.png'))
        label_files = sorted(glob.glob(f'{batch_label_dir}/*.txt'))
        nonempty = 0
        for path in label_files:
            if os.path.getsize(path) > 0:
                nonempty += 1
        rows.append({
            'batch_name': batch_name,
            'images': len(img_files),
            'labels': len(label_files),
            'nonempty_labels': nonempty,
        })
    return rows


FIN = guess_latest_export()
os.makedirs(EXPORT_ARCHIVE_DIR, exist_ok=True)
ARCHIVE_PATH = str(Path(EXPORT_ARCHIVE_DIR) / os.path.basename(FIN))
if os.path.abspath(FIN) != os.path.abspath(ARCHIVE_PATH):
    shutil.copy2(FIN, ARCHIVE_PATH)

with open(FIN, 'r', encoding='utf-8') as ifile:
    tasks = json.load(ifile)

image_map, duplicates = build_global_image_map()
written = 0
missing = []
unknown_labels = set()
batch_counts = Counter()

for task in tasks:
    image = task.get('data', {}).get('image', '')
    norm_name = normalize_image_name(image)
    row = image_map.get(norm_name)

    if row is None:
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

    with open(row['label_path'], 'w', encoding='utf-8') as ofile:
        ofile.write('\n'.join(lines))
        if lines:
            ofile.write('\n')

    written += 1
    batch_counts[row['batch_name']] += 1

print(f'loaded {len(tasks)} tasks from {FIN}')
print(f'wrote {written} yolo label files across all batches')
print(f'archived export to {ARCHIVE_PATH}')

if batch_counts:
    print('written by batch:')
    for batch_name, count in sorted(batch_counts.items()):
        print(f'  {batch_name}: {count}')

batch_rows = summarize_batches()
if batch_rows:
    print('batch status:')
    for row in batch_rows:
        print(
            f"  {row['batch_name']}: "
            f"{row['nonempty_labels']} labeled / {row['images']} images "
            f"(txt files: {row['labels']})"
        )

if missing:
    print(f'missing images: {len(missing)}')
    for x in missing[:10]:
        print('missing:', x)

if duplicates:
    print(f'duplicate normalized filenames across batches: {len(duplicates)}')
    for x in duplicates[:10]:
        print('duplicate:', x)

if unknown_labels:
    print('unknown labels:', sorted(unknown_labels))
