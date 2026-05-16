from pathlib import Path
import sys
from collections import Counter
from enum import IntEnum

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
import shutil
import cv2
import numpy as np
import onnxruntime as ort
import multiprocessing as mp
from rapidocr_onnxruntime import RapidOCR
from ultralytics import YOLO
from tqdm import tqdm

STEP_SEC = 30
SLIDE_MATCH_THRESHOLD = 0.80
RESCALED_SLIDE_MATCH_THRESHOLD = 0.33
OCR_CHAR_MATCH_RATIO_THRESHOLD = 0.70
BOX_SCREEN_RATIO_THRESHOLD = (0.5 , 0.62)

HOST_OVERLAY_MAX = 0.20
HOST_IMAGE_RATIO_THRESHOLD = 0.10
SAVE_DEBUG_FRAME = 0
DEBUG = 0

OCR_UPSCALE = 2
OCR_MODEL_DIR = str(ROOT / 'ocr' / 'models')
OCR_DET_MODEL_PATH = f'{OCR_MODEL_DIR}/det.onnx'
OCR_REC_MODEL_PATH = f'{OCR_MODEL_DIR}/rec.onnx'
OCR_REC_KEYS_PATH = f'{OCR_MODEL_DIR}/dict.txt'

YOLO_MODEL_PATH = str(ROOT / 'yolo' / 'weights' / 'current.pt')
YOLO_CONF = 0.1
YOLO_IOU = 0.45
YOLO_DEVICE = 0

WATERMARK_PATTERNS = [
    r'上帝影视',
    r'god\s*\\?$',
    r'上帝影视\s*god\s*\\?$',
]
N_WORKERS = 3
SHOW_FRAME_TQDM = False
VERBOSE = False
MAX_TASKS_PER_CHILD = 1

OCR_JSON_DIR = str(ROOT / 'ocr' / 'json')
OCR_TEXT_DIR = str(ROOT / 'ocr' / 'text')
OCR_DEBUG_DIR = str(ROOT / 'ocr' / 'debug')

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


class CropRescaled(IntEnum):
    NONE = 0
    CLEARER = 1
    BLURRIER = 2


def get_ocr():
    global ocr
    if ocr is None:
        ocr = RapidOCR(**ocr_kwargs)
    return ocr


def get_yolo():
    global yolo
    if yolo is None:
        if not os.path.exists(YOLO_MODEL_PATH):
            raise FileNotFoundError(f'YOLO model not found: {YOLO_MODEL_PATH}')
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


