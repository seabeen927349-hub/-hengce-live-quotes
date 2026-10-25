#!/usr/bin/env python3
from __future__ import annotations
import json, statistics
from pathlib import Path
import research.codex_full_reset_20261023.nextday_precision_ceiling as p

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/nextday_precision_failure_audit_result.json'
FEATURE_NAMES=['v6_score','v6_margin','breadth20','resid_rev_rank','mom20_rank','skip5_60_rank','liquidity_rank','lowvol_rank','r1','r5','r20','close_open_body','turn_acc_log','vol20','turnover_log']

pc=p.primary['selected_config']
MODEL=pc['model']; GATE=pc['gate']; THR=pc['threshold']

def select(rows):
    return [r for r in rows if r['breadth20']>=GATE and r['scores'][MODEL]>=THR]

def simple(rows):
    s=p.summarize(rows,0.0)
    return {k:s[k] for k in ('trades','wins','losses','win_rate','wilson95_lower','mean_return','median_return','worst_return','compounded_return','max_drawdown')}

def yr(rows,y):
    a=f'{y}-01-01'; b=f'{y}-12-31'
    return [r for r in rows if a<=r['signal_date']<=b]

def score_stats(rows):
    vals=[r['scores'][MODEL] for r in rows]
    if not vals:return None
    return {'n':len(vals),'mean':statistics.mean(vals),'median':statistics.median(vals),'min':min(vals),'max':max(vals),'q25':p.quantile(vals,.25),'q75':p.quantile(vals,.75)}

def feature_means(rows):
    if not rows:return []
    return [statistics.mean(r['x'][j] for r in rows) for j in range(len(FEATURE_NAMES))]

def feature_drift(a,b):
    ma=feature_means(a); mb=feature_means(b)
    out=[]
    for j,name in enumerate(FEATURE_NAMES):
        out.append({'feature':name,'validation_mean_z':ma[j],'holdout_mean_z':mb[j],'shift_z':mb[j]-ma[j],'abs_shift_z':abs(mb[j]-ma[j])})
    return sorted(out,key=lambda z:-z['abs_shift_z'])

def calibration_bins(valid_pool, hold_pool):
    vals=[r['scores'][MODEL] for r in valid_pool]
    cuts=[p.quantile(vals,q) for q in (.25,.50,.75)]
    bounds=[float('-inf')]+cuts+[float('inf')]
    bins=[]
    for i in range(4):
        lo,hi=bounds[i],bounds[i+1]
        def inbin(r):
            s=r['scores'][MODEL]
            return s>=lo and (s<hi if i<3 else s<=hi)
        vv=[r for r in valid_pool if inbin(r)]
        hh=[r for r in hold_pool if inbin(r)]
        bins.append({'bin':i+1,'score_lo':None if lo==float('-inf') else lo,'score_hi':None if hi==float('inf') else hi,'validation':simple(vv),'holdout':simple(hh)})
    return bins

valid_b60=[r for r in p.valid if r['breadth20']>=GATE]
hold_b60=[r for r in p.hold if r['breadth20']>=GATE]
sel_valid=select(p.valid); sel_hold=select(p.hold)
all_hold=p.hold

baseline={
    'all_holdout_top1_v6':simple(all_hold),
    'b60_holdout_top1_v6':simple(hold_b60),
    'all_2025':simple(yr(all_hold,2025)),
    'all_2026':simple(yr(all_hold,2026)),
    'b60_2025':simple(yr(hold_b60,2025)),
    'b60_2026':simple(yr(hold_b60,2026)),
}
selected={
    'validation_2024':simple(sel_valid),
    'holdout_combined':simple(sel_hold),
    'holdout_2025':simple(yr(sel_hold,2025)),
    'holdout_2026':simple(yr(sel_hold,2026)),
    'score_validation_pool':score_stats(valid_b60),
    'score_holdout_pool':score_stats(hold_b60),
}

# Fixed-rule stress only: same chosen rule, no threshold/model/gate changes.
# Compare whether higher model score remains monotonic in holdout.
cal=calibration_bins(valid_b60,hold_b60)
drift=feature_drift(valid_b60,hold_b60)

vwr=selected['validation_2024']['win_rate']
hwr=selected['holdout_combined']['win_rate']
basewr=baseline['b60_holdout_top1_v6']['win_rate']
if hwr is not None and basewr is not None and hwr < basewr and vwr is not None and vwr-hwr>=0.20:
    diagnosis='VALIDATION_SELECTION_DOES_NOT_GENERALIZE'
elif hwr is not None and basewr is not None and hwr <= basewr:
    diagnosis='NO_INCREMENTAL_HOLDOUT_EDGE'
else:
    diagnosis='SOME_HOLDOUT_EDGE_REMAINS'

res={
    'status':'PRECISION_FAILURE_AUDIT_COMPLETE',
    'diagnosis':diagnosis,
    'frozen_rule':{'model':MODEL,'breadth_gate':GATE,'score_threshold':THR,'source':'precision ceiling primary selected on 2024 only; unchanged here'},
    'selected_rule':selected,
    'baselines':baseline,
    'calibration_quartiles_fixed_from_2024_b60_pool':cal,
    'feature_drift_top10':drift[:10],
    'oracle_reference_from_prior_run':p.oracle.get('30'),
    'interpretation_guards':[
        'No model, gate, score threshold, coverage, or label was tuned in this audit.',
        '2025-2026 remains diagnostic historical holdout within an already-exposed research archive, not future unseen market data.',
        'Post-hoc oracle is descriptive only and cannot be promoted as an OOS model.'
    ],
    'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False}
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('===PRECISION_FAILURE_AUDIT===')
print(json.dumps(res,ensure_ascii=False,indent=2))
