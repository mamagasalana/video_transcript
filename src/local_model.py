from dotenv import load_dotenv
load_dotenv()

import os
import re
import json
import time
import glob
from typing import List, Optional

from src.openai_schema_tracker import FolderSchemaTracker
from src.normalize_transcript import NormFinder
from llama_cpp import Llama
from pydantic import BaseModel
from tqdm import tqdm


MODEL_PATH = os.getenv("MODEL_PATH")
CTX = 9999
GPU_LAYERS = -1
MAX_TOKENS = 5000
TEMP = 0.2
SEED = 1234
STOP = []

nf = NormFinder('')

class LLAMA_CPP_API:
    def __init__(
        self,
        
        pydantic_template: BaseModel,
        output_folder: str,
        schema: str,
        temperature: float = TEMP,
    ):
        self.schema = schema
        self.model = 'llama-cpp'
        self.template = pydantic_template
        self.temperature = temperature

        self.OUTPUT_FOLDER = os.path.join("outputs/model_output", f"{output_folder}_{self.model}")
        self.DEBUG_PATH = os.path.join("outputs/reasoning", f"debug_{output_folder}_{self.model}")
        os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)
        os.makedirs(self.DEBUG_PATH, exist_ok=True)

        start = time.time()
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=CTX,
            n_gpu_layers=GPU_LAYERS,
            n_batch=128,
            seed=SEED,
            verbose=False,
        )
        FolderSchemaTracker().set(folder=output_folder, model=self.model, schema=self.schema)
        print(f"done loading model, time taken: {time.time() - start:.2f}")

    def _schema_prompt(self) -> str:
        schema = self.schema
        schema_json = json.dumps(self.template.model_json_schema(), indent=2, ensure_ascii=False)
        schema = (
            f"{schema}\n\n"
            "输出规则（严格）：\n"
            "- 仅输出有效的 JSON。\n"
            "- 不得输出任何非 JSON 内容（包括说明、注释）。\n\n"
            "输出内容必须严格符合以下 JSON Schema：\n"
            f"{schema_json}\n"
        )
        return schema

    def _build_messages(self, transcript: str, helper: Optional[str] = None):
        sys_prompt = self._schema_prompt()
        user_text = f"Transcript:\n<<<\n{transcript}\n>>>"
        if helper is not None:
            user_text += f"\nHelper:\n<<<\n{helper}\n>>>"
        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_text},
        ]

    def get_json(self, transcript: str, **gen_kwargs):
        messages = self._build_messages(transcript)
        prompt = self._schema_prompt() + "\n\n" + messages[-1]["content"]
        return self.llm(
            prompt=prompt,
            temperature=self.temperature,
            max_tokens=MAX_TOKENS,
            stop=STOP,
            **gen_kwargs,
        )

    

    def _extract_text(self, resp) -> str:
        assert '</think>' in resp['choices'][0]['text']
        return re.split('</think>', resp['choices'][0]['text'])
        

    def _extract_json_payload(self, text: str) -> dict:
        try:
            return json.loads(text)
        except Exception:
            pass

        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence:
            return json.loads(fence.group(1).strip())

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])

        raise ValueError("No valid JSON found in model output.")

    def extract_output(self, resp):
        summary, js_raw = self._extract_text(resp)
        payload = self._extract_json_payload(js_raw)
        js = json.dumps(payload, indent=2, ensure_ascii=False)
        return js, summary

    def run_batch(self, transcripts: List, force: bool = False, max_retries: int = 5):

        for transcript_file in tqdm(transcripts):

            dt = os.path.basename(transcript_file).split(".")[0]
            out_path = os.path.join(self.OUTPUT_FOLDER, f"{dt}.json")
            debug_path = os.path.join(self.DEBUG_PATH, f"{dt}.txt")
            if not force and os.path.exists(out_path):
                continue

            with open(transcript_file, "r") as ifile:
                transcript = ifile.read()

            transcript2 = nf.normalize_zh_transcript(transcript)
            resp = None
            attempt = 0
            while True:
                try:
                    gen_kwargs = {}
                    if attempt > 0:
                        gen_kwargs = {
                            "repeat_penalty": 1.1 + 0.05 * attempt,
                            "frequency_penalty": 0.1 * attempt,
                            "presence_penalty": 0.05 * attempt,
                        }
                    resp = self.get_json(transcript2, **gen_kwargs)
                    js, summary = self.extract_output(resp)
                    break
                except Exception as exc:
                    attempt += 1
                    print(f"error formatting? {dt} (attempt {attempt}/{max_retries + 1})")
                    if resp is not None:
                        yield resp
                    if attempt > max_retries:
                        raise exc

            with open(out_path, "w", encoding="utf-8") as ofile:
                ofile.write(js)

            with open(debug_path, "w") as ofile:
                ofile.writelines(summary)

            yield resp


if __name__ == "__main__":
    from template.template_20260202_1620 import SCHEMA_INSTRUMENT_RULES_EXTRACT as schema, TradingInstrument as ts

    app = LLAMA_CPP_API(ts, "instrument_only(extract)_chunk", schema)
    for _ in app.run_batch('transcript/202007*'):
        break
