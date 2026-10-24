#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v15_state_exposure as v15

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v19_diversification_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v19_champion_events.jsonl'
COSTS=(.008,.012,.016)
VARIANTS=((3,'EW'),(3,'INV_VOL'),(5,'EW'),(5,'INV_VOL'),(8,'EW'),(8,'INV_VOL'))
V17_REF={'ret':2.1215791589270894,'dd':-0.28720698410951295,'rem':1.031059124000596}

cache=v15.v13.make_cache(v15.v13.V6)
idx={d:i for i,d in enumerate(v15.v13.dates)}
base_by_date={e['signal_date']:e for e in v15.base}

def clip(x,lo,hi):return max(lo,min(hi,x))
def vol_ratio(e):
 s=v15.state(e);a=s.get('median_vol20');b=s.get('prior60_median_vol20');return a/b if a is not None and b not in (None,0) else 1.0
def exposure(e):
 r=vol_ratio(e)
 if e['regime']=='STRONG':return .95 if r>1.10 else 1.0
 return clip(.60/r,.25,1.0)

def build_variant(topn,weighting):
 out=[];invalid=[]
 for d in sorted(base_by_date):
  b=base_by_date[d]; ranked=cache.get(d,[]);picks=ranked[:topn]
  if len(picks)<topn:invalid.append([d,'NOT_ENOUGH_PICKS']);continue
  outs=[];ok=True
  for t in picks:
   o=v15.v13.outcome(t,idx[d])
   r=v15.v13.by[d].get(t)
   if o is None or r is None or r.vol20 is None or r.vol20<=0:ok=False;break
   outs.append((t,o,r.vol20))
  if not ok:invalid.append([d,'INVALID_OUTCOME_OR_VOL']);continue
  if weighting=='EW':w=[1/topn]*topn
  else:
   raw=[1/x[2] for x in outs];s=sum(raw);w=[x/s for x in raw]
  gross=sum(wi*o[1][0] for wi,o in zip(w,outs));daily=[]
  for k in range(v15.v13.H+1):
   dd=outs[0][1][3][k][0];dr=sum(wi*o[1][3][k][1] for wi,o in zip(w,outs));daily.append([dd,dr])
  e={'signal_date':d,'entry_date':outs[0][1][1],'exit_date':outs[0][1][2],'tickers':picks,'weights':w,'gross_return':gross,'daily':daily,'regime':b['regime'],'breadth20':b['breadth20'],'year':b['year'],'top_n':topn,'weighting':weighting}
  e['exposure']=exposure(e);e['vol_ratio']=vol_ratio(e)
  out.append(e)
 return out,invalid

def product(xs):
 n=1.
 for x in xs:n*=1+x
 return n-1

def summarize(events,cost):
 nets=[];nav=1.;peak=1.;mdd=0.
 for e in events:
  ex=e['exposure'];net=ex*(e['gross_return']-cost);nets.append(net);b=nav
  for j,(d,r) in enumerate(e['daily']):
   temp=b*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
  nav=b*(1+net)
 bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
 return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}

results=[];event_map={}
for topn,wg in VARIANTS:
 ev,invalid=build_variant(topn,wg);event_map[(topn,wg)]=ev
 years={y:{str(c):summarize([e for e in ev if e['year']==y],c) for c in COSTS} for y in v15.v13.PERIODS}
 combined={str(c):summarize(ev,c) for c in COSTS}
 m12=[years[y]['0.012'] for y in v15.v13.PERIODS];m16=[years[y]['0.016'] for y in v15.v13.PERIODS]
 complete=len(ev)==len(v15.base) and not invalid
 worst=min(x['compounded_return'] for x in m12);worst16=min(x['compounded_return'] for x in m16);minrem=min(x['remove_best_basket_return'] for x in m12);worstdd=min(x['max_drawdown'] for x in m12);avgwin=statistics.mean(x['win_rate'] for x in m12)
 robust=complete and worst>0 and worst16>0 and minrem>0
 c=combined['0.012'];calmar=c['compounded_return']/abs(c['max_drawdown']) if c['max_drawdown']<0 else 999
 obj=.50*c['compounded_return']+1.9*c['max_drawdown']+.85*c['remove_best_basket_return']+1.3*worst+1.1*worstdd+.20*worst16+.30*avgwin+.10*calmar
 results.append({'top_n':topn,'weighting':wg,'invalid':invalid,'complete_common_schedule':complete,'years':years,'combined':combined,'robust':robust,'worst_year_return_012':worst,'worst_year_return_016':worst16,'min_remove_best_012':minrem,'worst_year_maxdd_012':worstdd,'calmar_like':calmar,'objective':obj})

pool=[r for r in results if r['robust']] or results
pool.sort(key=lambda r:(r['objective'],r['calmar_like'],r['combined']['0.012']['compounded_return']),reverse=True);champ=pool[0]
cev=event_map[(champ['top_n'],champ['weighting'])]
with EVENTS.open('w',encoding='utf-8') as fh:
 for e in cev:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
c=champ['combined']['0.012'];strict=champ['robust'] and c['compounded_return']>V17_REF['ret'] and c['max_drawdown']>V17_REF['dd'] and c['remove_best_basket_return']>V17_REF['rem'];risk=champ['robust'] and c['max_drawdown']>=-.25 and c['compounded_return']>=1.80 and c['remove_best_basket_return']>=.90
status='V19_STRICTLY_DOMINATES_V17' if strict else ('V19_MATERIAL_RISK_IMPROVEMENT' if risk else 'V19_DOES_NOT_BEAT_V17')
res={'status':status,'method':'frozen V6 ranking, H20 common signal schedule and V17 exposure; finite TopN x equal/inverse-vol portfolio construction only','variants':[list(x) for x in VARIANTS],'v17_reference':V17_REF,'champion':champ,'all_results':results,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':len(VARIANTS),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Variants screened on exposed 2024-2026 history. Inverse-vol weights use signal-date vol20 only; no cap or tuned weighting exponent.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
