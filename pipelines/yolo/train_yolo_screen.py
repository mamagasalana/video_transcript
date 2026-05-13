from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultralytics import YOLO
import os


MODEL = 'yolov8n.pt'
DATA = 'yolo/dataset_train_label.yaml'
IMGSZ = 1280
EPOCHS = 100
BATCH = 8
PROJECT = 'yolo/runs'
NAME = 'screen_label_subset'
DEVICE = 0
WORKERS = 4

os.makedirs(PROJECT, exist_ok=True)

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
