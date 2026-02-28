from openai import OpenAI
from openai.types.responses.response_reasoning_item import ResponseReasoningItem

from src.openai_usage_tracker import TOKEN_CAP, UsageTracker
from src.openai_schema_tracker import FolderSchemaTracker
from src.normalize_transcript import NormFinder
from dotenv import load_dotenv
from pydantic import BaseModel
from tqdm import tqdm
import glob
import re
import os
import json
import hashlib

from typing_extensions import override
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional, Sequence, Tuple, Union
import time
import asyncio
import nest_asyncio
load_dotenv() 
SEED  = 12345

nf = NormFinder('')

@dataclass(frozen=True)
class BatchItem:
    id: str
    text: str
    helper: Optional[str] = None


BatchInputs = Union[Iterable[Tuple[str, str]], Iterable[BatchItem]]


def texts_to_items(texts: Iterable[str]) -> Iterator[BatchItem]:
    for text in texts:
        text_str = str(text)
        text_hash = hashlib.sha1(text_str.encode("utf-8")).hexdigest()
        yield BatchItem(id=text_hash, text=text_str)


def iter_batch_items(inputs: BatchInputs) -> Iterator[BatchItem]:
    for item in inputs:
        if isinstance(item, BatchItem):
            yield item
            continue
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], str)
        ):
            yield BatchItem(id=item[0], text=item[1])
            continue
        raise TypeError(
            "inputs must be an iterable of BatchItem or (id: str, text: str) tuples"
        )


def _format_blocks(blocks: Sequence[Tuple[str, str]]) -> str:
    return "\n".join([f"{label}:\n<<<\n{value}\n>>>" for (label, value) in blocks])


