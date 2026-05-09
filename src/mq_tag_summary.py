import glob
import json
import os
import re
from collections import defaultdict

from opencc import OpenCC


to_simplified = OpenCC("t2s")


def get_tag_summary(
    prefix='2026_04_24_t0',
    model='deepseek-v4-flash',
    model_class='deepseek-v4-flash',
    classification_prefix='class4',
    batches=range(3),
):
    glob_template = "outputs/model_output/%s_{batch}_%s/*" % (prefix, model)
    raw_by_date = defaultdict(set)
    final_by_date = defaultdict(set)
    norm2raw = defaultdict(set)
    raw2norm = defaultdict(set)

    classification_map = {}
    classification_source = {}

    for f in glob.glob(f'outputs/model_output/{classification_prefix}_{model_class}/*'):
        js = json.load(open(f, 'r'))
        try:
            classifications = js['instruments']
        except Exception:
            os.remove(f)
            print('removed %s' % f)
            continue

        for x in classifications:
            norm_inst = to_simplified.convert(x['raw'])
            tmp = []
            country = '_%s' % x['country']
            if country == '_GLOBAL':
                country = ''
            ticker = x['ticker']
            if ticker:
                ticker = '_%s' % ticker

            for ua in x['underlying_assets']:
                if len(x['underlying_assets']) == 2 and ua == 'fx_usd':
                    continue
                tmp.append('%s%s%s' % (ua, country, ticker))
            classification_map[norm_inst] = tmp.copy()
            classification_source[norm_inst] = os.path.basename(f).split('.')[0]

    for batch in batches:
        pattern = glob_template.format(batch=batch)
        for f in sorted(glob.glob(pattern)):
            f2 = os.path.basename(f)
            date_str = re.findall(r'\d+', f2)[0]
            with open(f, "r", encoding="utf-8-sig") as fp:
                jsrows = json.load(fp)["instruments"]
                for js in jsrows:
                    raw_inst = js['instrument']
                    norm_inst = to_simplified.convert(js['instrument_normalized'])
                    norm2raw[norm_inst].add(raw_inst)
                    raw2norm[raw_inst].add(norm_inst)
                    if norm_inst in classification_map:
                        final_by_date[date_str].update(classification_map[norm_inst])
                    else:
                        raw_by_date[date_str].add(raw_inst)

    return {
        'norm2raw': norm2raw,
        'raw2norm': raw2norm,
        'raw_by_date': raw_by_date,
        'final_by_date': final_by_date,
        'classification_map': classification_map,
        'classification_source': classification_source,
    }

if __name__ == '__main__':
    import pandas as pd

    ret = get_tag_summary('2026_04_24_t0', model_class='deepseek-v4-flash')
    ret2 = get_tag_summary('2026_04_24_t0', model_class='deepseek-v4-pro', classification_prefix='class7')


    df = pd.DataFrame.from_dict(ret['classification_map'], orient='index')
    df2 = pd.DataFrame.from_dict(ret2['classification_map'], orient='index')


    df['test'] = df.index.map(ret['norm2raw'])
    df2['test'] = df2.index.map(ret2['norm2raw'])
    df['source'] = df.index.map(ret['classification_source'])
    df2['source'] = df2.index.map(ret2['classification_source'])

    df3 = df.merge(df2, left_index=True, right_index=True, how='outer', suffixes=['flash', 'pro'])
    df3 = df3.reindex(sorted(df3.columns, key=str), axis=1)
    df3.to_csv('review.csv')