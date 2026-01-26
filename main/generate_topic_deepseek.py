from src.openai_api import OPENAI_API
from dotenv import load_dotenv

load_dotenv() 

from src.schemas import SCHEMA_DEVELOPER_DEEPSEEK as schema
from template.template import TopicChunks_deepseek as ts

app = OPENAI_API( ts, 'topic_deepseek', schema)
for _ in app.run_batch('transcript2/202007*.txt'):
    # break
    pass
