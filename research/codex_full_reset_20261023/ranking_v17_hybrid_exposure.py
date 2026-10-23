#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v15_state_exposure as v15

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v17_hybrid_exposure_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v17_events.jsonl'
COSTS=(.008,.012,.016)
V14={'ret':2.0942494161154364,'dd':-0.29390473237009496,'rem':0.9769276596728977}
V16_PARETO={'ret':2.178473538435324,'dd':-0.29390473237009485,'rem':1.0307387701020279}

def clip(x,lo,hi):return max(lo,min(hi,x))
def vr(e):
 s=v15.state(e);a=s.get('median_vol20');b=s.get('prior60_median_vol20');return a/b if a is not None and b not in (None,0) else 1.0

def exposure(e):
 r=vr(e)
 if e['regime']=='STRONG':return .95 if r>1.10 else 1.0
 return clip(.60/r,.25,1.0)

def product(xs):
 n=1.
 for x in xs:n*=1+x
 return n-1

def summarize(events,cost,emit=False):
 nets=[];nav=1.;peak=1.;mdd=0.;out=[]
 for e in events:
  ex=exposure(e);net=ex*(e['gross_return']-cost);nets.append(net);b=nav
  for j,(d,r) in enumerate(e['daily']):
   temp=b*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
  nav=b*(1+net)
  if emit:
   z=dict(e);z['vol_ratio']=vr(e);z['exposure']=ex;z['scaled_net_return']=net;out.append(z)
 bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
 m={'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}
 if emit:m['events']=out
 return m

years={y:{str(c):summarize([e for e in v15.base if e['year']==y],c) for c in COSTS} for y in v15.v13.PERIODS}
combined={str(c):summarize(v15.base,c) for c in COSTS}
full=summarize(v15.base,.012,True)
with EVENTS.open('w',encoding='utf-8') as fh:
 for e in full['events']:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
m12=[years[y]['0.012'] for y in v15.v13.PERIODS];m16=[years[y]['0.016'] for y in v15.v13.PERIODS]
robust=min(x['compounded_return'] for x in m12)>0 and min(x['compounded_return'] for x in m16)>0 and min(x['remove_best_basket_return'] for x in m12)>0
c=combined['0.012'];dominates_v14=robust and c['compounded_return']>V14['ret'] and c['max_drawdown']>V14['dd'] and c['remove_best_basket_return']>V14['rem']
res={'status':'V17_DOMINATES_V14' if dominates_v14 else 'V17_DOES_NOT_DOMINATE_V14','method':'single fixed hybrid exposure candidate: frozen V6 selection; weak exposure clip(0.60/vol_ratio,0.25,1); strong exposure 0.95 only when vol_ratio>1.10 else 1.0','years':years,'combined':combined,'robust':robust,'v14_reference':V14,'v16_return_pareto_reference':V16_PARETO,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Single candidate chosen after exposed-history V16 diagnostics; not pristine OOS. All exposure variables are signal-time-only.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
