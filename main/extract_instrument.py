from dotenv import load_dotenv
import glob
import os

from src.mq_iterclass import iter_items_from_files
from src.openai_api import OPENAI_API_DEEPSEEK
from template.template_20260424_2026 import (
    SCHEMA_INSTRUMENT_RULES_EXTRACT as schema,
    TradingInstrument as ts,
)
from tqdm import tqdm


load_dotenv()


TRANSCRIPT_GLOB = 'transcripts/clean/*'
TRANSCRIPT_FOLDER = 'transcripts/clean'
MODEL = 'deepseek-v4-flash'
OUTPUT_PREFIX = '2026_04_24_t0'
BATCHES = range(3)


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


def run(batch_dates=None):
    apps = build_apps()
    errlist = []

    if batch_dates is None:
        batch_dates = list_batch_dates()

    pbar = tqdm(batch_dates, desc='extract instrument', unit='day')
    for dt in pbar:
        files = []
        files.extend(glob.glob(f'{TRANSCRIPT_FOLDER}/{dt}.txt'))
        if not files:
            continue

        for batch, app in apps.items():
            try:
                pbar.set_postfix(dt=dt, batch=batch, files=len(files))
                app.run_batch_multiprocess( iter_items_from_files(files), show_progress=False,)
            except Exception as e:
                # pbar.write('error %s %s %s' % (dt, batch, e))
                errlist.append((dt, batch, str(e)))

    return errlist


if __name__ == '__main__':
    run()
