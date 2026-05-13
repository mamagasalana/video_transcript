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
from ultralytics import YOLO
from tqdm import tqdm

STEP_SEC = 30
SLIDE_DIFF_THRESHOLD = 0.10
SAVE_DEBUG_FRAME = True
OCR_UPSCALE = 2
OCR_MODEL_DIR = str(ROOT / 'ocr' / 'models')
OCR_DET_MODEL_PATH = f'{OCR_MODEL_DIR}/det.onnx'
OCR_REC_MODEL_PATH = f'{OCR_MODEL_DIR}/rec.onnx'
OCR_REC_KEYS_PATH = f'{OCR_MODEL_DIR}/dict.txt'
YOLO_MODEL_PATH = str(ROOT / 'yolo' / 'runs' / 'screen_label_subset' / 'weights' / 'best.pt')
YOLO_CONF = 0.25
YOLO_IOU = 0.45
HOST_OVERLAY_MAX = 0.20
YOLO_DEVICE = 0
WATERMARK_PATTERNS = [
    r'上帝影视',
    r'god\s*\\?$',
    r'上帝影视\s*god\s*\\?$',
]
FORCE_RESET = 1
N_WORKERS = 3
SHOW_FRAME_TQDM = False
VERBOSE = False
MAX_TASKS_PER_CHILD = 1

os.makedirs(str(ROOT / 'ocr' / 'json'), exist_ok=True)
os.makedirs(str(ROOT / 'ocr' / 'text'), exist_ok=True)
os.makedirs(str(ROOT / 'ocr' / 'debug'), exist_ok=True)
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
yolo = None


def get_ocr():
    global ocr
    if ocr is None:
        if VERBOSE:
            print('init ocr in pid', os.getpid())
        ocr = RapidOCR(**ocr_kwargs)
    return ocr


def get_yolo():
    global yolo
    if yolo is None:
        if not os.path.exists(YOLO_MODEL_PATH):
            raise FileNotFoundError(f'YOLO model not found: {YOLO_MODEL_PATH}')
        if VERBOSE:
            print('init yolo in pid', os.getpid())
        yolo = YOLO(YOLO_MODEL_PATH)
    return yolo


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


def normalize_box(x0, y0, x1, y1, W, H):
    x0 = max(0, min(int(round(x0)), W))
    y0 = max(0, min(int(round(y0)), H))
    x1 = max(0, min(int(round(x1)), W))
    y1 = max(0, min(int(round(y1)), H))
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def shrink_box(box, W, H, ratio=0.02):
    if box is None:
        return None
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    pad_x = int(w * ratio)
    pad_y = int(h * ratio)
    return normalize_box(x0 + pad_x, y0 + pad_y, x1 - pad_x, y1 - pad_y, W, H)


def box_area(box):
    if box is None:
        return 0
    x0, y0, x1, y1 = box
    return max(0, x1 - x0) * max(0, y1 - y0)


def box_intersection(box1, box2):
    if box1 is None or box2 is None:
        return 0
    ax0, ay0, ax1, ay1 = box1
    bx0, by0, bx1, by1 = box2
    x0 = max(ax0, bx0)
    y0 = max(ay0, by0)
    x1 = min(ax1, bx1)
    y1 = min(ay1, by1)
    if x1 <= x0 or y1 <= y0:
        return 0
    return (x1 - x0) * (y1 - y0)


def host_overlay_ratio(screen_box, host_box):
    area = box_area(screen_box)
    if area <= 0:
        return 0.0
    return box_intersection(screen_box, host_box) / area


