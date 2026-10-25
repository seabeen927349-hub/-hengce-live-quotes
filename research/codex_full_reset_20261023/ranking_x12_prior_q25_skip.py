#!/usr/bin/env python3
from __future__ import annotations
import copy,json,math,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_x11_tail_confidence_drawdown_gate as x11

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x12_prior_q25_skip_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x12_events.jsonl'
COSTS=(.008,.012,.016)
LOW_Q=.25
MIN_PRIOR=x11.MIN_PRIOR

def quantile(xs,q):
    a=sorted(xs)
    if not a:return None
    if len(a)==1:return a[0]
    z=(len(a)-1)*q;i=int(math.floor(z));j=int(math.ceil(z))
    if i==j:return a[i]
    return a[i]*(j-z)+a[j]*(z-i)

def build():
    out=[];prior=[];log=[]
    for e0 in sorted(x11.EV,key=lambda e:e['signal_date']):
        e=copy.deepcopy(e0)
        raw=e['x10_confidence_multiplier']
        q25=quantile(prior,LOW_Q) if len(prior)>=MIN_PRIOR else None
        take=(q25 is None or raw>=q25)
        e['x12_prior_multiplier_q25']=q25
        e['x12_take_trade']=take
        e['x12_pre_skip_exposure']=e['exposure']
        if not take:e['exposure']=0.0
        e['ranking_rule']='X12_EXACT_X11_WITH_EXPANDING_PRIOR_Q25_LOW_CONFIDENCE_SKIP'
        out.append(e)
        log.append({'signal_date':e['signal_date'],'raw_x10_multiplier':raw,'prior_multiplier_q25':q25,'take_trade':take,'pre_skip_exposure':e['x12_pre_skip_exposure'],'final_exposure':e['exposure']})
        prior.append(raw)
    return out,log

def product(xs):
    n=1.0
    for x in xs:n*=1+x
    return n-1

def summarize(events,cost):
    nets=[];active=[];nav=1.;peak=1.;mdd=0.
    for e in events:
        ex=e['exposure'];net=ex*(e['gross_return']-cost);nets.append(net);b=nav
        if ex>1e-12:active.append(net)
        for j,(d,r) in enumerate(e['daily']):
            temp=b*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=b*(1+net)
    bi=max(range(len(active)),key=lambda k:active[k]) if active else None
    return {'scheduled_baskets':len(events),'active_trades':len(active),'wins':sum(x>0 for x in active),'win_rate':sum(x>0 for x in active)/len(active) if active else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_active_trade_return':product([x for k,x in enumerate(active) if k!=bi]) if bi is not None and len(active)>1 else None,'mean_active_net_return':statistics.mean(active) if active else None,'best_active_trade_net':max(active) if active else None,'worst_active_trade_net':min(active) if active else None,'max_single_name_weight':max((max(e['weights']) for e in events if e['exposure']>1e-12),default=None),'mean_exposure_all_schedule':statistics.mean([e['exposure'] for e in events]) if events else None}

EV,GATE_LOG=build();complete=(len(EV)==len(x11.EV));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in x11.x10.v43.v41.v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_active_trade_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
x11ref=x11.combined['0.012'];c=combined['0.012'];dominates=robust and c['compounded_return']>x11ref['compounded_return'] and c['max_drawdown']>=x11ref['max_drawdown'] and c['remove_best_active_trade_return']>x11ref['remove_best_basket_return'] and c['win_rate']>x11ref['win_rate']
status='X12_STRICTLY_DOMINATES_X11_AND_RAISES_WIN_RATE' if dominates else 'X12_DOES_NOT_STRICTLY_DOMINATE_X11'
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed X12: retain exact X11/V43 scheduled baskets and X11 exposure logic, but skip the trade entirely when current X10 confidence multiplier is below the expanding prior-only 25th percentile after the same four-observation minimum used by the existing tail-risk layer. No future outcomes used; skipped dates remain in schedule with zero exposure.','low_quantile':LOW_Q,'min_prior_multipliers':MIN_PRIOR,'complete_common_schedule':complete,'invalid':[],'robust':robust,'gate_log':GATE_LOG,'years':years,'combined':combined,'x11_reference':x11ref,'strictly_dominates_x11_and_raises_win_rate':dominates,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One fixed exposed-history trade-selection hypothesis motivated by weak-confidence filtering. Exact X11 stock picks, weights, H20 schedule, costs and upstream risk controls retained; no grid or parameter scan.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