def image_diff_ratio2(img1, img2, center_ratio=0.5):
    a = np.array(img1.convert('L'))
    b = np.array(img2.convert('L'))

    if a.size == 0 or b.size == 0:
        return None

    ah, aw = a.shape[:2]
    bh, bw = b.shape[:2]

    if ah < 4 or aw < 4 or bh < 4 or bw < 4:
        return None

    ch = max(1, int(ah * center_ratio))
    cw = max(1, int(aw * center_ratio))
    y0 = max(0, (ah - ch) // 2)
    x0 = max(0, (aw - cw) // 2)
    tpl = a[y0:y0 + ch, x0:x0 + cw]

    if tpl.size == 0:
        return None

    if bh < ch or bw < cw:
        b = cv2.resize(b, (aw, ah), interpolation=cv2.INTER_LINEAR)
        bh, bw = b.shape[:2]
        if bh < ch or bw < cw:
            return None

    score = cv2.matchTemplate(b, tpl, cv2.TM_CCOEFF_NORMED).max()
    return float(score)


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


def host_image_ratio(host_box, W, H):
    area = W * H
    if area <= 0 or host_box is None:
        return 0.0
    return box_area(host_box) / area


def detect_layout(frame):
    W, H = frame.size
    full_screen_box = (0, 0, W, H)
    arr_rgb = np.array(frame)
    arr_bgr = cv2.cvtColor(arr_rgb, cv2.COLOR_RGB2BGR)

    result = get_yolo().predict(
        source=arr_bgr,
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
    image_ratio = 0.0
    screen_box_ratio = 0.0

    if screen_candidates:
        screen_box = shrink_box(screen_candidates[0]['box'], W, H, ratio=0.02)

    if host_candidates:
        host_box = host_candidates[0]['box']
        image_ratio = host_image_ratio(host_box, W, H)


    if host_box is None:
        screen_box = full_screen_box
        overlay_ratio = 0.0
    if image_ratio < HOST_IMAGE_RATIO_THRESHOLD:
        screen_box = full_screen_box

    if host_box is not None and screen_box is not None:
        overlay_ratio = host_overlay_ratio(screen_box, host_box)

    if screen_box is not None:
        screen_box_ratio = (screen_box[3] - screen_box[1])/(screen_box[2] - screen_box[0])

    return {
        'screen_box': screen_box,
        'host_box': host_box,
        'host_overlay_ratio': overlay_ratio,
        'host_image_ratio': image_ratio,
        'screen_box_ratio': screen_box_ratio,
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


def ocr_char_match_ratio(old_zh, new_zh):
    old_text = ''.join(old_zh)
    new_text = ''.join(new_zh)

    old_counter = Counter(old_text)
    new_counter = Counter(new_text)

    matched = 0
    for ch in old_counter.keys() | new_counter.keys():
        matched += min(old_counter[ch], new_counter[ch])

    new_in_old = 0.0 if len(new_text) == 0 else matched / len(new_text)
    old_in_new = 0.0 if len(old_text) == 0 else matched / len(old_text)

    return {
        'matched': matched,
        'old_text': old_text,
        'new_text': new_text,
        'new_in_old': new_in_old,
        'old_in_new': old_in_new,
    }


def is_fullscreen_box(screen_box, frame_size):
    if screen_box is None or frame_size is None:
        return False
    return tuple(screen_box) == (0, 0, frame_size[0], frame_size[1])


def build_data_entry(row):
    return {
        'hhmmss': row['hhmmss'],
        'sec': row['sec'],
        'text_raw': row['text_raw'],
        'text_zh': list(row['text_zh']),
        'quality_is_fullscreen': row['quality_is_fullscreen'],
    }


def find_matching_data_entry(data, text_zh):
    best_key = None
    best_ratio = None
    best_stats = None

    for key, entry in data.items():
        stats = ocr_char_match_ratio(entry['text_zh'], text_zh)
        ratio = min(stats['new_in_old'], stats['old_in_new'])

        if best_ratio is None or ratio > best_ratio:
            best_key = key
            best_ratio = ratio
            best_stats = stats

    return best_key, best_ratio, best_stats


def find_sample_row(samples, hhmmss):
    for sample in samples:
        if sample.get('hhmmss') == hhmmss:
            return sample
    return None


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

    # prev_frame.save(prev_path) # disable, redundant
    frame.save(curr_path)


def save_debug_crop(dt, sec, crop, replace=False):
    if not SAVE_DEBUG_FRAME:
        return

    debug_dir = str(ROOT / 'ocr' / 'debug' / dt)
    os.makedirs(debug_dir, exist_ok=True)
    hhmmss = sec_to_hhmmss(sec).replace(':', '')
    crop_path = f'{debug_dir}/{hhmmss}_crop{"_r" if replace else ""}.png'
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
    debug_dir = str(ROOT / 'ocr' / 'debug' / dt)

    if not DEBUG and os.path.exists(FOUT) and os.path.getsize(FOUT) > 0:
        return

    # force reset delete entire folder, save debug frame only remove folder at runtime
    if SAVE_DEBUG_FRAME and os.path.isdir(debug_dir):
        shutil.rmtree(debug_dir)

    file_start = time.perf_counter()
    if VERBOSE:
        print('OCR %s ... this may take a while.' % dt)

    duration = get_duration(video_path)

    samples = []
    data = {}
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

        diff_ratio2 = None
        changed = False
        layout = detect_layout(frame)
        screen_box = layout['screen_box']
        host_box = layout['host_box']
        overlay_ratio = layout['host_overlay_ratio']
        image_ratio = layout['host_image_ratio']
        screen_box_ratio = layout['screen_box_ratio']

        crop_rescaled = CropRescaled.NONE
        if prev_frame is None:
            changed = True
        else:

            if prev_screen_box is not None and screen_box is not None:
                prev_crop = crop_by_box(prev_frame, prev_screen_box)
                curr_crop = crop_by_box(frame, screen_box)
                if curr_crop.size == frame.size and prev_crop.size != frame.size:
                    prev_crop =  Image.fromarray(cv2.resize(np.array(prev_crop), frame.size, interpolation=cv2.INTER_LINEAR))
                    crop_rescaled = CropRescaled.CLEARER
                elif curr_crop.size != frame.size and prev_crop.size == frame.size:
                    curr_crop =  Image.fromarray(cv2.resize(np.array(curr_crop), frame.size, interpolation=cv2.INTER_LINEAR))
                    crop_rescaled = CropRescaled.BLURRIER

                diff_ratio2 = image_diff_ratio2(prev_crop, curr_crop)
            else:
                diff_ratio2 = image_diff_ratio2(prev_frame, frame)

            if crop_rescaled != CropRescaled.NONE:
                changed = diff_ratio2 < RESCALED_SLIDE_MATCH_THRESHOLD
            else:
                changed = diff_ratio2 < SLIDE_MATCH_THRESHOLD


        row = {
                'sec': sec,
                'hhmmss': sec_to_hhmmss(sec),
                'diff_ratio2': diff_ratio2,
                'crop_rescaled': int(crop_rescaled),
                'screen_box': screen_box,
                'host_box': host_box,
                'host_overlay_ratio': overlay_ratio,
                'host_image_ratio': image_ratio,
                'screen_box_ratio': screen_box_ratio,
                'remark': '',
                'changed' : changed,
                'frame_size': frame.size,
                'ocr_match_found': False,
                'ocr_match_hhmmss': None,
                'ocr_match_ratio': None,
                'ocr_match_new_in_old': None,
                'ocr_match_old_in_new': None,
                'quality_is_fullscreen': is_fullscreen_box(screen_box, frame.size),
                'replaced_by': None,
                'replaces': None,
        }

        skip_reason = None
        if screen_box is None:
            skip_reason = 'no_screen'
        elif not (BOX_SCREEN_RATIO_THRESHOLD[0] < screen_box_ratio < BOX_SCREEN_RATIO_THRESHOLD[1]):
            skip_reason = 'bad_screen'

        if overlay_ratio >= HOST_OVERLAY_MAX:
            skip_reason = 'host_overlay'

        row['skip_reason'] = skip_reason
        # skip_reason = None
        if skip_reason is None:
            if changed or (crop_rescaled == CropRescaled.CLEARER):
                save_debug_box(dt, sec, frame, layout)
                save_debug_pair(dt, sec, prev_frame, frame, diff_ratio2)
                frame2 = crop_by_box(frame, screen_box)
                save_debug_crop(dt, sec, frame2, not changed)
                text_raw = ocr_frame(frame2)
                text_zh = keep_zh_lines(text_raw)

                if text_zh:
                    now_text = '\n'.join(text_zh)
                    if now_text != prev_text:
                        match_key, match_ratio, match_stats = find_matching_data_entry(data, text_zh)
                        # get best match ratio
                        if match_key is not None and match_stats is not None:
                            row['ocr_match_found'] = True
                            row['ocr_match_hhmmss'] = match_key
                            row['ocr_match_ratio'] = match_ratio
                            row['ocr_match_new_in_old'] = match_stats['new_in_old']
                            row['ocr_match_old_in_new'] = match_stats['old_in_new']

                        # if match ratio > threshold, slide exist previously
                        if (
                            match_key is not None
                            and match_stats is not None
                            and match_ratio is not None
                            and match_ratio >= OCR_CHAR_MATCH_RATIO_THRESHOLD
                        ):
                            old_entry = data[match_key]
                            if row['quality_is_fullscreen'] and not old_entry.get('quality_is_fullscreen'):
                                old_row = find_sample_row(samples, match_key)
                                if old_row is not None:
                                    old_row['remark'] = f'duplicate_replaced_by_{row["hhmmss"]}'
                                    old_row['replaced_by'] = row['hhmmss']
                                row['remark'] = f'duplicate_replacement_of_{match_key}'
                                row['replaces'] = match_key
                                data.pop(match_key, None)
                                row_with_text = dict(row)
                                row_with_text['text_raw'] = text_raw
                                row_with_text['text_zh'] = text_zh
                                data[row['hhmmss']] = build_data_entry(row_with_text)
                                prev_text = now_text
                            else:
                                row['remark'] = f'duplicate_of_{match_key}'
                        else:
                            row_with_text = dict(row)
                            row_with_text['text_raw'] = text_raw
                            row_with_text['text_zh'] = text_zh
                            data[row['hhmmss']] = build_data_entry(row_with_text)
                            prev_text = now_text
            
                prev_frame = frame
                prev_screen_box = screen_box

        samples.append(row)


    with open(FOUT, 'w', encoding='utf-8') as ofile:
        json.dump({
            'video_path': video_path,
            'dt': dt,
            'step_sec': STEP_SEC,
            'ratio': {
                'slide_match_threshold': SLIDE_MATCH_THRESHOLD,
                'rescaled_slide_match_threshold': RESCALED_SLIDE_MATCH_THRESHOLD,
                'ocr_char_match_ratio_threshold': OCR_CHAR_MATCH_RATIO_THRESHOLD,
                'box_screen_ratio_threshold': BOX_SCREEN_RATIO_THRESHOLD,
                'host_overlay_max': HOST_OVERLAY_MAX,
                'host_image_ratio_threshold': HOST_IMAGE_RATIO_THRESHOLD,
            },
            'samples': samples,
            'data': dict(sorted(data.items())),
        }, ofile, ensure_ascii=False, indent=2)

    with open(FOUT2, 'w', encoding='utf-8') as ofile:
        for hhmmss in sorted(data):
            row = data[hhmmss]
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
    DEBUG = 0
    FORCE_RESET = 0

    if FORCE_RESET:
        print('deleing existing ocr outputs ...')
        for folder in [OCR_JSON_DIR, OCR_TEXT_DIR, OCR_DEBUG_DIR]:
            if os.path.isdir(folder):
                shutil.rmtree(folder)


    os.makedirs(OCR_JSON_DIR, exist_ok=True)
    os.makedirs(OCR_TEXT_DIR, exist_ok=True)
    os.makedirs(OCR_DEBUG_DIR, exist_ok=True)
    os.makedirs(OCR_MODEL_DIR, exist_ok=True)

    if DEBUG:
        video_paths = [x for x in video_paths if '20240117' in x]
        SAVE_DEBUG_FRAME =True
        N_WORKERS = 1
        VERBOSE =True
        SHOW_FRAME_TQDM = True
    else:
        filtered_video_paths = []
        for video_path in video_paths:
            dt_match = re.findall(r'【\d+】', video_path)
            if not dt_match:
                continue
            fout = str(ROOT / 'ocr' / 'json' / f'{dt_match[0]}.json')
            if os.path.exists(fout) and os.path.getsize(fout) > 0:
                continue
            filtered_video_paths.append(video_path)
        video_paths = filtered_video_paths

    if N_WORKERS <= 1:
        for video_path in video_paths:
            process_video(video_path)
    else:
        ctx = mp.get_context('spawn')
        with ctx.Pool(N_WORKERS, maxtasksperchild=MAX_TASKS_PER_CHILD) as pool:
            list(tqdm(pool.imap_unordered(process_video, video_paths), total=len(video_paths), desc='videos', unit='video'))
