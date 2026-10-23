#!/usr/bin/env python3
from __future__ import annotations
import runpy,json,statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'research/codex_full_reset_20261023/ranking_v13_weak_regime_profiles.py'
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v14_strong_regime_profiles_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v14_champion_events.jsonl'
ns=runpy.run_path(str(BASE))
features=ns['features'];breadth=ns['breadth'];V6=tuple(ns['V6']);CUT=ns['BREADTH_CUTOFF'];PERIODS=ns['PERIODS'];COSTS=ns['COSTS'];simulate=ns['simulate'];summarize=ns['summarize']
V6_REF={'combined_return_012':2.502731886924238,'combined_maxdd_012':-0.40608721504832834}
STRONG_PROFILES={
 'V6':V6,
 'TREND_HEAVY':(.05,.30,.45,.05,.15),
 'MOMENTUM_LOWVOL':(.05,.35,.35,.05,.20),
 'SKIP_HEAVY':(.10,.20,.45,.05,.20),
 'LIQ_TREND':(.10,.25,.35,.15,.15),
 'BALANCED':(.15,.25,.35,.05,.20),
}

def make_cache(strongw):
 cache={}
 for d,F in features.items():
  w=strongw if breadth[d]>=CUT else V6
  arr=[(sum(w[i]*v[i] for i in range(5)),t) for t,v in F.items()]
  arr.sort(key=lambda z:(-z[0],z[1]));cache[d]=[t for s,t in arr]
 return cache

results=[]
for name,w in STRONG_PROFILES.items():
 cache=make_cache(w);years={};all_ev=[];cens=0
 for y,(s,e) in PERIODS.items():
  ev,c=simulate(cache,s,e);cens+=c
  for x in ev:x['year']=y
  all_ev.extend(ev);years[y]={str(cost):summarize(ev,cost) for cost in COSTS}
 combined={str(cost):summarize(sorted(all_ev,key=lambda z:z['signal_date']),cost) for cost in COSTS}
 m12=[years[y]['0.012'] for y in PERIODS];m16=[years[y]['0.016'] for y in PERIODS]
 enough=all(x['baskets']>=7 for x in m12);worst=min(x['compounded_return'] for x in m12);worst16=min(x['compounded_return'] for x in m16);minrem=min(x['remove_best_basket_return'] for x in m12);worstdd=min(x['max_drawdown'] for x in m12);avgwin=statistics.mean(x['win_rate'] for x in m12)
 robust=enough and worst>0 and worst16>0 and minrem>0
 obj=2.2*worst+.4*combined['0.012']['compounded_return']+.8*minrem+.5*avgwin+1.2*worstdd+1.0*combined['0.012']['max_drawdown']+.25*worst16
 results.append({'strong_profile':name,'strong_weights':w,'years':years,'combined':combined,'robust':robust,'worst_year_return_012':worst,'worst_year_return_016':worst16,'min_remove_best_012':minrem,'objective':obj,'regime_return_012':{g:summarize([x for x in all_ev if x['regime']==g],.012) for g in ('STRONG','WEAK')},'censored':cens})
rob=[r for r in results if r['robust']];pool=rob or results;pool.sort(key=lambda r:(r['objective'],r['combined']['0.012']['compounded_return']),reverse=True);champ=pool[0]
cache=make_cache(tuple(champ['strong_weights']));cev=[]
for y,(s,e) in PERIODS.items():
 ev,_=simulate(cache,s,e)
 for x in ev:x['year']=y
 cev.extend(ev)
with EVENTS.open('w',encoding='utf-8') as fh:
 for e in cev:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
cr=champ['combined']['0.012']['compounded_return'];cd=champ['combined']['0.012']['max_drawdown']
strict_dom=champ['strong_profile']!='V6' and champ['robust'] and cr>V6_REF['combined_return_012'] and cd>V6_REF['combined_maxdd_012']
status='V14_DOMINATES_V6' if strict_dom else 'V14_DOES_NOT_BEAT_V6'
res={'status':status,'method':'weak-breadth frozen V6 plus finite strong-breadth trend-profile comparison','breadth_cutoff':CUT,'weak_weights':V6,'strong_profiles':STRONG_PROFILES,'champion':champ,'all_results':results,'v6_reference':V6_REF,'new_model_evaluations':len(results),'events_file':str(EVENTS.relative_to(ROOT)),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Strong-profile choice is screened on exposed 2024-2026 history; baseline V6 is not counted as an improvement.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
