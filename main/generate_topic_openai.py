from src.openai_api import OPENAI_API
import os
from dotenv import load_dotenv

load_dotenv() 

from src.schemas import SCHEMA_DEVELOPER_OPENAI
from template.template import TopicChunks

app = OPENAI_API( TopicChunks, 'topic', SCHEMA_DEVELOPER_OPENAI)
for _ in app.run_batch(app.iter_items_from_glob(None)):
    break
    pass
