#!/usr/bin/env python3
import csv,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
D=Path(__file__).resolve().parent
cand=[]
with (D/'candidate_dates_localshock.csv').open(encoding='utf-8-sig',newline='') as f:
    cand=[r['date'] for r in csv.DictReader(f)]
mask={}
with (R/'macro/macro_gate_mask_daily.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f): mask[r['date']]=int(r['mask'])
missing=[d for d in cand if d not in mask]
if missing: raise SystemExit('MISSING_MACRO_DATES:'+','.join(missing[:20]))
out=D/'candidate_macro_masks.csv'
with out.open('w',encoding='utf-8',newline='') as f:
    w=csv.writer(f);w.writerow(['date','mask']);w.writerows((d,mask[d]) for d in cand)
rec={'status':'PASS','candidate_count':len(cand),'missing_count':0,'mask_source':'../macro/macro_gate_mask_daily.csv','bits':{'1':'SOX_1D<=0','2':'SOX_5D<=-0.03','4':'DXY_5D>=-0.005'},'thresholds_optimized':False,'causal_source_required':True}
(D/'candidate_macro_masks_receipt.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rec,ensure_ascii=False))