class OPENAI_API:
    def __init__(self, pydantic_template: BaseModel, 
                 output_folder:str, 
                 schema: str, 
                 model:str= 'openai',
                 temperature:float=1.0,
                 default_block_label: str = "Transcript"):
        """Initialize the extractor.

        Args:
            pydantic_template: Pydantic model class or instance used as the output template.
            output_folder: Folder path to write extracted results.
            schema: Prompt/schema instructions passed to the model.
        """
        self.schema = schema
        self.model = model
        self.template = pydantic_template
        self.temperature = temperature
        self.default_block_label = default_block_label
        self.OUTPUT_FOLDER= os.path.join('outputs/model_output', '%s_%s' % (output_folder, self.model))
        self.DEBUG_PATH = os.path.join('outputs/reasoning', 'debug_%s_%s' % (output_folder, self.model))
        os.makedirs(self.OUTPUT_FOLDER, exist_ok=True)
        os.makedirs(self.DEBUG_PATH, exist_ok=True)
        FolderSchemaTracker().set(folder=output_folder, model=self.model, schema=self.schema)
        self.client = OpenAI()

    def request(self, *, blocks: Sequence[Tuple[str, str]]):
        user_text = _format_blocks(blocks)
        resp = self.client.responses.parse(
            model="gpt-5-nano",
            input=[
                {"role": "developer", "content": [{"type": "input_text", "text": self.schema}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
            ],
            text_format=self.template,
            text={"verbosity": "low"},
            reasoning={"effort": "high", "summary": "detailed"},
            tools=[],
            store=True,
            include=[],
            temperature=self.temperature,
            timeout=300,
            # max_output_tokens=1000
        )
        return resp

    def get_json(self, text, block_label: Optional[str] = None):
        label = block_label or self.default_block_label
        return self.request(blocks=[(label, text)])

    def get_json2(self, transcript, helper):
        return self.request(blocks=[("Transcript", transcript), ("Helper", helper)])

    def extract_output(self, resp):        
        js = resp.output_parsed.model_dump_json(indent=2)
        summary = ""
        if resp.output and isinstance(resp.output[0],ResponseReasoningItem ):
            summary = [ln.text.replace('. ', '.\n') for ln in resp.output[0].summary]
        used = resp.usage.total_tokens
        return js, summary, used

    def normalize_usage(self, resp, filename , time_spent):
        usage = resp.usage.to_dict()
        return {
            "provider": self.model,
            "model": resp.model,
            "filename":  filename,
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "reasoning_tokens": usage.get("output_tokens_details", {}).get("reasoning_tokens", 0),
            "cached_tokens": usage.get("input_tokens_details", {}).get("cached_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            'time_spent': time_spent,
        }

    def _iter_items_from_glob(self, glob_pattern: Optional[str]) -> Iterator[BatchItem]:
        if glob_pattern:
            transcript_files = sorted(glob.glob(glob_pattern))
        else:
            transcript_files = sorted(glob.glob('transcript2/*.txt'))

        for transcript_file in transcript_files:
            dt = os.path.basename(transcript_file).split('.')[0]
            with open(transcript_file, 'r') as ifile:
                transcript = ifile.read()
            yield BatchItem(id=dt, text=transcript)

    def iter_items_from_glob(self, glob_pattern: Optional[str]) -> Iterator[BatchItem]:
        return self._iter_items_from_glob(glob_pattern)

    def _iter_items_from_glob_with_helper(
        self, glob_pattern: Optional[str], helper_folder: str
    ) -> Iterator[BatchItem]:
        for item in self._iter_items_from_glob(glob_pattern):
            support_file = glob.glob(
                os.path.join('outputs/model_output', helper_folder, f'{item.id}*')
            )
            assert support_file, "Support file not found"
            with open(support_file[0], 'r') as ifile:
                support = ifile.read()
            yield BatchItem(id=item.id, text=item.text, helper=support)

    def iter_items_from_glob_with_helper(
        self, glob_pattern: Optional[str], helper_folder: str
    ) -> Iterator[BatchItem]:
        return self._iter_items_from_glob_with_helper(glob_pattern, helper_folder)

    def run_batch(self, inputs: BatchInputs, token_cap=TOKEN_CAP, force=False):
        ustrack = UsageTracker(model=self.model, cap=token_cap)
        spent = ustrack.get()['spent']

        items: Iterable[BatchItem] = iter_batch_items(inputs)

        pbar = tqdm(items, desc="Extracting", unit="doc")
        for item in pbar:
            # stop BEFORE calling if already at/over cap
            
            if spent >= token_cap:
                pbar.set_postfix({"spent": spent, "cap": token_cap, "status": "cap reached"})
                break
            
            out_path = os.path.join(self.OUTPUT_FOLDER, f"{item.id}.json")
            debug_path = os.path.join(self.DEBUG_PATH, f"d{item.id}.txt")
            if not force and os.path.exists(out_path):
                continue

            transcript2 = nf.normalize_zh_transcript(item.text)
            
            now = time.time()
            if item.helper is None:
                resp = self.get_json(transcript2)
            else:
                resp = self.get_json2(transcript2, item.helper)

            try:
                js, summary, used = self.extract_output(resp)
            except:
                print('error formatting? %s' % item.id)
                yield resp
                raise

            with open(out_path, "w", encoding="utf-8") as ofile:
                ofile.write(js)
                
            with open(debug_path, 'w') as ofile:   
                ofile.writelines(summary)

            spent = ustrack.set(used)

            try:
                ustrack.update_db(self.normalize_usage(resp, '%s/%s' % (self.OUTPUT_FOLDER ,str(item.id)) , time.time() - now))
            except:
                print('error parsing usage? %s' % item.id)
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

    async def _process_one_item_async(
        self,
        item: BatchItem,
        ustrack: UsageTracker,
        usage_lock: asyncio.Lock,
        force: bool,
        semaphore: asyncio.Semaphore,
    ):
        async with semaphore:
            out_path = os.path.join(self.OUTPUT_FOLDER, f"{item.id}.json")
            debug_path = os.path.join(self.DEBUG_PATH, f"d{item.id}.txt")
            if not force and os.path.exists(out_path):
                return {"dt": item.id, "skipped": True, "used": 0}

            transcript2 = nf.normalize_zh_transcript(item.text)

            now = time.time()
            if item.helper is None:
                resp = await asyncio.to_thread(self.get_json, transcript2)
            else:
                resp = await asyncio.to_thread(self.get_json2, transcript2, item.helper)

            try:
                js, summary, used = self.extract_output(resp)
            except Exception as exc:
                print('error formatting? %s' % item.id)
                raise exc

            with open(out_path, "w", encoding="utf-8") as ofile:
                ofile.write(js)

            with open(debug_path, 'w') as ofile:
                ofile.writelines(summary)

            async with usage_lock:
                spent = ustrack.set(used)
                try:
                    ustrack.update_db(
                        self.normalize_usage(
                            resp,
                            '%s/%s' % (self.OUTPUT_FOLDER, str(item.id)),
                            time.time() - now,
                        )
                    )
                except Exception as exc:
                    print('error parsing usage? %s' % item.id)
                    raise exc

            return {
                "dt": item.id,
                "skipped": False,
                "used": used,
                "spent": spent,
                "resp": resp,
            }

    async def _process_one_file_async(
        self,
        transcript_file: str,
        ustrack: UsageTracker,
        usage_lock: asyncio.Lock,
        force: bool,
        semaphore: asyncio.Semaphore,
    ):
        dt = os.path.basename(transcript_file).split('.')[0]
        with open(transcript_file, 'r') as ifile:
            transcript = ifile.read()
        item = BatchItem(id=dt, text=transcript)
        return await self._process_one_item_async(
            item=item,
            ustrack=ustrack,
            usage_lock=usage_lock,
            force=force,
            semaphore=semaphore,
        )

    def run_batch_multiprocess(
        self,
        inputs: BatchInputs,
        force: bool = False,
        max_workers: int = 20,
        raise_on_error: bool = True,
    ):
        async def _runner():
            ustrack = UsageTracker(model=self.model, cap=TOKEN_CAP)

            items = iter_batch_items(inputs)

            semaphore = asyncio.Semaphore(max_workers)
            usage_lock = asyncio.Lock()

            tasks = []
            for item in items:
                out_path = os.path.join(self.OUTPUT_FOLDER, f"{item.id}.json")
                if not force and os.path.exists(out_path):
                    continue
                tasks.append(
                    asyncio.create_task(
                        self._process_one_item_async(
                            item=item,
                            ustrack=ustrack,
                            usage_lock=usage_lock,
                            force=force,
                            semaphore=semaphore,
                        )
                    )
                )

            results = []
            errors = []
            pbar = tqdm(tasks, desc="Extracting", unit="doc")
            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                    results.append(result)
                    pbar.update(1)
                    pbar.set_postfix({
                        "used": result.get("used", 0),
                        "spent": result.get("spent", 0),
                        "status": "skipped" if result.get("skipped") else "ok",
                    })
                except Exception as exc:
                    errors.append(exc)
                    pbar.update(1)
                    pbar.set_postfix({"status": "error"})
                    if raise_on_error:
                        pbar.close()
                        raise
            pbar.close()

            if errors and raise_on_error:
                raise errors[0]

            return results

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            nest_asyncio.apply(loop)
            return loop.run_until_complete(_runner())

        return asyncio.run(_runner())



    def run_batch_with_helper(self, inputs: BatchInputs, token_cap=TOKEN_CAP, force=False):
        """Get support from topic?

        Args:
            token_cap (_type_, optional): early exit if token cap reach. Defaults to TOKEN_CAP.
            force (bool, optional): overwrite file if True. Defaults to False.
        """
        for resp in self.run_batch(inputs=inputs, token_cap=token_cap, force=force):
            yield resp


class OPENAI_API_DEEPSEEK(OPENAI_API):
    def __init__(self, pydantic_template: BaseModel, output_folder:str, schema: str, model: str="deepseek-reasoner", temperature: float=1.0):
        super().__init__(
            pydantic_template=pydantic_template,
            output_folder=output_folder,
            schema=schema,
            model=model,
            temperature=temperature,
            default_block_label="Transcript",
        )
        self.schema = f"""
{schema}

输出规则（严格）：
- 仅输出有效的 JSON。
- 不得输出任何非 JSON 内容（包括说明、注释）。

输出内容必须严格符合以下 JSON Schema：
{json.dumps(self.template.model_json_schema(), indent=2, ensure_ascii=False)}
        """
        FolderSchemaTracker().set(folder=output_folder, model=self.model, schema=self.schema)
        self.client = OpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url='https://api.deepseek.com')
        self._JSON_FENCE_RE = re.compile(
            r"```(?:json)?\s*([\s\S]*?)\s*```",
            re.IGNORECASE
        )

    def request(self, *, blocks: Sequence[Tuple[str, str]]):
        user_text = _format_blocks(blocks)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.schema},
                {"role": "user", "content": user_text},
            ],
            temperature=self.temperature,
        )
        return resp
    
    @override
    def get_json2(self, transcript, helper):
        return super().get_json2(transcript, helper)
             
    @override
    def get_json(self, text, block_label: Optional[str] = None):
        return super().get_json(text, block_label=block_label)


    @override
    def extract_output(self, resp):
        text = resp.choices[0].message.content

        try:
            js = json.loads(text)
        except:
            m = self._JSON_FENCE_RE.search(text)
            js = json.loads(m.group(1).strip())
            
        js2 = json.dumps(js, indent=2, ensure_ascii=False)

        summary = getattr(resp.choices[0].message, 'reasoning_content', '')
        used = resp.usage.total_tokens
        return js2, summary, used
    
    @override
    def normalize_usage(self, resp, filename , time_spent):
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
            'time_spent': time_spent,
        }
    

if __name__ == "__main__":
    load_dotenv() 
    OUTPUT_FOLDER= os.getenv('OUTPUT_FOLDER')
    assert OUTPUT_FOLDER , "output folder missing?"

    from src.schemas import SCHEMA_DEVELOPER_OPENAI
    from template.template import TopicChunks

    app = OPENAI_API(TopicChunks, OUTPUT_FOLDER, SCHEMA_DEVELOPER_OPENAI)
    for _ in app.run_batch(app.iter_items_from_glob(None)):
        break
