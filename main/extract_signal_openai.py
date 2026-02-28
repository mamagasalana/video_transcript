from src.openai_api import OPENAI_API
import os
from dotenv import load_dotenv

load_dotenv() 

from src.schemas import SCHEMA_SIGNAL_RULES2 as rule
from template.template import TradingSignal

app = OPENAI_API(TradingSignal, 'signal', rule)
for _ in app.run_batch(app._iter_items_from_glob(None)):
    # break
    pass
