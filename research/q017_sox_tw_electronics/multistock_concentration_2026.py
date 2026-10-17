#!/usr/bin/env python3
import json,math
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'capacity_aware_multistock_2026'/'summary.json';OUT=ROOT/'multistock_concentration_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.006;N=3
src=json.loads(SRC.read_text(encoding='utf-8'));events=src['event_candidate_snapshot']

def sim(excluded=None):
 excluded=set(excluded or []);cap=START;curve=[]
 for ev in events:
  if ev['entry'] in excluded:continue
  before=cap;remaining=cap;pnl=0;positions=[]
  for rank,c in enumerate(ev['candidates'][:N],1):
   px=c.get('entry_price');cl=c.get('capacity_lots',0)
   if not px or cl<=0:continue
   lots=min(cl,math.floor(remaining/(px*1000)))
   if lots<=0:continue
   inv=lots*1000*px;remaining-=inv;net=c['exit_close']/px-1-COST;pp=inv*net;pnl+=pp
   positions.append({'rank':rank,'ticker':c['ticker'],'lots':lots,'invested':inv,'net':net,'pnl':pp})
  cap+=pnl;curve.append({'entry':ev['entry'],'capital_before':before,'event_pnl':pnl,'capital':cap,'positions':positions})
 return {'final':cap,'ret':cap/START-1,'events':len(curve),'curve':curve}
base=sim();ranked=sorted(base['curve'],key=lambda x:x['event_pnl'],reverse=True)
res={'base':base}
for n in (1,2,3):res[f'remove_top_{n}_events']=sim([x['entry'] for x in ranked[:n]])
for m in sorted({e['entry'][:7] for e in events}):res[f'leave_out_{m}']=sim([e['entry'] for e in events if e['entry'].startswith(m)])
for e in events:res[f'leave_out_event_{e["entry"]}']=sim([e['entry']])
summary={'objective':'test whether capacity-aware Top3 practical profit survives removing dominant events/months','contract':src['contract'],'results':res}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{'final':v['final'],'ret':v['ret'],'events':v['events']} for k,v in res.items() if k=='base' or k.startswith('remove_top_') or k.startswith('leave_out_2026-')},ensure_ascii=False,indent=2))
