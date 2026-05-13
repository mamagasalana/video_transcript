from typing import List, Tuple
import textwrap
from collections import Counter
import re
from opencc import OpenCC

to_simplified = OpenCC("t2s") 

class NormFinder:
    def __init__(self, raw: str):
        if not raw:
            return
        self.raw = raw
        self.norm, self.norm2raw_list = self._normalize_with_map(raw)
        self.norm2raw = {idx: v for idx, v in enumerate(self.norm2raw_list)}

        raw2norm = {v:k for k,v in self.norm2raw.items()} # this has gap
        self.raw2norm = {}
        prev = raw2norm[min(raw2norm)]   # fill missing gap with previous value
        for i in range(min(raw2norm), max(raw2norm) + 1):
            prev = raw2norm.get(i, prev)
            self.raw2norm[i] = prev

    def _normalize_with_map(self, s: str) -> Tuple[str, List[int]]:
        norm_chars: List[str] = []
        norm2raw: List[int] = []

        i, n = 0, len(s)
        while i < n:
            ch = s[i]
            if ch.isspace():
                # consume whitespace run
                j = i
                while j < n and s[j].isspace():
                    j += 1

                i = j
            else:
                norm_chars.append(ch)
                norm2raw.append(i)
                i += 1

        return "".join(norm_chars), norm2raw

    def normalize(self, s: str) -> str:
        # we only need normalized string; ignore map
        return self._normalize_with_map(s)[0]

    def find(self, needle: str, start_norm: int = 0) -> int:
        needle_n = self.normalize(needle)
        if not needle_n:
            return -1, -1

        j = self.norm.find(needle_n, start_norm)
        if j == -1:
            return -1, -1

        return j, self.norm2raw[j]

    def find_by_chunk(self, needle: str, start_norm: int = 0, chunksize: int=10) -> int:
        needle_n = self.normalize(needle)
        needle_chunks = textwrap.wrap(needle_n, width=chunksize)
        implied_starts= []
        for idx, nc in enumerate(needle_chunks):
            j = self.norm.find(nc, start_norm)
            if j != -1:
                j-=chunksize*idx
            implied_starts.append(j)
        
        c = Counter(implied_starts)
        # print(len(needle_n), implied_starts)
        s_hat, votes = c.most_common(1)[0]
        return { 'normalized_idx': s_hat,
                'raw_idx': self.norm2raw[s_hat], 
                'win_vote' : votes ,
                 'total_vote' : len(implied_starts), 
                 'extra_debug': c}


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