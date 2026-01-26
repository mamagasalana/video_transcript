from openai import OpenAI
from openai.types.responses.response_reasoning_item import ResponseReasoningItem

from src.openai_usage_tracker import TOKEN_CAP, UsageTracker
from dotenv import load_dotenv
from pydantic import BaseModel
from tqdm import tqdm
import glob
import re
import os
import json
from opencc import OpenCC
from dotenv import load_dotenv
from typing_extensions import override

load_dotenv() 


to_simplified = OpenCC("t2s") 

class OPENAI_API:
    def __init__(self, pydantic_template: BaseModel, 
                 output_folder:str, 
                 schema: str, 
                 debug_path:str='debug_summary/'):
        """Initialize the extractor.

        Args:
            pydantic_template: Pydantic model class or instance used as the output template.
            output_folder: Folder path to write extracted results.
            schema: Prompt/schema instructions passed to the model.
        """
        self.schema = schema
        self.model = "openai"
        self.template = pydantic_template
        self.OUTPUT_FOLDER= os.path.join('outputs', output_folder)
        self.DEBUG_PATH = os.path.join('outputs', debug_path)
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
        text={"verbosity":"low"},
        reasoning={"effort": "high", "summary":"detailed"},
        tools=[],
        store=True,
        include=[
        ],
        timeout= 300,
        # max_output_tokens=1000
        )
        
        return resp

    def extract_output(self, resp):        
        js = resp.output_parsed.model_dump_json(indent=2)
        summary = ""
        if resp.output and isinstance(resp.output[0],ResponseReasoningItem ):
            summary = [ln.text.replace('. ', '.\n') for ln in resp.output[0].summary]
        used = resp.usage.total_tokens
        return js, summary, used

    def normalize_usage(self, resp, filename):
        usage = resp.usage.to_dict()
        return {
            "provider": self.model,
            "model": resp.model,
            "filename": filename,
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "reasoning_tokens": usage.get("output_tokens_details", {}).get("reasoning_tokens", 0),
            "cached_tokens": usage.get("input_tokens_details", {}).get("cached_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    def run_batch(self, glob_pattern=None, token_cap=TOKEN_CAP, force=False):
        ustrack = UsageTracker(model=self.model, cap=token_cap)
        spent = ustrack.get()['spent']

        if glob_pattern:
            transcripts = sorted(glob.glob(glob_pattern))
        else:
            transcripts = sorted(glob.glob('transcript2/*.txt'))
        pbar = tqdm(transcripts, desc="Extracting", unit="doc")
        for i, transcript_file in enumerate(pbar, start=1):
            # stop BEFORE calling if already at/over cap
            
            if spent >= token_cap:
                pbar.set_postfix({"spent": spent, "cap": token_cap, "status": "cap reached"})
                break
            
            dt = re.findall(r'\d+', os.path.basename(transcript_file))[0]
            out_path = os.path.join(self.OUTPUT_FOLDER, f"{dt}.json")
            debug_path = os.path.join(self.DEBUG_PATH, f"{dt}.txt")
            if not force and os.path.exists(out_path):
                continue

            with open(transcript_file, 'r') as ifile:
                transcript = ifile.read()

            transcript2 = self.normalize_zh_transcript(transcript)
            
            resp = self.get_json(transcript2)

            try:
                js, summary, used = self.extract_output(resp)
            except:
                print('error formatting? %s' % dt)
                yield resp
                raise

            with open(out_path, "w", encoding="utf-8") as ofile:
                ofile.write(js)
                
            with open(debug_path, 'w') as ofile:   
                ofile.writelines(summary)

            spent = ustrack.set(used)

            try:
                ustrack.update_db(self.normalize_usage(resp, str(dt)))
            except:
                print('error parsing usage? %s' % dt)
                yield resp
                raise

            pbar.set_postfix({
                "used": used,
                "spent": spent,
                "remain": max(token_cap - spent, 0),
            })

            # stop AFTER call if this call pushed you over
            if spent >= token_cap:
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
    
class OPENAI_API_DEEPSEEK(OPENAI_API):
    def __init__(self, pydantic_template: BaseModel, output_folder:str, schema: str, debug_path:str='debug_summary_deepseek'):
        super().__init__(
            pydantic_template=pydantic_template,
            output_folder=output_folder,
            schema=schema,
            debug_path=debug_path,
        )
        self.model = "deepseek"
        self.schema = f"""
{schema}

输出规则（严格）：
- 仅输出有效的 JSON。
- 不得输出任何非 JSON 内容（包括说明、注释）。

输出内容必须严格符合以下 JSON Schema：
{json.dumps(self.template.model_json_schema(), indent=2, ensure_ascii=False)}
        """
        self.client = OpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url='https://api.deepseek.com')
        self._JSON_FENCE_RE = re.compile(
            r"```(?:json)?\s*([\s\S]*?)\s*```",
            re.IGNORECASE
        )
                
    @override
    def get_json(self, transcript):
        resp = self.client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": self.schema},
                {"role": "user", "content": f"Transcript:\n<<<\n{transcript}\n>>>"},
            ],
            timeout= 300,
            # response_format={"type": "json_object"},  # force JSON object (if provider supports it)
        )
        return resp


    @override
    def extract_output(self, resp):
        text = resp.choices[0].message.content

        try:
            js = json.loads(text)
        except:
            m = self._JSON_FENCE_RE.search(text)
            js = json.loads(m.group(1).strip())
            
        js2 = json.dumps(js, indent=2, ensure_ascii=False)

        summary = resp.choices[0].message.reasoning_content
        used = resp.usage.total_tokens
        return js2, summary, used
    
    @override
    def normalize_usage(self, resp, filename):
        usage = resp.usage.to_dict()
        return {
            "provider": "deepseek",
            "model": resp.model,
            "filename": filename,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "reasoning_tokens": usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0),
            "cached_tokens": usage.get("prompt_tokens_details", {}).get("cached_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }