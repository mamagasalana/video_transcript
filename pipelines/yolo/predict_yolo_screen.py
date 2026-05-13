from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultralytics import YOLO
import glob
import os


MODEL = 'yolo/runs/screen_label_subset/weights/best.pt'
SOURCE = 'yolo/images/train_label'
PROJECT = 'yolo/runs_predict'
NAME = 'screen_label_subset'
DEVICE = 0
CONF = 0.25
MAX_IMAGES = 30


all_images = sorted(glob.glob(f'{SOURCE}/*.png'))
images = all_images[:MAX_IMAGES]

if not images:
    raise RuntimeError(f'no images found in {SOURCE}')

if not os.path.exists(MODEL):
    raise FileNotFoundError(f'model not found: {MODEL}')

os.makedirs(PROJECT, exist_ok=True)

model = YOLO(MODEL)
model.predict(
    source=images,
    conf=CONF,
    device=DEVICE,
    project=PROJECT,
    name=NAME,
    save=True,
)
