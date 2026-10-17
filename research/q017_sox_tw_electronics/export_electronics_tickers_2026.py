#!/usr/bin/env python3
import csv,json
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'factor_join_2026';OUT.mkdir(parents=True,exist_ok=True)
t={}
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
    t[r['ticker']]=r.get('name','')
keys=sorted(t)
rows=[{'ticker':k,'name':t[k]} for k in keys]
(OUT/'electronics_tickers.json').write_text(json.dumps({'n':len(rows),'tickers':rows},ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'electronics_tickers.txt').write_text(','.join(keys),encoding='utf-8')
print(json.dumps({'n':len(rows),'ticker_csv':','.join(keys)},ensure_ascii=False))
