from src.openai_api import OPENAI_API_DEEPSEEK
import os
from dotenv import load_dotenv

load_dotenv() 

from src.schemas import SCHEMA_SIGNAL_RULES2 as rule
from template.template import TradingSignal_deepseek as ts

app = OPENAI_API_DEEPSEEK(ts, 'signal2', rule )
for _ in app.run_batch(app.iter_items_from_glob('transcript2/202007*.txt')):
    # break
    pass
