from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
import glob
import json
import os

from src.llm.mq_iterclass import iter_items_from_files_with_helpers
from src.llm.openai_api import OPENAI_API_DEEPSEEK
from src.transcript.normalize_transcript import NormFinder
from template.template_20260424_2026 import (
    SCHEMA_INSTRUMENT_RULES_EXTRACT as schema,
    TradingInstrument as ts,
)
from tqdm import tqdm


load_dotenv()


TRANSCRIPT_GLOB = 'transcripts/clean/*'
OCR_JSON_FOLDER = 'ocr/json'
MODEL = 'deepseek-v4-flash'
OUTPUT_PREFIX = '2026_04_24_t1'
BATCHES = range(3)

nf = NormFinder('')


def build_apps():
    apps = {}
    for batch in BATCHES:
        apps[batch] = OPENAI_API_DEEPSEEK(
            ts,
            '%s_%s' % (OUTPUT_PREFIX, batch),
            schema,
            model=MODEL,
            temperature=0,
        )
    return apps


def list_batch_dates():
    batch_date = set()
    for f in glob.glob(TRANSCRIPT_GLOB):
        dt = os.path.basename(f)[:7] + '*'
        batch_date.add(dt)
    return sorted(batch_date)


def build_ocr_text(dt: str) -> str:
    ocr_path = os.path.join(OCR_JSON_FOLDER, f'【{dt}】.json')
    if not os.path.exists(ocr_path):
        return ''

    try:
        with open(ocr_path, 'r', encoding='utf-8') as ifile:
            payload = json.load(ifile)
    except Exception:
        return ''

    sorted_items = sorted(payload["data"].items(), key=lambda x: x[0])

    snippets = []
    for _, entry in sorted_items:
        text_raw = entry.get('text_zh', [])
        if text_raw:
            snippets.append(''.join(text_raw))

    return nf.normalize_zh_transcript('\n\n'.join(snippets).strip())


def build_helper(dt: str):
    helper = {}
    ocr_text = build_ocr_text(dt)
    if ocr_text:
        helper['ocr_text'] = ocr_text
    return json.dumps(helper, ensure_ascii=False)


def run(batch_dates=None):
    apps = build_apps()
    errlist = []

    if batch_dates is None:
        batch_dates = list_batch_dates()

    pbar = tqdm(batch_dates, desc='extract instrument', unit='day')
    for dt in pbar:
        files = []
        files.extend(glob.glob(f'transcripts/clean/{dt}.txt'))
        if not files:
            continue
        files = sorted(files)
        helpers = []
        for transcript_file in files:
            dt2 = os.path.basename(transcript_file).split('.')[0]
            helpers.append(build_helper(dt2))

        for batch, app in apps.items():
            try:
                pbar.set_postfix(dt=dt, batch=batch, files=len(files))
                app.run_batch_multiprocess(
                    iter_items_from_files_with_helpers(files, helpers=helpers),
                    show_progress=False,
                )
            except Exception as e:
                # pbar.write('error %s %s %s' % (dt, batch, e))
                errlist.append((dt, batch, str(e)))

    return errlist


if __name__ == '__main__':
    run(['20260402'])
