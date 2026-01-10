from typing import List, Tuple

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
