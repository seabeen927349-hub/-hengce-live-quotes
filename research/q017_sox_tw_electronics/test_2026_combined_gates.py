#!/usr/bin/env python3
import csv,json
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics'); P=ROOT/'residual_gate_2026'/'events.csv'; OUT=ROOT/'combined_gate_2026'; OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.0
rows=[]
for r in csv.DictReader(P.open(encoding='utf-8')):
    for k in ['ret','shock','sox_prevret','sox_ret3','sox_ret5','sox_dd20','beta_mean','gap_mean','expected_gap_mean','residual_mean','residual_min','residual_max']:
        r[k]=float(r[k])
    rows.append(r)

def eq(z):
    c=START;pk=c;dd=0;wins=0
    for e in z:c*=1+e['ret'];pk=max(pk,c);dd=min(dd,c/pk-1);wins+=e['ret']>0
    return {'n':len(z),'wins':wins,'win_rate':wins/len(z) if z else 0,'final':c,'return':c/START-1,'mdd':dd}
sox5_th=[0.00,-0.01,-0.02,-0.03,-0.04,-0.05]
resid_th=[0.00,0.01,0.02,0.025,0.03,0.04]
gap_th=[0.00,-0.01,-0.02,-0.03]
out=[]
for s in sox5_th:
  for rr in resid_th:
    z=[e for e in rows if e['sox_ret5']<=s and e['residual_mean']<=rr]
    x=eq(z);out.append({'kind':'SOX5+RESID','sox5_max':s,'resid_max':rr,'gap_max':'',**x})
for s in sox5_th:
  for g in gap_th:
    z=[e for e in rows if e['sox_ret5']<=s and e['gap_mean']<=g]
    x=eq(z);out.append({'kind':'SOX5+GAP','sox5_max':s,'resid_max':'','gap_max':g,**x})
for s in sox5_th:out.append({'kind':'SOX5_ONLY','sox5_max':s,'resid_max':'','gap_max':'',**eq([e for e in rows if e['sox_ret5']<=s])})
for rr in resid_th:out.append({'kind':'RESID_ONLY','sox5_max':'','resid_max':rr,'gap_max':'',**eq([e for e in rows if e['residual_mean']<=rr])})
valid=[dict(x) for x in out if x['n']>=8]
valid.sort(key=lambda x:(x['return'],x['mdd']),reverse=True)
zone=[dict(x) for x in out if x['kind']=='SOX5+RESID' and x['sox5_max'] in (-.01,-.02,-.03) and x['resid_max'] in (.02,.025,.03) and x['n']>=8]
for x in valid[:15]:
    if x['kind']=='SOX5+RESID':z=[e for e in rows if e['sox_ret5']<=x['sox5_max'] and e['residual_mean']<=x['resid_max']]
    elif x['kind']=='SOX5+GAP':z=[e for e in rows if e['sox_ret5']<=x['sox5_max'] and e['gap_mean']<=x['gap_max']]
    elif x['kind']=='SOX5_ONLY':z=[e for e in rows if e['sox_ret5']<=x['sox5_max']]
    else:z=[e for e in rows if e['residual_mean']<=x['resid_max']]
    mon={}
    for e in z:mon.setdefault(e['entry'][:7],[]).append(e['ret'])
    x['monthly']={m:__import__('math').prod(1+r for r in rs)-1 for m,rs in mon.items()}
summary={'baseline':eq(rows),'tested':len(out),'valid_ge8':len(valid),'top15':valid[:15],'robust_zone':zone}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'grid.csv').open('w',newline='',encoding='utf-8') as f:
    fields=['kind','sox5_max','resid_max','gap_max','n','wins','win_rate','final','return','mdd']
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(out)
print(json.dumps(summary,ensure_ascii=False,indent=2))