def detect_layout(frame):
    arr = np.array(frame)
    H, W = arr.shape[:2]
    full_screen_box = (0, 0, W, H)

    result = get_yolo().predict(
        source=arr,
        conf=YOLO_CONF,
        iou=YOLO_IOU,
        device=YOLO_DEVICE,
        verbose=False,
    )[0]

    names = result.names
    screen_candidates = []
    host_candidates = []

    boxes = result.boxes
    if boxes is not None:
        xyxy = boxes.xyxy.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        conf = boxes.conf.cpu().numpy()

        for box_xyxy, cls_id, score in zip(xyxy, cls, conf):
            label = names[int(cls_id)]
            box = normalize_box(
                box_xyxy[0], box_xyxy[1], box_xyxy[2], box_xyxy[3], W, H
            )
            if box is None:
                continue

            row = {
                'label': label,
                'box': box,
                'score': float(score),
            }
            if label == 'screen':
                screen_candidates.append(row)
            elif label == 'host':
                host_candidates.append(row)

    screen_candidates = sorted(screen_candidates, key=lambda x: (box_area(x['box']), x['score']), reverse=True)
    host_candidates = sorted(host_candidates, key=lambda x: (box_area(x['box']), x['score']), reverse=True)

    screen_box = None
    host_box = None
    overlay_ratio = 0.0

    if screen_candidates:
        screen_box = shrink_box(screen_candidates[0]['box'], W, H, ratio=0.02)

    if screen_box is not None:
        best_host = None
        best_overlay = 0.0
        for row in host_candidates:
            overlay = host_overlay_ratio(screen_box, row['box'])
            if overlay > best_overlay:
                best_overlay = overlay
                best_host = row['box']
        host_box = best_host
        overlay_ratio = best_overlay

    if host_box is None:
        screen_box = full_screen_box
        overlay_ratio = 0.0

    return {
        'screen_box': screen_box,
        'host_box': host_box,
        'host_overlay_ratio': overlay_ratio,
    }


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

    debug_dir = str(ROOT / 'ocr' / 'debug' / dt)
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

    debug_dir = str(ROOT / 'ocr' / 'debug' / dt)
    os.makedirs(debug_dir, exist_ok=True)
    hhmmss = sec_to_hhmmss(sec).replace(':', '')
    crop_path = f'{debug_dir}/{hhmmss}_crop.png'
    crop.save(crop_path)


def crop_by_box(img, box):
    x0, y0, x1, y1 = box
    return img.crop((x0, y0, x1, y1))


def save_debug_box(dt, sec, frame, layout):
    if not SAVE_DEBUG_FRAME:
        return

    debug_dir = str(ROOT / 'ocr' / 'debug' / dt)
    os.makedirs(debug_dir, exist_ok=True)
    hhmmss = sec_to_hhmmss(sec).replace(':', '')
    box_path = f'{debug_dir}/{hhmmss}_box.png'

    arr = np.array(frame).copy()
    screen_box = layout.get('screen_box')
    host_box = layout.get('host_box')
    overlay_ratio = layout.get('host_overlay_ratio', 0.0)

    if screen_box is not None:
        x0, y0, x1, y1 = screen_box
        cv2.rectangle(arr, (x0, y0), (x1, y1), (255, 0, 0), 4)
        cv2.putText(arr, 'screen', (x0, max(30, y0 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)
    if host_box is not None:
        x0, y0, x1, y1 = host_box
        cv2.rectangle(arr, (x0, y0), (x1, y1), (0, 0, 255), 4)
        cv2.putText(arr, f'host {overlay_ratio:.2f}', (x0, max(30, y0 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
    Image.fromarray(arr).save(box_path)


def process_video(video_path):

    if '【' not in video_path:
        return

    dt = re.findall(r'【\d+】', video_path)[0]
    FOUT = str(ROOT / 'ocr' / 'json' / f'{dt}.json')
    FOUT2 = str(ROOT / 'ocr' / 'text' / f'{dt}.txt')

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
    prev_screen_box = None
    prev_text = None

    secs = list(range(STEP_SEC, int(duration) + 1, STEP_SEC))
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
        layout = detect_layout(frame)
        screen_box = layout['screen_box']
        host_box = layout['host_box']
        overlay_ratio = layout['host_overlay_ratio']
        if prev_frame is None:
            changed = True
        else:
            if prev_screen_box is not None and screen_box is not None:
                prev_crop = crop_by_box(prev_frame, prev_screen_box)
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
                'screen_box': screen_box,
                'host_box': host_box,
                'host_overlay_ratio': overlay_ratio,
                'text_raw': '',
                'text_zh': [],
            }


            save_debug_box(dt, sec, frame, layout)
            save_debug_pair(dt, sec, prev_frame, frame, diff_ratio)
            skip_reason = None

            if screen_box is None and host_box is not None:
                skip_reason = 'no_screen'
            elif host_box is not None and overlay_ratio >= HOST_OVERLAY_MAX:
                skip_reason = 'host_overlay'

            row['skip_reason'] = skip_reason

            if skip_reason is None and screen_box is not None:
                frame2 = crop_by_box(frame, screen_box)
                save_debug_crop(dt, sec, frame2)
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
        prev_screen_box = screen_box

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
    if N_WORKERS <= 1:
        for video_path in video_paths:
            process_video(video_path)
    else:
        ctx = mp.get_context('spawn')
        with ctx.Pool(N_WORKERS, maxtasksperchild=MAX_TASKS_PER_CHILD) as pool:
            list(tqdm(pool.imap_unordered(process_video, video_paths), total=len(video_paths), desc='videos', unit='video'))
