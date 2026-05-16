import hashlib
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional
import os
import glob

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

def texts_to_items2(texts: Iterable[str], ids: Iterable[str] ) -> Iterator[BatchItem]:
    for text, _id in zip(texts, ids):
        text_str = str(text)
        yield BatchItem(id=_id, text=text_str)

def iter_items_from_files(iterables: Iterable[str] =None) -> Iterator[BatchItem]:
    if iterables is not None:
        transcript_files = sorted(iterables)
    else:
        transcript_files = sorted(glob.glob('transcripts/clean/*.txt'))

    for transcript_file in transcript_files:
        dt = os.path.basename(transcript_file).split('.')[0]
        with open(transcript_file, 'r') as ifile:
            transcript = ifile.read()
        yield BatchItem(id=dt, text=transcript)

def iter_items_from_files_with_helpers(
    iterables: Iterable[str],
    helpers: Iterable[str],
) -> Iterator[BatchItem]:
    transcript_files = sorted(iterables)
    helper_values = list(helpers)

    if len(helper_values) != len(transcript_files):
        raise ValueError(
            f"helpers length mismatch: {len(helper_values)} helpers for {len(transcript_files)} files"
        )

    for helper, transcript_file in zip(helper_values, transcript_files):
        dt = os.path.basename(transcript_file).split('.')[0]
        with open(transcript_file, 'r', encoding='utf-8') as ifile:
            transcript = ifile.read()
        yield BatchItem(id=dt, text=transcript, helper=helper)
        
