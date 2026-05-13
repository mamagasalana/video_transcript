from dotenv import load_dotenv

load_dotenv()
from tqdm import tqdm
from PIL import Image
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import glob
import os
import re
import subprocess
import io
import random


STEP_SEC = 60
MAX_PER_VIDEO = 6
VAL_RATIO = 0.2
SEED = 1234

IMAGE_ROOT = 'yolo/images'
TRAIN_DIR = f'{IMAGE_ROOT}/train'
VAL_DIR = f'{IMAGE_ROOT}/val'
LABEL_ROOT = 'yolo/labels'
LABEL_TRAIN_DIR = f'{LABEL_ROOT}/train'
LABEL_VAL_DIR = f'{LABEL_ROOT}/val'

os.makedirs(TRAIN_DIR, exist_ok=True)
os.makedirs(VAL_DIR, exist_ok=True)
os.makedirs(LABEL_TRAIN_DIR, exist_ok=True)
os.makedirs(LABEL_VAL_DIR, exist_ok=True)

random.seed(SEED)


def get_duration(video_path):
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path,
    ]
    out = subprocess.check_output(cmd).decode().strip()
    return float(out)


def extract_frame(video_path, sec):
    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-nostdin',
        '-loglevel', 'error',
        '-ss', str(sec),
        '-i', video_path,
        '-frames:v', '1',
        '-f', 'image2pipe',
        '-vcodec', 'png',
        '-',
    ]
    ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if ret.stdout:
        return Image.open(io.BytesIO(ret.stdout)).convert('RGB')

    err = ret.stderr.decode(errors='ignore').strip()
    raise RuntimeError(err or f'ffmpeg failed for {video_path} @ {sec}s')


def choose_secs(duration):
    secs = list(range(0, int(duration) + 1, STEP_SEC))
    if len(secs) <= MAX_PER_VIDEO:
        return secs

    out = []
    if MAX_PER_VIDEO == 1:
        return [secs[len(secs) // 2]]

    for i in range(MAX_PER_VIDEO):
        idx = round(i * (len(secs) - 1) / (MAX_PER_VIDEO - 1))
        out.append(secs[idx])
    return sorted(set(out))


def sec_to_tag(sec):
    sec = int(sec)
    hh = sec // 3600
    mm = (sec % 3600) // 60
    ss = sec % 60
    return f'{hh:02d}{mm:02d}{ss:02d}'


video_paths = sorted(glob.glob(os.getenv('FOLDER') + '/*'))
video_paths = [x for x in video_paths if '【' in x]

TOTAL_MAX = 300
all_items = []
for video_path in tqdm(video_paths[:TOTAL_MAX]):
    dt = re.findall(r'【\d+】', video_path)[0]
    duration = get_duration(video_path)
    for sec in choose_secs(duration):
        all_items.append((video_path, dt, sec))

random.shuffle(all_items)

n_val = int(len(all_items) * VAL_RATIO)
val_keys = set((x[1], x[2]) for x in all_items[:n_val])


for video_path, dt, sec in tqdm(all_items):
    tag = sec_to_tag(sec)
    fname = f'{dt}_{tag}.png'
    is_val = (dt, sec) in val_keys
    out_dir = VAL_DIR if is_val else TRAIN_DIR
    label_dir = LABEL_VAL_DIR if is_val else LABEL_TRAIN_DIR

    out_path = f'{out_dir}/{fname}'
    label_path = f'{label_dir}/{fname.replace(".png", ".txt")}'

    if os.path.exists(out_path):
        continue

    img = extract_frame(video_path, sec)
    img.save(out_path)

    if not os.path.exists(label_path):
        with open(label_path, 'w') as ofile:
            ofile.write('')
