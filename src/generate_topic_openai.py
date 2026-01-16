from openai import OpenAI
from src.schemas import SCHEMA_DEVELOPER_OPENAI
from src.openai_usage_tracker import TOKEN_CAP, UsageTracker
from dotenv import load_dotenv
from typing import List, Optional
from pydantic import BaseModel, Field
from tqdm import tqdm
import glob
import re
import os
import json
import time
import datetime

load_dotenv() 
OUTPUT_FOLDER= os.getenv('OUTPUT_FOLDER')
assert OUTPUT_FOLDER , "output folder missing?"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

class TopicChunk(BaseModel):
    chunk_id: int
    topic_label_raw: str
    start_anchor: str
    summary: str
    key_entities: List[str] = Field(default_factory=list)
    key_indicators_mentioned: List[str] = Field(default_factory=list)

class Result(BaseModel): 
    topic_chunks: List[TopicChunk]
    
client = OpenAI()

def get_json(transcript):
    resp =  client.responses.parse(
    model="gpt-5-nano",
    input=[
        {"role": "developer", "content": [{"type": "input_text","text": SCHEMA_DEVELOPER_OPENAI,}]}, 
        {"role": "user", "content": [{"type": "input_text", "text": f"Transcript:\n<<<\n{transcript}\n>>>"}]}
        ],
    text_format=Result,
    text={"verbosity":"low"},
    reasoning={"effort": "medium"},
    tools=[],
    store=True,
    include=[
        "reasoning.encrypted_content",
        "web_search_call.action.sources"
    ]
    )
    
    return resp


def run_batch():

    ustrack = UsageTracker()
    spent = ustrack.get()['spent']

    transcripts = sorted(glob.glob('transcript/【*.txt'))
    pbar = tqdm(transcripts, desc="Extracting", unit="doc")
    for i, transcript_file in enumerate(pbar, start=1):
        # stop BEFORE calling if already at/over cap
        
        if spent >= TOKEN_CAP:
            pbar.set_postfix({"spent": spent, "cap": TOKEN_CAP, "status": "cap reached"})
            break
        
        dt = re.findall(r'\d+', transcript_file)[0]
        out_path = os.path.join(OUTPUT_FOLDER, f"{dt}.json")
        if os.path.exists(out_path):
            continue

        with open(transcript_file, 'r') as ifile:
            transcript = ifile.read()

        resp = get_json(transcript)

        with open(out_path, "w", encoding="utf-8") as ofile:
            ofile.write(resp.output_parsed.model_dump_json(indent=2))

        used = resp.usage.total_tokens
        spent = ustrack.set(used)

        pbar.set_postfix({
            "used": used,
            "spent": spent,
            "remain": max(TOKEN_CAP - spent, 0),
        })

        # stop AFTER call if this call pushed you over
        if spent >= TOKEN_CAP:
            break

        yield resp  # or yield resp.output_parsed, etc.


if __name__ == "__main__":
    for _ in run_batch():
        pass