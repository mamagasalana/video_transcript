
#!/usr/bin/env python3
import glob
import json
import os
from typing import Any, Dict, Optional
import time
import re
from llama_cpp import Llama
from schemas import SCHEMA_ECON_THEORY_INSTRUCTIONS, SCHEMA_ECON_DATA_INSTRUCTIONS, SCHEMA_REPORT_INSTRUCTIONS, SCHEMA_HIST_EVENTS_INSTRUCTIONS, SCHEMA_INSTRUMENT_OUTLOOK_INSTRUCTIONS
from tqdm import tqdm
import re

MODEL_PATH = os.getenv('MODEL_PATH')
TRANSCRIPT_GLOB = "transcript/*.txt"  
OUTPUT_PATH = 'result/'
CTX = 8192
GPU_LAYERS = -1
MAX_TOKENS = 1400
TEMP = 0.2
OVERWRITE = False


if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

print('loading model')
start = time.time()
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=CTX,
    n_gpu_layers=GPU_LAYERS,
    verbose=False,
)
print('done loading model, time taken: %.2f' % (time.time()-  start))

SCHEMAS = {
    "economic_theories": {
        "instruction": SCHEMA_ECON_THEORY_INSTRUCTIONS,
        "out_file": "economic_theories.json",
    },
    "economic_data": {
        "instruction": SCHEMA_ECON_DATA_INSTRUCTIONS,
        "out_file": "economic_data.json",
    },
    "research_reports_used": {
        "instruction": SCHEMA_REPORT_INSTRUCTIONS,
        "out_file": "research_reports_used.json",
    },
    "historical_events": {
        "instruction": SCHEMA_HIST_EVENTS_INSTRUCTIONS,
        "out_file": "historical_events.json",
    },
    "instrument_outlook": {
        "instruction": SCHEMA_INSTRUMENT_OUTLOOK_INSTRUCTIONS,
        "out_file": "instrument_outlook.json",
    },
}


def chunk_text(s: str, max_chars: int = 12000, overlap: int = 1000):
    s = s.strip()
    if not s:
        return
    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= max_chars:
        raise ValueError("overlap must be < max_chars (otherwise infinite loop)")

    i = 0
    step = max_chars - overlap  # guaranteed > 0
    n = len(s)

    while i < n:
        j = min(n, i + max_chars)
        yield s[i:j]
        i += step


def run_extract(llm: Llama, SCHEMA_INSTRUCTIONS,  transcript: str) -> Dict[str, Any]:
    prompt = f"{SCHEMA_INSTRUCTIONS}\n\nTranscript:\n<<<\n{transcript.strip()}\n>>>\n"
    STOP = ["} {", "}\n{", "\n} {", "\n}\n{"]

    out = llm(
        prompt,
        max_tokens=MAX_TOKENS,
        temperature=TEMP,
        top_p=0.9,
        repeat_penalty=1.1,
        stop=STOP,
        seed=1234,

    )
    return out


def normalize_zh_transcript(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 先把很多空行壓成雙換行（段落）
    text = re.sub(r"\n\s*\n+", "\n\n", text.strip())

    lines = [ln.strip() for ln in text.split("\n")]
    out = []
    for ln in lines:
        if not ln:
            out.append("")  # 段落分隔
            continue
        if not out or out[-1] == "":
            out.append(ln)
            continue

        # 若上一行不像一句話結尾，就合併
        if not re.search(r"[。！？!?：:）\)]$", out[-1]) and len(out[-1]) < 60:
            out[-1] = out[-1] + " " + ln
        else:
            out.append(ln)

    text2 = "\n".join(out)
    text2 = re.sub(r"\n{3,}", "\n\n", text2).strip()
    return text2

for in_path in tqdm(sorted(glob.glob(TRANSCRIPT_GLOB))):
    # in_path = os.path.join('transcript/', '【20251229】.txt')

    dt = re.findall('\d+', in_path)[0]
    with open(in_path, "r", encoding="utf-8") as f:
        transcript = f.read()

    transcript2 = normalize_zh_transcript(transcript)
    for theme, info in SCHEMAS.items():
        start = time.time()
        SCHEMA_INSTRUCTIONS = info['instruction']
        outfile = os.path.join(OUTPUT_PATH, info['out_file'].replace('.json', '_%s.json' % dt))

        ret = run_extract(llm , SCHEMA_INSTRUCTIONS, transcript2)

        tmp = ret['choices'][0]['text']
        try:
            tmp2 = json.loads(tmp)
            with open(outfile, "w", encoding="utf-8") as f:
                json.dump(tmp2, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [{dt}] [{theme}] ERR: {e}")







