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
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from tqdm import tqdm

STEP_SEC = 30
SLIDE_DIFF_THRESHOLD = 0.10
SAVE_DEBUG_FRAME = True
WATERMARK_PATTERNS = [
    r'上帝影视',
    r'god\s*\\?$',
    r'上帝影视\s*god\s*\\?$',
]

os.makedirs('ocr/json', exist_ok=True)
os.makedirs('ocr/text', exist_ok=True)
os.makedirs('ocr/debug', exist_ok=True)

ocr = RapidOCR()


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
        '-loglevel', 'error',
        '-ss', str(sec),
        '-i', video_path,
        '-frames:v', '1',
        '-f', 'image2pipe',
        '-vcodec', 'png',
        '-',
    ]
    out = subprocess.check_output(cmd)
    return Image.open(io.BytesIO(out)).convert('RGB')


def image_diff_ratio(img1, img2, size=(96, 96)):
    a = img1.convert('L').resize(size)
    b = img2.convert('L').resize(size)

    pa = list(a.getdata())
    pb = list(b.getdata())

    diff = 0
    for x, y in zip(pa, pb):
        diff += abs(x - y)

    return diff / (255 * len(pa))


def ocr_frame(img):
    arr = np.array(img)
    ret, _ = ocr(arr)

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


def save_debug_pair(dt, sec, prev_frame, frame, diff_ratio, changed):
    if not SAVE_DEBUG_FRAME:
        return

    if prev_frame is None:
        return

    if not changed:
        return

    debug_dir = f'ocr/debug/{dt}'
    os.makedirs(debug_dir, exist_ok=True)

    hhmmss = sec_to_hhmmss(sec).replace(':', '')
    diff_str = 'none' if diff_ratio is None else f'{diff_ratio:.4f}'

    prev_path = f'{debug_dir}/{hhmmss}_prev_diff_{diff_str}.png'
    curr_path = f'{debug_dir}/{hhmmss}_curr_diff_{diff_str}.png'

    prev_frame.save(prev_path)
    frame.save(curr_path)


for video_path in sorted(glob.glob(os.getenv('FOLDER') + '/*')):

    if '【' not in video_path:
        continue

    dt = re.findall(r'【\d+】', video_path)[0]
    FOUT = f'ocr/json/{dt}.json'
    FOUT2 = f'ocr/text/{dt}.txt'

    if os.path.exists(FOUT):
        with open(FOUT, 'r') as ifile:
            head = ifile.read()

        if head:
            continue

    file_start = time.perf_counter()
    print('OCR %s ... this may take a while.' % dt)

    duration = get_duration(video_path)

    samples = []
    prev_frame = None
    prev_text = None

    secs = list(range(0, int(duration) + 1, STEP_SEC))
    for sec in tqdm(secs, desc=dt, unit='frame'):
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
        if prev_frame is None:
            changed = True
        else:
            diff_ratio = image_diff_ratio(prev_frame, frame)
            changed = diff_ratio >= SLIDE_DIFF_THRESHOLD

        row = {
            'sec': sec,
            'hhmmss': sec_to_hhmmss(sec),
            'diff_ratio': diff_ratio,
            'text_raw': '',
            'text_zh': [],
        }

        save_debug_pair(dt, sec, prev_frame, frame, diff_ratio, changed)

        if changed:
            text_raw = ocr_frame(frame)
            text_zh = keep_zh_lines(text_raw)

            if text_zh:
                now_text = '\n'.join(text_zh)
                if now_text != prev_text:
                    row['text_raw'] = text_raw
                    row['text_zh'] = text_zh
                    prev_text = now_text

            samples.append(row)
        prev_frame = frame

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
    print(f'  Finished {video_path} in {file_end - file_start:.2f} seconds.\n')
