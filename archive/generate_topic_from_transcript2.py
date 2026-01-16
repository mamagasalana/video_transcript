
#!/usr/bin/env python3
import glob
import json
import os
from typing import Any, Dict, Optional
import time
import re
from llama_cpp import Llama
import re
from src.schemas import END_ANCHOR_ONLY_INSTRUCTIONS
from tqdm import tqdm
import sys
from dotenv import load_dotenv
from archive.normalize_transcript import NormFinder
from opencc import OpenCC

load_dotenv()  # looks for .env in current working dir (or parents)
to_simplified = OpenCC("t2s") 

MODEL_PATH = os.getenv('MODEL_PATH')
TRANSCRIPT_GLOB = "transcript/*.txt"  
OUTPUT_PATH = 'result/'
CTX = 9999
GPU_LAYERS = -1
MAX_TOKENS = 3000
TEMP = 0.2
OVERWRITE = False
CHUNK_SIZE = 6000
SEED = 1234

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

print('loading model %s' % MODEL_PATH)
start = time.time()
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=CTX,
    n_gpu_layers=GPU_LAYERS,
    n_batch=128,
    verbose=False,
)
print('done loading model, time taken: %.2f' % (time.time()-  start))

def clean_think(txt):
    start_idx = 0
    if '</think>' in txt:
        start_idx = txt.find('</think>')

    return re.findall(r'([\u4e00-\u9fff].*?)<<IWANTTOREST>>', txt[start_idx:])[0]

def extract(prompt):
    STOP = []
    out = llm(
        prompt,
        max_tokens= MAX_TOKENS,
        temperature=TEMP,
        top_p=0.9,
        repeat_penalty=1.1,
        stop=STOP,
        seed=SEED,

    )
    
    try:
        tmp = clean_think(out['choices'][0]['text'])
        out['js'] =  tmp
    except Exception as e:

        with open("test.txt", "w", encoding="utf-8") as f:
            f.write(out["choices"][0]["text"])
        with open("test.txt", "a", encoding="utf-8") as f:
            f.write('\n')
            f.write(json.dumps(out.get("usage", {})))
        print('debug')

    return out
    
def run_extract(SCHEMA_INSTRUCTIONS,  transcript_raw: str) -> Dict[str, Any]:
    transcript= re.sub(r'\s+', ' ', transcript_raw).strip()
    # STOP = ["<<IWANTTOREST>>"]
    all_out= []
    nf = NormFinder(transcript)

    i = 0
    next_norm_idx = 0
    attempt= 1
    debug_attempt = {}
    while attempt:

        prompt =  f"{SCHEMA_INSTRUCTIONS}\n\nTranscript:\n<<<\n{transcript[i:i+CHUNK_SIZE].strip()}\n>>>\n"
        out = extract(prompt)
        debug_attempt[attempt] = i
                
        anchor = out['js']
        next_norm_idx, next_original_idx = nf.find(to_simplified.convert(anchor), next_norm_idx)
        out.update( {'start_index': i, 
                      'end_index': next_original_idx})
        all_out.append(out)
        try:
            assert next_original_idx != -1, anchor
        except:
            with open("test.txt", "w", encoding="utf-8") as f:
                f.write(transcript[debug_attempt[attempt]:debug_attempt[attempt]+CHUNK_SIZE])
            print('debug')
        
        attempt+=1
        i= next_original_idx

    return all_out


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
    text2 = re.sub(r"\n{3,}", "\n\n", text2).strip()
    return to_simplified.convert(text2)

for in_path in tqdm(sorted(glob.glob('transcript/*'))):
    dt = re.findall('\d+', in_path)[0]
    if len(sys.argv)  > 1:
        if dt != sys.argv[1]:
            continue

    out_path = '%stopic_%s.json' % (OUTPUT_PATH, dt)
    if os.path.exists(out_path):
        continue

    with open(in_path, "r", encoding="utf-8") as f:
        transcript = f.read()
    transcript2 = normalize_zh_transcript(transcript)

    try:
        all_ret  = run_extract(END_ANCHOR_ONLY_INSTRUCTIONS, transcript2)

        final_ret = []
        for ret in all_ret:
            js = ret['js']
            final_ret.append(js)
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(final_ret, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"  [{dt}] ERR: {e}")

