

from faster_whisper import WhisperModel
import logging
import glob
import re
import os
import time
import torch
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
model_size = "medium"

# 2. Load model on GPU
# model = WhisperModel(
#     model_size,
#     device="cuda",        # "cuda" for GPU, "cpu" if no GPU
#     compute_type="float16"  # good balance of speed+accuracy on RTX GPUs
# )

model = WhisperModel(
    model_size,
    device="cpu",
    compute_type="int8",  # fastest on CPU, acceptable accuracy drop
)

for video_path in glob.glob('/mnt/c/Users/pokes/Downloads/*.mp4'):

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
