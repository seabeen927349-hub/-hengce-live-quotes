#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v21_dual_sleeve_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v21_events.jsonl'
COSTS=(.008,.012,.016)
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}

TOP3,inv3=v19.build_variant(3,'INV_VOL')
TOP5,inv5=v19.build_variant(5,'INV_VOL')
M3={e['signal_date']:e for e in TOP3};M5={e['signal_date']:e for e in TOP5}
common=sorted(set(M3)&set(M5))
invalid=list(inv3)+list(inv5)
BLEND=[]
for d in common:
    a,b=M3[d],M5[d]
    if a['entry_date']!=b['entry_date'] or a['exit_date']!=b['exit_date'] or len(a['daily'])!=len(b['daily']):
        invalid.append([d,'PATH_MISMATCH']);continue
    daily=[]
    ok=True
    for x,y in zip(a['daily'],b['daily']):
        if x[0]!=y[0]:ok=False;break
        daily.append([x[0],.5*x[1]+.5*y[1]])
    if not ok:
        invalid.append([d,'DAILY_DATE_MISMATCH']);continue
    e={'signal_date':d,'entry_date':a['entry_date'],'exit_date':a['exit_date'],'tickers_top3':a['tickers'],'weights_top3':a['weights'],'tickers_top5':b['tickers'],'weights_top5':b['weights'],'gross_return':.5*a['gross_return']+.5*b['gross_return'],'daily':daily,'regime':a['regime'],'breadth20':a['breadth20'],'year':a['year'],'exposure':a['exposure'],'vol_ratio':a['vol_ratio'],'blend':'50pct_Top3_INV_VOL__50pct_Top5_INV_VOL'}
    BLEND.append(e)
BLEND.sort(key=lambda e:e['signal_date'])

complete=(not invalid and len(BLEND)==len(v19.v15.base))
years={y:{str(c):v19.summarize([e for e in BLEND if e['year']==y],c) for c in COSTS} for y in v19.v15.v13.PERIODS}
combined={str(c):v19.summarize(BLEND,c) for c in COSTS}
m12=[years[y]['0.012'] for y in v19.v15.v13.PERIODS];m16=[years[y]['0.016'] for y in v19.v15.v13.PERIODS]
robust=complete and all(x['compounded_return']>0 and x['remove_best_basket_return']>0 for x in m12) and all(x['compounded_return']>0 for x in m16)
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in BLEND:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
c=combined['0.012'];strict=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'];risk=robust and c['max_drawdown']>=-.20 and c['compounded_return']>=1.90 and c['remove_best_basket_return']>=.90
status='V21_STRICTLY_DOMINATES_V19' if strict else ('V21_MATERIAL_RISK_IMPROVEMENT' if risk else 'V21_DOES_NOT_BEAT_V19')
res={'status':status,'method':'single fixed 50/50 capital blend of V19 Top3 inverse-vol and Top5 inverse-vol on identical V19 signal dates; V17 exposure and H20 unchanged','complete_common_schedule':complete,'invalid':invalid,'years':years,'combined':combined,'v19_reference':V19_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Single historical blend candidate evaluated on exposed 2024-2026 data; not pristine OOS.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
