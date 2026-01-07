

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
model_size = "large-v3-turbo"

# 2. Load model on GPU
model = WhisperModel(
    model_size,
    device="cuda",        # "cuda" for GPU, "cpu" if no GPU
    compute_type="float16"  # good balance of speed+accuracy on RTX GPUs
)

os.makedirs('transcript' , exist_ok=True)

for video_path in sorted(glob.glob(os.getenv('FOLDER') + '/*')):

    if '【' not in video_path:
        continue
    
    dt = re.findall(r'【\d+】', video_path)[0]
    FOUT = f'transcript/{dt}.txt'

    if os.path.exists(FOUT):
        continue

    file_start = time.perf_counter()   # tic for this file
    print("Transcribing %s ... this may take a while." % dt)
    
    prompt_zh = (
        "这是普通话财经节目。请使用标准财经用语并准确转写机构与公司名称。"
        "常见机构/公司：摩根大通、高盛、摩根士丹利、花旗、瑞银、瑞信、德意志银行、"
        "贝莱德、桥水、富达、景顺；常见词：美联储、加息、降息、收益率、国债、基点、"
        "通胀、CPI、GDP、EPS、PE、标普500、纳斯达克、道琼斯。"
    )
    segments, info = model.transcribe(
        video_path,
        beam_size=5,
        vad_filter=False,   # turn off VAD
        initial_prompt=prompt_zh,
        language="zh",
    )

    print(f"Detected language: {info.language} ({info.language_probability:.2%})")


    with open(FOUT, 'w', encoding="utf-8") as ofile:
        for segment in segments:    
            ofile.write(segment.text.strip() + "\n")
            
    file_end = time.perf_counter()     # toc for this file
    print(f"  Finished {video_path} in {file_end - file_start:.2f} seconds.\n")
