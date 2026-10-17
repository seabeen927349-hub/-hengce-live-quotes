#!/usr/bin/env python3
import json,math
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'execution_realism_2026'/'summary.json';OUT=ROOT/'concentration_stress_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;PART=.10;SLIP=.002;COST=.006
src=json.loads(SRC.read_text(encoding='utf-8'));events=src['events_with_volume']

def simulate(exclude_dates=None,exclude_rank_n=0):
    exclude_dates=set(exclude_dates or [])
    # First derive standalone stressed return and a deterministic profit rank using current starting capital only for exclusion labeling.
    ranked=[]
    for e in events:
        px=e['entry_price']*(1+SLIP);vol=int(e['entry_candle_volume_shares']);desired=(math.floor(START/px)//1000)*1000;maxq=(math.floor(vol*PART)//1000)*1000;q=min(desired,maxq)
        net=e['exit_close']/px-1-COST;ranked.append((q*px*net,e['entry']))
    ranked.sort(reverse=True);exclude_dates|={d for _,d in ranked[:exclude_rank_n]}
    cap=START;curve=[];wins=0
    for e in events:
        if e['entry'] in exclude_dates:continue
        px=e['entry_price']*(1+SLIP);vol=int(e['entry_candle_volume_shares']);desired=(math.floor(cap/px)//1000)*1000;maxq=(math.floor(vol*PART)//1000)*1000;q=min(desired,maxq)
        if q<=0:continue
        net=e['exit_close']/px-1-COST;pnl=q*px*net;cap+=pnl;wins+=net>0;curve.append({'entry':e['entry'],'ticker':e['ticker'],'shares':q,'net':net,'pnl':pnl,'capital':cap})
    return {'final':cap,'ret':cap/START-1,'n':len(curve),'wins':wins,'curve':curve,'excluded':sorted(exclude_dates)}

base=simulate();stress={'base':base}
for n in (1,2,3):stress[f'remove_top_{n}_standalone_pnl']=simulate(exclude_rank_n=n)
months=sorted({e['entry'][:7] for e in events})
for m in months:stress[f'leave_out_{m}']=simulate([e['entry'] for e in events if e['entry'].startswith(m)])
# Also one-event-at-a-time leave-one-event-out, since monthly labels can contain more than one event.
for e in events:stress['leave_out_event_'+e['entry']]=simulate([e['entry']])
summary={'objective':'test whether practical executable profits depend on a few exceptional 2026 trades','contract':{'mode':'boardlot','participation_cap':PART,'slippage':SLIP,'roundtrip_cost':COST},'results':stress}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
