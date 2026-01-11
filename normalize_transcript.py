from typing import List, Tuple
import textwrap
from collections import Counter


class NormFinder:
    def __init__(self, raw: str):
        self.raw = raw
        self.norm, self.norm2raw = self._normalize_with_map(raw)

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
            implied_starts.append(j - chunksize*idx)
        
        c = Counter(implied_starts)
        # print(len(needle_n), implied_starts)
        s_hat, votes = c.most_common(1)[0]
        return s_hat, self.norm2raw[s_hat], votes , len(implied_starts), c
