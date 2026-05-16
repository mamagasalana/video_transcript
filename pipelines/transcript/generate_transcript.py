from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from faster_whisper import WhisperModel
import glob
import logging
import multiprocessing as mp
import os
import re
import time
import torch
from src.transcript.normalize_transcript import NormFinder
from tqdm import tqdm
import shutil

nf = NormFinder("")

if not torch.cuda.is_available():
    raise RuntimeError("No CUDA device available - cannot run on GPU.")

root = logging.getLogger()
root.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
ch.setFormatter(formatter)
root.addHandler(ch)

logging.getLogger("faster_whisper").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

MODEL_SIZE = "large-v3-turbo"
MODEL_DOWNLOAD_ROOT = str(ROOT / "models" / "faster-whisper")
MODEL_LOCAL_FILES_ONLY = False
MODEL_DEVICE = "cuda"
MODEL_COMPUTE_TYPE = "float16"
BEAM_SIZE = 5
TRANSCRIBE_LANGUAGE = "zh"
TRANSCRIBE_VAD_FILTER = True

RAW_DIR = str(ROOT / "transcripts" / "raw")
CLEAN_DIR = str(ROOT / "transcripts" / "clean")

N_WORKERS = 4
MAX_TASKS_PER_CHILD = 1
VERBOSE = False
DEBUG = 0
FORCE_RESET = 0

model = None


def get_cached_model_dir():
    repo_cache_dir = os.path.join(
        MODEL_DOWNLOAD_ROOT,
        "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo",
    )
    ref_path = os.path.join(repo_cache_dir, "refs", "main")
    if os.path.isfile(ref_path):
        with open(ref_path, "r", encoding="utf-8") as ifile:
            revision = ifile.read().strip()
        if revision:
            snapshot_dir = os.path.join(repo_cache_dir, "snapshots", revision)
            if os.path.isdir(snapshot_dir):
                return snapshot_dir

    snapshots_dir = os.path.join(repo_cache_dir, "snapshots")
    if os.path.isdir(snapshots_dir):
        snapshot_names = sorted(
            x for x in os.listdir(snapshots_dir)
            if os.path.isdir(os.path.join(snapshots_dir, x))
        )
        if snapshot_names:
            return os.path.join(snapshots_dir, snapshot_names[-1])

    return None

def get_model():
    global model
    if model is None:
        model_source = get_cached_model_dir() or MODEL_SIZE
        if VERBOSE:
            print(f"Loading Whisper model: {model_source}")
            print(f"Whisper download_root: {MODEL_DOWNLOAD_ROOT}")
        kwargs = {
            "device": MODEL_DEVICE,
            "compute_type": MODEL_COMPUTE_TYPE,
        }
        if model_source == MODEL_SIZE:
            kwargs["download_root"] = MODEL_DOWNLOAD_ROOT
            kwargs["local_files_only"] = MODEL_LOCAL_FILES_ONLY
        model = WhisperModel(model_source, **kwargs)
    return model

def wrap_by_whitespace(text: str, max_len: int = 30) -> str:
    tokens = re.findall(r"\S+", text)

    lines = []
    current = ""

    for tok in tokens:
        if not current:
            current = tok
        else:
            candidate = current + " " + tok
            if len(candidate) <= max_len:
                current = candidate
            else:
                lines.append(current)
                current = tok

    if current:
        lines.append(current)

    return "\n".join(lines)


def process_video(video_path):
    if "【" not in video_path:
        return

    dt = re.findall(r"【\d+】", video_path)[0]
    fout = os.path.join(RAW_DIR, f"{dt}.txt")
    clean_out = os.path.join(CLEAN_DIR, f"{dt.strip('【】')}.txt")

    if not DEBUG and os.path.exists(fout) and os.path.getsize(fout) > 0:
        return

    if os.path.exists(clean_out):
        os.remove(clean_out)

    file_start = time.perf_counter()
    if VERBOSE:
        print(f"Transcribing {dt} ... this may take a while.")

    segments, info = get_model().transcribe(
        video_path,
        beam_size=BEAM_SIZE,
        vad_filter=TRANSCRIBE_VAD_FILTER,
        language=TRANSCRIBE_LANGUAGE,
    )

    if VERBOSE:
        print(f"Detected language: {info.language} ({info.language_probability:.2%})")

    joined_text = "\n".join(
        segment.text.strip()
        for segment in segments
        if segment.text and segment.text.strip()
    )

    with open(fout, "w", encoding="utf-8") as ofile:
        ofile.write(joined_text)

    file_end = time.perf_counter()
    if VERBOSE:
        print(f"  Finished {video_path} in {file_end - file_start:.2f} seconds.\n")


def clean_transcript_file(transcript_path):
    with open(transcript_path, "r", encoding="utf-8") as ifile:
        transcript_raw = ifile.read()

    if not transcript_raw.strip():
        return

    transcript_path2 = re.findall(r"\d+", transcript_path)[0]
    out_file = os.path.join(CLEAN_DIR, f"{transcript_path2}.txt")

    if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
        return

    transcript_clean = nf.normalize_zh_transcript(transcript_raw)
    transcript_clean2 = wrap_by_whitespace(transcript_clean, 60)

    with open(out_file, "w", encoding="utf-8") as ofile:
        ofile.write(transcript_clean2)


if __name__ == "__main__":
    video_paths = sorted(glob.glob(os.getenv("FOLDER") + "/*"))
    video_paths = [x for x in video_paths if "【" in x]

    DEBUG = 0
    FORCE_RESET = 1

    if FORCE_RESET:
        print('deleing existing transcripts outputs ...')
        for folder in[RAW_DIR, CLEAN_DIR]:
            if os.path.isdir(folder):
                shutil.rmtree(folder)

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(CLEAN_DIR, exist_ok=True)

    if DEBUG:
        video_paths = [x for x in video_paths if "20260402" in x]
        N_WORKERS = 1
        VERBOSE = True
    else:
        filtered_video_paths = []
        for video_path in video_paths:
            dt_match = re.findall(r"【\d+】", video_path)
            if not dt_match:
                continue
            fout = os.path.join(RAW_DIR, f"{dt_match[0]}.txt")
            if os.path.exists(fout) and os.path.getsize(fout) > 0:
                continue
            filtered_video_paths.append(video_path)
        video_paths = filtered_video_paths

    if N_WORKERS <= 1:
        for video_path in video_paths:
            process_video(video_path)
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(N_WORKERS, maxtasksperchild=MAX_TASKS_PER_CHILD) as pool:
            list(
                tqdm(
                    pool.imap_unordered(process_video, video_paths),
                    total=len(video_paths),
                    desc="videos",
                    unit="video",
                )
            )

    transcript_paths = sorted(glob.glob(os.path.join(RAW_DIR, "*")))
    for transcript_path in tqdm(transcript_paths, desc="clean", unit="file"):
        clean_transcript_file(transcript_path)
