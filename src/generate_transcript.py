

from faster_whisper import WhisperModel
import logging
import glob
import re
import os
import time
import torch
from opencc import OpenCC
from tqdm import tqdm

to_simplified = OpenCC("t2s") 

if not torch.cuda.is_available():
    raise RuntimeError("No CUDA device available – cannot run on GPU.")

root = logging.getLogger()
root.setLevel(logging.INFO)

# If handlers already exist, don't add another console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
ch.setFormatter(formatter)
root.addHandler(ch)

# 1. Choose model size: "tiny", "base", "small", "medium", "large-v2"
model_size = "large-v3-turbo"

# 2. Load model on GPU
model = WhisperModel(
    model_size,
    device="cuda",        # "cuda" for GPU, "cpu" if no GPU
    compute_type="float16"  # good balance of speed+accuracy on RTX GPUs
)

os.makedirs('transcript' , exist_ok=True)
os.makedirs('transcript2' , exist_ok=True)

for video_path in sorted(glob.glob(os.getenv('FOLDER') + '/*')):

    if '【' not in video_path:
        continue
    
    dt = re.findall(r'【\d+】', video_path)[0]
    FOUT = f'transcript/{dt}.txt'

    if os.path.exists(FOUT):
        continue

    file_start = time.perf_counter()   # tic for this file
    print("Transcribing %s ... this may take a while." % dt)
    
    segments, info = model.transcribe(
        video_path,
        beam_size=5,
        vad_filter=False,   # turn off VAD
        language="zh",
    )

    print(f"Detected language: {info.language} ({info.language_probability:.2%})")


    with open(FOUT, 'w', encoding="utf-8") as ofile:
        for segment in segments:    
            ofile.write(segment.text.strip() + "\n")
            
    file_end = time.perf_counter()     # toc for this file
    print(f"  Finished {video_path} in {file_end - file_start:.2f} seconds.\n")


def normalize_zh_transcript(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n\s*\n+", "\n\n", text.strip())

    lines = [ln.strip() for ln in text.split("\n")]
    out = []
    for ln in lines:
        if not ln:
            out.append("")  
            continue
        if not out or out[-1] == "":
            out.append(ln)
            continue

        
        if not re.search(r"[。！？!?：:）\)]$", out[-1]) and len(out[-1]) < 60:
            out[-1] = out[-1] + " " + ln
        else:
            out.append(ln)

    text2 = "\n".join(out)
    # text2 = re.sub(r"\n{3,}", "\n\n", text2).strip()
    text2 = re.sub(r'\s+', ' ', text2).strip()
    return to_simplified.convert(text2)

def wrap_by_whitespace(text: str, max_len: int = 30) -> str:
    # Split by any whitespace and drop empties
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


# clean to make it readable
for transcript_path in  tqdm(sorted(glob.glob('transcript/*'))):
    with open(transcript_path, 'r') as ifile:
        transcript_raw =ifile.read()


    transcript_path2 = re.findall(r'\d+', transcript_path)[0]
    out_file = os.path.join('transcript2', '%s.txt' % transcript_path2)
    if os.path.exists(out_file):
        continue
    
    transcript_clean = normalize_zh_transcript(transcript_raw)
    transcript_clean2 = wrap_by_whitespace(transcript_clean, 60)
    
    with open(out_file, 'w') as ofile:
        transcript_raw =ofile.write(transcript_clean2)