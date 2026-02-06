import os
import re
import glob
import shutil


INPUT_DIR = "transcript2"
OUTPUT_DIR = "transcript3"
MAX_LEN = 2000
OVERLAP = 100

def tokenize(text: str) -> list[str]:
    tokens = re.split(r"\s+", text.strip())
    return [t for t in tokens if t]


def chunk_tokens(tokens: list[str], max_len: int = MAX_LEN, overlap: int = OVERLAP):
    if not tokens:
        return []
    if overlap >= max_len:
        raise ValueError("OVERLAP must be smaller than MAX_LEN")
    chunks = []
    n = len(tokens)
    i = 0
    while i < n:
        start = i
        cur_len = 0
        while i < n:
            tlen = len(tokens[i])
            if cur_len == 0 and tlen > max_len:
                i += 1
                cur_len = tlen
                break
            if cur_len + tlen <= max_len:
                cur_len += tlen+1
                i += 1
            else:
                break
        end = i
        if end == start:
            i += 1
            continue
        chunks.append(" ".join(tokens[start:end]))
        if end >= n:
            break
        if overlap > 0:
            ol = 0
            j = end - 1
            while j >= start and ol < overlap:
                ol += len(tokens[j])
                j -= 1
            i = max(0, j + 1)
        else:
            i = end
    return chunks


def extract_dt(path: str) -> str:
    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)
    nums = re.findall(r"\d+", stem)
    return nums[0] if nums else stem


def process_all(input_dir: str = INPUT_DIR, output_dir: str = OUTPUT_DIR):
    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(input_dir, "*.txt")))
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        tokens = tokenize(raw)
        if not tokens:
            continue
        chunks = chunk_tokens(tokens, MAX_LEN, OVERLAP)
        dt = extract_dt(path)
        for idx, chunk in enumerate(chunks):
            out_path = os.path.join(output_dir, f"{dt}_{idx}.txt")
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(chunk)


if __name__ == "__main__":
    process_all()
