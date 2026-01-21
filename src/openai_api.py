from openai import OpenAI
from openai.types.responses.response_reasoning_item import ResponseReasoningItem

from src.openai_usage_tracker import TOKEN_CAP, UsageTracker
from dotenv import load_dotenv
from pydantic import BaseModel
from tqdm import tqdm
import glob
import re
import os
from opencc import OpenCC

to_simplified = OpenCC("t2s") 

class OPENAI_API:
    def __init__(self, pydantic_template: BaseModel, output_folder:str, schema: str):
        """Initialize the extractor.

        Args:
            pydantic_template: Pydantic model class or instance used as the output template.
            output_folder: Folder path to write extracted results.
            schema: Prompt/schema instructions passed to the model.
        """
        self.schema = schema
        self.template = pydantic_template
        self.OUTPUT_FOLDER= output_folder
        self.DEBUG_PATH = 'debug_summary/'
        os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)
        os.makedirs(self.DEBUG_PATH, exist_ok=True)
        self.client = OpenAI()

    def normalize_zh_transcript(self, text: str) -> str:
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

    def get_json(self, transcript):
        resp =  self.client.responses.parse(
        model="gpt-5-nano",
        input=[
            {"role": "developer", "content": [{"type": "input_text","text": self.schema,}]}, 
            {"role": "user", "content": [{"type": "input_text", "text": f"Transcript:\n<<<\n{transcript}\n>>>"}]}
            ],
        text_format=self.template,
        text={"verbosity":"medium"},
        reasoning={"effort": "high", "summary":"detailed"},
        tools=[],
        store=True,
        include=[
        ],
        # max_output_tokens=1000
        )
        
        return resp


    def run_batch(self, glob_pattern=None):
        ustrack = UsageTracker()
        spent = ustrack.get()['spent']

        if glob_pattern:
            transcripts = sorted(glob.glob(glob_pattern))
        else:
            transcripts = sorted(glob.glob('transcript/【*.txt'))
        pbar = tqdm(transcripts, desc="Extracting", unit="doc")
        for i, transcript_file in enumerate(pbar, start=1):
            # stop BEFORE calling if already at/over cap
            
            if spent >= TOKEN_CAP:
                pbar.set_postfix({"spent": spent, "cap": TOKEN_CAP, "status": "cap reached"})
                break
            
            dt = re.findall(r'\d+', transcript_file)[0]
            out_path = os.path.join(self.OUTPUT_FOLDER, f"{dt}.json")
            debug_path = os.path.join(self.DEBUG_PATH, f"{dt}.txt")
            if os.path.exists(out_path):
                continue

            with open(transcript_file, 'r') as ifile:
                transcript = ifile.read()

            transcript2 = self.normalize_zh_transcript(transcript)
            resp = self.get_json(transcript2)

            with open(out_path, "w", encoding="utf-8") as ofile:
                ofile.write(resp.output_parsed.model_dump_json(indent=2))
                
            if resp.output and isinstance(resp.output[0],ResponseReasoningItem ):
                summary = [ln.text.replace('. ', '.\n') for ln in resp.output[0].summary]
                with open(debug_path, 'w') as ofile:   
                    ofile.writelines(summary)

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

    load_dotenv() 
    OUTPUT_FOLDER= os.getenv('OUTPUT_FOLDER')
    assert OUTPUT_FOLDER , "output folder missing?"

    from src.schemas import SCHEMA_DEVELOPER_OPENAI
    from template.template import TopicChunks

    app = OPENAI_API( TopicChunks, OUTPUT_FOLDER, SCHEMA_DEVELOPER_OPENAI)
    for _ in app.run_batch():
        break
    