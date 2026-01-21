from src.openai_api import OPENAI_API
import os
from dotenv import load_dotenv

load_dotenv() 
OUTPUT_FOLDER= os.getenv('SIGNAL_FOLDER')
assert OUTPUT_FOLDER , "output folder missing?"

from src.schemas import SCHEMA_SIGNAL_RULES
from template.template import TradingSignal

app = OPENAI_API(TradingSignal, OUTPUT_FOLDER, SCHEMA_SIGNAL_RULES)
for _ in app.run_batch():
    # break
    pass
