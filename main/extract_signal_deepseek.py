from src.openai_api import OPENAI_API_DEEPSEEK
import os
from dotenv import load_dotenv

load_dotenv() 

from src.schemas import SCHEMA_SIGNAL_RULES2 as rule
from template.template import TradingSignal

app = OPENAI_API_DEEPSEEK(TradingSignal, 'signal_deepseek', rule)
for _ in app.run_batch('transcript2/202007*.txt'):
    # break
    pass
