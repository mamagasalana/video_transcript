from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from PIL import Image
import glob
import json
import os
import re
import subprocess
import time
import io
import cv2
import numpy as np
import onnxruntime as ort
import multiprocessing as mp
from rapidocr_onnxruntime import RapidOCR
from tqdm import tqdm

STEP_SEC = 30
SLIDE_DIFF_THRESHOLD = 0.10
SAVE_DEBUG_FRAME = True
OCR_UPSCALE = 2
OCR_MODEL_DIR = 'ocr/models'
OCR_DET_MODEL_PATH = f'{OCR_MODEL_DIR}/det.onnx'
OCR_REC_MODEL_PATH = f'{OCR_MODEL_DIR}/rec.onnx'
OCR_REC_KEYS_PATH = f'{OCR_MODEL_DIR}/dict.txt'
WATERMARK_PATTERNS = [
    r'上帝影视',
    r'god\s*\\?$',
    r'上帝影视\s*god\s*\\?$',
]
FORCE_RESET=1
N_WORKERS = 5
SHOW_FRAME_TQDM = False
VERBOSE = False
MAX_TASKS_PER_CHILD = 1

os.makedirs('ocr/json', exist_ok=True)
os.makedirs('ocr/text', exist_ok=True)
os.makedirs('ocr/debug', exist_ok=True)
os.makedirs(OCR_MODEL_DIR, exist_ok=True)

providers = ort.get_available_providers()
USE_CUDA = 'CUDAExecutionProvider' in providers

ocr_kwargs = {
    'det_use_cuda': USE_CUDA,
    'cls_use_cuda': USE_CUDA,
    'rec_use_cuda': USE_CUDA,
}

if os.path.exists(OCR_DET_MODEL_PATH):
    ocr_kwargs['det_model_path'] = OCR_DET_MODEL_PATH

if os.path.exists(OCR_REC_MODEL_PATH):
    ocr_kwargs['rec_model_path'] = OCR_REC_MODEL_PATH

if os.path.exists(OCR_REC_KEYS_PATH):
    ocr_kwargs['rec_keys_path'] = OCR_REC_KEYS_PATH

ocr = None


def get_ocr():
    global ocr
    if ocr is None:
        if VERBOSE:
            print('init ocr in pid', os.getpid())
        ocr = RapidOCR(**ocr_kwargs)
    return ocr


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


def sec_to_hhmmss(sec):
    sec = int(sec)
    hh = sec // 3600
    mm = (sec % 3600) // 60
    ss = sec % 60
    return f'{hh:02d}:{mm:02d}:{ss:02d}'


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
        try:
            return Image.open(io.BytesIO(ret.stdout)).convert('RGB')
        except Exception:
            pass

    err = ret.stderr.decode(errors='ignore').strip()
    raise RuntimeError(err or f'ffmpeg failed for {video_path} @ {sec}s')


def image_diff_ratio(img1, img2, size=(96, 96)):
    a = img1.convert('L').resize(size)
    b = img2.convert('L').resize(size)

    pa = list(a.getdata())
    pb = list(b.getdata())

    diff = 0
    for x, y in zip(pa, pb):
        diff += abs(x - y)

    return diff / (255 * len(pa))


def detect_screen_box(img):
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    H, W = gray.shape[:2]
    best = None
    best_score = -1

    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        if len(approx) < 4 or len(approx) > 6:
            continue

        x, y, w, h = cv2.boundingRect(approx)
        area = w * h
        if area < W * H * 0.04:
            continue

        ratio = w / max(h, 1)
        if ratio < 0.9 or ratio > 3.2:
            continue

        if y > H * 0.82:
            continue

        cx = x + w / 2
        if cx < W * 0.35:
            continue

        score = area
        if score > best_score:
            best_score = score
            best = (x, y, w, h)

    if best is None:
        return None

    x, y, w, h = best
    pad_x = int(w * 0.02)
    pad_y = int(h * 0.02)

    x0 = max(0, x + pad_x)
    y0 = max(0, y + pad_y)
    x1 = min(W, x + w - pad_x)
    y1 = min(H, y + h - pad_y)

    if x1 <= x0 or y1 <= y0:
        return None

    return (x0, y0, x1, y1)


def ocr_frame(img):
    if OCR_UPSCALE > 1:
        img = img.resize(
            (img.width * OCR_UPSCALE, img.height * OCR_UPSCALE),
            Image.Resampling.LANCZOS,
        )

    arr = np.array(img)
    ret, _ = get_ocr()(arr)

    if not ret:
        return ''

    lines = []
    for row in ret:
        if not row or len(row) < 3:
            continue
        txt = str(row[1]).strip()
        if not txt:
            continue
        lines.append(txt)

    return '\n'.join(lines).strip()


