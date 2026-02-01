import pandas as pd
import json
import glob
import re
import os

def compile(glob_pattern):
    dfs =[]
    for f in glob.glob(glob_pattern):
        dt = re.findall(r'\d+', os.path.basename(f))[0]
        df  =pd.DataFrame(json.load(open(f, 'r'))['signals'])
        df['dt'] =dt
        dfs.append(df)
    ret = pd.concat(dfs, ignore_index=True)
    return ret


compare = ['signal_with_instrument_openai', 'signal_with_instrument_deepseek' ]
df1 = compile(f'outputs/model_output/{compare[0]}/*.json')
df2 = compile(f'outputs/model_output/{compare[1]}/*.json')

print(len(df1), len(df2))
SELECTED_COLUMNS = ['dt', 'instrument', 'instrument_normalized', 'intent', 'trading_window']
INDEX_COLUMNS = ['dt', 'instrument', 'instrument_normalized']

df1[SELECTED_COLUMNS].merge(
    df2[SELECTED_COLUMNS], 
    how='outer', 
    left_on=INDEX_COLUMNS, 
    right_on=INDEX_COLUMNS, 
    suffixes=[ '_%s' % x for x in compare]).to_csv('comparison.csv', index=False)

