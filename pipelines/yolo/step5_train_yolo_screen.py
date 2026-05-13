from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultralytics import YOLO
import os
import glob
import shutil


MODEL = str(ROOT / 'yolov8n.pt')
DATA = str(ROOT / 'yolo' / 'dataset_train_label.yaml')
IMGSZ = 1280
EPOCHS = 100
BATCH = 8
PROJECT = str(ROOT / 'yolo' / 'runs')
NAME = 'screen_label_subset'
DEVICE = 0
WORKERS = 4
BATCH_IMG_ROOT = str(ROOT / 'yolo' / 'images' / 'batches')
BATCH_LABEL_ROOT = str(ROOT / 'yolo' / 'labels' / 'batches')
MERGED_IMG_DIR = str(ROOT / 'yolo' / 'images' / 'train_label')
MERGED_LABEL_DIR = str(ROOT / 'yolo' / 'labels' / 'train_label')


def rebuild_merged_train_label():
    if os.path.isdir(MERGED_IMG_DIR):
        shutil.rmtree(MERGED_IMG_DIR)
    if os.path.isdir(MERGED_LABEL_DIR):
        shutil.rmtree(MERGED_LABEL_DIR)

    os.makedirs(MERGED_IMG_DIR, exist_ok=True)
    os.makedirs(MERGED_LABEL_DIR, exist_ok=True)

    count = 0
    for batch_img_dir in sorted(glob.glob(f'{BATCH_IMG_ROOT}/batch_*')):
        batch_name = os.path.basename(batch_img_dir)
        batch_label_dir = f'{BATCH_LABEL_ROOT}/{batch_name}'
        for src_img in sorted(glob.glob(f'{batch_img_dir}/*.png')):
            base = os.path.basename(src_img)
            src_label = f'{batch_label_dir}/{base.replace(".png", ".txt")}'
            dst_img = f'{MERGED_IMG_DIR}/{base}'
            dst_label = f'{MERGED_LABEL_DIR}/{base.replace(".png", ".txt")}'
            shutil.copy2(src_img, dst_img)
            if os.path.exists(src_label):
                shutil.copy2(src_label, dst_label)
            else:
                with open(dst_label, 'w') as ofile:
                    ofile.write('')
            count += 1

    print(f'merged {count} labeled images into {MERGED_IMG_DIR}')


os.makedirs(PROJECT, exist_ok=True)
rebuild_merged_train_label()

model = YOLO(MODEL)
model.train(
    data=DATA,
    imgsz=IMGSZ,
    epochs=EPOCHS,
    batch=BATCH,
    project=PROJECT,
    name=NAME,
    device=DEVICE,
    workers=WORKERS,
)
