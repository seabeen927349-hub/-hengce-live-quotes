#!/usr/bin/env python3
import json,math
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'capacity_aware_multistock_2026'/'summary.json';OUT=ROOT/'overflow_score_gate_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.006;N=3
src=json.loads(SRC.read_text(encoding='utf-8'));events=src['event_candidate_snapshot']

def sim(ratio):
 cap=START;curve=[];wins=0
 for ev in events:
  before=cap;remaining=cap;pnl=0;pos=[];top=ev['candidates'][0]['score'] if ev['candidates'] else 0
  for rank,c in enumerate(ev['candidates'][:N],1):
   if rank>1 and (top<=0 or c['score']/top<ratio):continue
   px=c.get('entry_price');cl=c.get('capacity_lots',0)
   if not px or cl<=0:continue
   lots=min(cl,math.floor(remaining/(px*1000)))
   if lots<=0:continue
   inv=lots*1000*px;remaining-=inv;net=c['exit_close']/px-1-COST;pp=inv*net;pnl+=pp;wins+=net>0
   pos.append({'rank':rank,'ticker':c['ticker'],'score_ratio':c['score']/top if top else None,'lots':lots,'invested':inv,'net':net,'pnl':pp})
  cap+=pnl;curve.append({'entry':ev['entry'],'capital_before':before,'deploy_ratio':1-remaining/before if before else 0,'event_pnl':pnl,'capital':cap,'positions':pos})
 return {'ratio_gate':ratio,'final':cap,'ret':cap/START-1,'position_wins':wins,'curve':curve}
rows=[sim(r) for r in (0,0.4,0.5,0.6,0.7,0.8,0.9,0.95,1.0)]
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0]
summary={'objective':'avoid wasting overflow capital on materially weaker score candidates','contract':src['contract'],'tested':len(rows),'best':best,'grid':[{k:v for k,v in r.items() if k!='curve'} for r in rows],'best_curve':best['curve']}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary['grid'],ensure_ascii=False,indent=2))