def keep_zh_lines(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        bad = False
        for pat in WATERMARK_PATTERNS:
            if re.search(pat, line, flags=re.I):
                bad = True
                break
        if bad:
            continue
        if re.search(r'[\u3400-\u4dbf\u4e00-\u9fff]', line):
            out.append(line)
    return out


def save_debug_pair(dt, sec, prev_frame, frame, diff_ratio):
    if not SAVE_DEBUG_FRAME:
        return

    if prev_frame is None:
        return

    debug_dir = f'ocr/debug/{dt}'
    os.makedirs(debug_dir, exist_ok=True)

    hhmmss = sec_to_hhmmss(sec).replace(':', '')
    diff_str = 'none' if diff_ratio is None else f'{diff_ratio:.4f}'

    prev_path = f'{debug_dir}/{hhmmss}_prev_diff_{diff_str}.png'
    curr_path = f'{debug_dir}/{hhmmss}_curr_diff_{diff_str}.png'

    prev_frame.save(prev_path) # disable, redundant
    frame.save(curr_path)


def save_debug_crop(dt, sec, crop):
    if not SAVE_DEBUG_FRAME:
        return

    debug_dir = f'ocr/debug/{dt}'
    os.makedirs(debug_dir, exist_ok=True)
    hhmmss = sec_to_hhmmss(sec).replace(':', '')
    crop_path = f'{debug_dir}/{hhmmss}_crop.png'
    crop.save(crop_path)


def crop_by_box(img, box):
    x0, y0, x1, y1 = box
    return img.crop((x0, y0, x1, y1))


def save_debug_box(dt, sec, frame, box):
    if not SAVE_DEBUG_FRAME:
        return

    debug_dir = f'ocr/debug/{dt}'
    os.makedirs(debug_dir, exist_ok=True)
    hhmmss = sec_to_hhmmss(sec).replace(':', '')
    box_path = f'{debug_dir}/{hhmmss}_box.png'

    arr = np.array(frame).copy()
    if box is not None:
        x0, y0, x1, y1 = box
        cv2.rectangle(arr, (x0, y0), (x1, y1), (255, 0, 0), 4)
    Image.fromarray(arr).save(box_path)


def process_video(video_path):

    if '【' not in video_path:
        return

    dt = re.findall(r'【\d+】', video_path)[0]
    FOUT = f'ocr/json/{dt}.json'
    FOUT2 = f'ocr/text/{dt}.txt'

    if os.path.exists(FOUT) and not FORCE_RESET:
        with open(FOUT, 'r') as ifile:
            head = ifile.read()

        if head:
            return

    file_start = time.perf_counter()
    if VERBOSE:
        print('OCR %s ... this may take a while.' % dt)

    duration = get_duration(video_path)

    samples = []
    prev_frame = None
    prev_box = None
    prev_text = None

    secs = list(range(0, int(duration) + 1, STEP_SEC))
    sec_iter = secs if not SHOW_FRAME_TQDM else tqdm(secs, desc=dt, unit='frame')
    for sec in sec_iter:
        try:
            frame = extract_frame(video_path, sec)
        except Exception as e:
            samples.append({
                'sec': sec,
                'hhmmss': sec_to_hhmmss(sec),
                'error': str(e),
            })
            continue

        diff_ratio = None
        changed = False
        screen_box = detect_screen_box(frame)
        if prev_frame is None:
            changed = True
        else:
            if prev_box is not None and screen_box is not None:
                prev_crop = crop_by_box(prev_frame, prev_box)
                curr_crop = crop_by_box(frame, screen_box)
                diff_ratio = image_diff_ratio(prev_crop, curr_crop)
            else:
                diff_ratio = image_diff_ratio(prev_frame, frame)
            changed = diff_ratio >= SLIDE_DIFF_THRESHOLD


        # save_debug_pair(dt, sec, prev_frame, frame, diff_ratio)
        if changed:

            row = {
                'sec': sec,
                'hhmmss': sec_to_hhmmss(sec),
                'diff_ratio': diff_ratio,
                'text_raw': '',
                'text_zh': [],
            }


            save_debug_box(dt, sec, frame, screen_box)
            save_debug_pair(dt, sec, prev_frame, frame, diff_ratio)
            if screen_box is not None:
                frame2 = crop_by_box(frame, screen_box)
                save_debug_crop(dt, sec, frame2)
            else:
                frame2 = frame

            text_raw = ocr_frame(frame2)
            text_zh = keep_zh_lines(text_raw)

            if text_zh:
                now_text = '\n'.join(text_zh)
                if now_text != prev_text:
                    row['text_raw'] = text_raw
                    row['text_zh'] = text_zh
                    prev_text = now_text

            samples.append(row)
        prev_frame = frame
        prev_box = screen_box

    with open(FOUT, 'w', encoding='utf-8') as ofile:
        json.dump({
            'video_path': video_path,
            'dt': dt,
            'step_sec': STEP_SEC,
            'slide_diff_threshold': SLIDE_DIFF_THRESHOLD,
            'samples': samples,
        }, ofile, ensure_ascii=False, indent=2)

    with open(FOUT2, 'w', encoding='utf-8') as ofile:
        for row in samples:
            if not row.get('text_zh'):
                continue
            ofile.write('[%s]\n' % row['hhmmss'])
            for line in row['text_zh']:
                ofile.write(line + '\n')
            ofile.write('\n')

    file_end = time.perf_counter()
    if VERBOSE:
        print(f'  Finished {video_path} in {file_end - file_start:.2f} seconds.\n')


if __name__ == '__main__':
    video_paths = sorted(glob.glob(os.getenv('FOLDER') + '/*'))
    video_paths = [x for x in video_paths if '【' in x]

    print('RapidOCR providers:', providers)
    print('RapidOCR use cuda:', USE_CUDA)

    N_WORKERS = 1
    video_paths = [x for x in video_paths if '20200721' in x]
    if N_WORKERS <= 1:
        for video_path in video_paths:
            process_video(video_path)
    else:
        ctx = mp.get_context('spawn')
        with ctx.Pool(N_WORKERS, maxtasksperchild=MAX_TASKS_PER_CHILD) as pool:
            list(tqdm(pool.imap_unordered(process_video, video_paths), total=len(video_paths), desc='videos', unit='video'))
