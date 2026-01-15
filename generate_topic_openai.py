from openai import OpenAI
from schemas import SCHEMA_DEVELOPER_OPENAI
from dotenv import load_dotenv
from typing import List, Optional
from pydantic import BaseModel, Field

class TopicChunk(BaseModel):
    chunk_id: int
    topic_label_raw: str
    start_anchor: str
    summary: str
    key_entities: List[str] = Field(default_factory=list)
    key_indicators_mentioned: List[str] = Field(default_factory=list)

class Result(BaseModel): 
    topic_chunks: List[TopicChunk]
    
load_dotenv() 
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