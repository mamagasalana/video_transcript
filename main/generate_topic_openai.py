from src.openai_api import OPENAI_API
import os
from dotenv import load_dotenv

load_dotenv() 
OUTPUT_FOLDER= os.getenv('OUTPUT_FOLDER')
assert OUTPUT_FOLDER , "output folder missing?"

from src.schemas import SCHEMA_DEVELOPER_OPENAI
from template.template import TopicChunks

app = OPENAI_API( TopicChunks, OUTPUT_FOLDER, SCHEMA_DEVELOPER_OPENAI)
for _ in app.run_batch():
    break
    pass
