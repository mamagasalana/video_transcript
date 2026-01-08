
#!/usr/bin/env python3
import glob
import json
import os
from typing import Any, Dict, Optional
import time
import re
from llama_cpp import Llama
import re
from schemas import SCHEMA_TOPIC_CHUNK_INSTRUCTIONS
from tqdm import tqdm
import sys
from dotenv import load_dotenv
from normalize_transcript import NormFinder
from opencc import OpenCC

load_dotenv()  # looks for .env in current working dir (or parents)
to_simplified = OpenCC("t2s") 

MODEL_PATH = os.getenv('MODEL_PATH')
TRANSCRIPT_GLOB = "transcript/*.txt"  
OUTPUT_PATH = 'result/'
CTX = 8192
GPU_LAYERS = -1
MAX_TOKENS = 2000
TEMP = 0.2
OVERWRITE = False
CHUNK_SIZE = 6000
SEED = 1234

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


def run_extract(llm: Llama, SCHEMA_INSTRUCTIONS,  transcript_raw: str, seed=1234) -> Dict[str, Any]:
    transcript= re.sub(r'\s+', ' ', transcript_raw).strip()
    prompt = f"{SCHEMA_INSTRUCTIONS}\n\nTranscript:\n<<<\n{transcript.strip()}\n>>>\n"
    STOP = ["<<END_JSON>>"]
    sz = len(llm.tokenize(prompt.encode('utf-8')))
    all_out= []
    nf = NormFinder(transcript)

    if sz + MAX_TOKENS > CTX:
        i = 0
        while 1:
            out = run_extract(llm, SCHEMA_INSTRUCTIONS, transcript[i:i+CHUNK_SIZE], seed=seed)
            out[0]['start_index'] = i
            out[0]['end_index'] = min(i+CHUNK_SIZE, len(transcript)-1)
            all_out.extend(out)
            
            if i+CHUNK_SIZE >= len(transcript):
                break
            tmp = json.loads(out[0]['choices'][0]['text'])
            anchor = tmp['topic_chunks'][-1]['start_anchor']
            i = nf.find(to_simplified.convert(anchor))
            assert i != -1, tmp['topic_chunks'][-1]['start_anchor']
    else:
        out = llm(
            prompt,
            max_tokens= MAX_TOKENS,
            temperature=TEMP,
            top_p=0.9,
            repeat_penalty=1.1,
            stop=STOP,
            seed=seed,

        )
        out['start_index'] = 0
        out['end_index'] = len(transcript)-1
        all_out.append(out)
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
        all_ret  = run_extract(llm , SCHEMA_TOPIC_CHUNK_INSTRUCTIONS, transcript2, seed=SEED)

        final_ret = []
        for ret in all_ret:
            js = json.loads(ret['choices'][0]['text'])
            if final_ret:
                final_ret.pop() # remove last one if exist
            for j in js['topic_chunks']:
                final_ret.append(j)
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(final_ret, f, ensure_ascii=False, indent=2)

    except Exception as e:
        with open('test.txt', 'w') as ofile:
            ofile.write(transcript2)
        print(f"  [{dt}] ERR: {e}")

