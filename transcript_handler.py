#!/usr/bin/env python3
import glob
import json
import os
from typing import Any, Dict, Optional
import time
import re
from llama_cpp import Llama

MODEL_PATH = os.getenv('MODEL_PATH')
TRANSCRIPT_GLOB = "transcript/*.txt"  
OUTPUT_PATH = 'result/'
CTX = 8192
GPU_LAYERS = -1
MAX_TOKENS = 1400
TEMP = 0.2
OVERWRITE = False


SCHEMA_INSTRUCTIONS = r"""
You are an information extraction system for Mandarin financial video transcripts.
Extract ONLY what is explicitly stated in the transcript. Do not invent facts.
Return valid JSON ONLY (no markdown, no commentary, no code fences).

Known metadata (for reference only; do NOT infer new facts from it):
- program: 金錢報
- host: 世光
- members: 金鐵桿
Rules about metadata:
- Use metadata ONLY to label speakers/program if the transcript is ambiguous.
- Do NOT add theories/data/events/instruments unless they appear in the transcript.

Schema (must match exactly):
{
  "economic_theories":[{"raw":string,"normalized":string|null,"confidence":number,"evidence":string,"note":string|null}],
  "economic_data":[{"indicator_raw":string,"indicator_normalized":string|null,"value":string|null,"unit":string|null,"frequency":string|null,"confidence":number,"evidence":string,"note":string|null}],
  "derived_data":[{"raw":string,"normalized":string|null,"confidence":number,"formula":string|null,"inputs":[string],"value":string|null,"unit":string|null,"evidence":string,"note":string|null}],
  "instruments":[{"instrument_raw":string,"instrument_normalized":string|null,"prediction":string|null,"direction":"up|down|neutral"|null,"target_or_level":string|null,"horizon":string|null,"confidence":number,"evidence":string,"note":string|null}],
  "historical_events":[{"raw":string,"normalized":string|null,"confidence":number,"date":string|null,"evidence":string,"note":string|null}],
  "reports_used":[{"raw":string,"normalized":string|null,"publisher":string|null,"date":string|null,"confidence":number,"evidence":string,"note":string|null}]
}


IMPORTANT (economic_data):
- "indicator_raw" must be the NAME of the economic indicator, not a number.
- Examples:
  - Correct: indicator_raw="美國股市本益比", value="21.7", unit="倍"
  - Incorrect: indicator_raw="21.7倍"
- Numeric values must go into "value".

Transcript may contain ASR typos (homophones).
Normalization rules:
- Always include the exact transcript phrase in "raw".
- Only fill "normalized" if you are highly confident (>=0.8) about the intended entity.
- If multiple candidates exist (e.g., 摩根大通 vs 摩根士丹利), set "normalized": null and explain ambiguity in "note".
- Never silently replace an entity; preserve uncertainty.

Rules:
- evidence should be a short quote or faithful paraphrase from the transcript.
- If missing/unclear, set the field to null (or empty list) and say why in evidence.
- Do not guess dates. Use null if not explicitly provided.
""".strip()


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



def build_prompt(transcript: str) -> str:
    return f"{SCHEMA_INSTRUCTIONS}\n\nTranscript:\n<<<\n{transcript.strip()}\n>>>\n"


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    t = text.strip()
    if t.startswith("{") and t.endswith("}"):
        try:
            return json.loads(t)
        except Exception:
            pass

    start = text.find("{")
    if start == -1:
        return None

    brace = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            brace += 1
        elif text[i] == "}":
            brace -= 1
            if brace == 0:
                candidate = text[start : i + 1].strip()
                try:
                    return json.loads(candidate)
                except Exception:
                    return None
    return None


def validate_shape(obj: Dict[str, Any]) -> bool:
    required = ["economic_theories", "economic_data", "derived_data", "instruments", "historical_events"]
    return all(k in obj for k in required)


def run_extract(llm: Llama, transcript: str) -> Dict[str, Any]:
    prompt = build_prompt(transcript)

    out = llm(
        prompt,
        max_tokens=MAX_TOKENS,
        temperature=TEMP,
        top_p=0.9,
        repeat_penalty=1.1,
        stop=[],
    )
    text = out["choices"][0]["text"]

    obj = extract_json(text)
    if obj is not None and isinstance(obj, dict) and validate_shape(obj):
        return obj

    # one repair try
    repair_prompt = (
        SCHEMA_INSTRUCTIONS
        + "\n\nYour previous output was invalid or not pure JSON.\n"
          "Return ONLY valid JSON matching the schema.\n\n"
        + "Transcript:\n<<<\n"
        + transcript.strip()
        + "\n>>>\n"
    )
    out2 = llm(
        repair_prompt,
        max_tokens=MAX_TOKENS,
        temperature=0.0,
        top_p=1.0,
        repeat_penalty=1.1,
        stop=[],
    )
    text2 = out2["choices"][0]["text"]
    obj2 = extract_json(text2)
    if obj2 is None or not isinstance(obj2, dict) or not validate_shape(obj2):
        raise RuntimeError("Model did not return valid JSON (even after repair).")
    return obj2


def main():
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

    os.makedirs("transcript", exist_ok=True)

    for in_path in sorted(glob.glob(TRANSCRIPT_GLOB, recursive=True)):
        # base, _ = os.path.splitext(in_path)
        dt = re.findall('\d+', in_path)[0]
        out_path = '%s%s.json' % (OUTPUT_PATH, dt)

        if os.path.exists(out_path) and not OVERWRITE:
            print(f"[SKIP] {out_path} exists")
            continue

        with open(in_path, "r", encoding="utf-8") as f:
            transcript = f.read()

        if not transcript.strip():
            print(f"[SKIP] empty transcript: {in_path}")
            continue

        chunks = list(chunk_text(transcript, max_chars=8000, overlap=800))
        all_outputs = []

        for idx, ch in enumerate(chunks, start=1):
            try:
                obj = run_extract(llm, ch)
                all_outputs.append(obj)
                print(f"  [CHUNK {idx}/{len(chunks)}] OK")
            except Exception as e:
                print(f"  [CHUNK {idx}/{len(chunks)}] ERR: {e}")

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"chunks": all_outputs}, f, ensure_ascii=False, indent=2)
    print("Done.")


if __name__ == "__main__":
    main()
