import hashlib
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional, Sequence, Tuple, Union
import os

@dataclass(frozen=True)
class BatchItem:
    id: str
    text: str
    helper: Optional[str] = None
    
def texts_to_items(texts: Iterable[str]) -> Iterator[BatchItem]:
    for text in texts:
        text_str = str(text)
        text_hash = hashlib.sha1(text_str.encode("utf-8")).hexdigest()
        yield BatchItem(id=text_hash, text=text_str)

def iter_items_from_files(iterables: Iterable[str] =None) -> Iterator[BatchItem]:
    if iterables is not None:
        transcript_files = sorted(iterables)
    else:
        transcript_files = sorted(glob.glob('transcript2/*.txt'))

    for transcript_file in transcript_files:
        dt = os.path.basename(transcript_file).split('.')[0]
        with open(transcript_file, 'r') as ifile:
            transcript = ifile.read()
        yield BatchItem(id=dt, text=transcript)
        