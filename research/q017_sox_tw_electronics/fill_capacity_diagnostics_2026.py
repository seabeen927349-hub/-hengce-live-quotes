#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'multiminute_fill_stress_2026'/'summary.json';OUT=ROOT/'fill_capacity_diagnostics_2026';OUT.mkdir(parents=True,exist_ok=True)
x=json.loads(SRC.read_text(encoding='utf-8'))['results']
rows=[]
for key in ('1m_open','3m_open','5m_open','10m_open','5m_high','10m_high'):
    v=x[key]
    for e in v['curve']:
        before=e['capital']-e.get('pnl',0)
        invested=e.get('invested',0)
        rows.append({'variant':key,'entry':e['entry'],'ticker':e['ticker'],'capital_before':before,'invested':invested,'deploy_ratio':invested/before if before else 0,'shares':e['shares'],'fills':len(e.get('fills',[])),'avg_entry':e.get('avg_entry'),'pnl':e.get('pnl'),'capital_after':e['capital']})
# event-level side-by-side
events=[]
for ent in sorted({r['entry'] for r in rows}):
    rec={'entry':ent,'ticker':next(r['ticker'] for r in rows if r['entry']==ent)}
    for key in ('1m_open','3m_open','5m_open','10m_open','5m_high','10m_high'):
        r=next(z for z in rows if z['entry']==ent and z['variant']==key)
        rec[key]={'deploy_ratio':r['deploy_ratio'],'invested':r['invested'],'shares':r['shares'],'fills':r['fills'],'avg_entry':r['avg_entry'],'pnl':r['pnl']}
    events.append(rec)
summary={'objective':'identify which trades actually benefit from wider fill windows','variant_final':{k:x[k]['final'] for k in ('1m_open','3m_open','5m_open','10m_open','5m_high','10m_high')},'events':events,'diagnostic':{'events_under_90pct_deployed_1m':sum(e['1m_open']['deploy_ratio']<.9 for e in events),'events_under_90pct_deployed_5m':sum(e['5m_open']['deploy_ratio']<.9 for e in events),'events_under_90pct_deployed_10m':sum(e['10m_open']['deploy_ratio']<.9 for e in events)}}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
