#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

import research.codex_full_reset_20261023.nextday_o3_delayed_close_overnight as o3

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research' / 'codex_full_reset_20261023' / 'nextday_o3_robustness_audit_result.json'
COST = o3.PRIMARY_COST
PERIODS = {
    '2024_DEV': o3.DEV,
    '2025_REUSED_VALIDATION': o3.VAL,
    '2026_DIAGNOSTIC': o3.DIAG,
}


def in_period(r,p):
    return p[0] <= r['signal_date'] <= p[1]

def wr(xs):
    return sum(x > 0 for x in xs)/len(xs) if xs else None

def basic(rs):
    xs=[r['gross_return']-COST for r in rs]
    if not xs:
        return {'n':0}
    c=Counter(r['ticker'] for r in rs)
    return {
        'n':len(xs),'wins':sum(x>0 for x in xs),'win_rate':wr(xs),
        'mean':statistics.mean(xs),'median':statistics.median(xs),
        'worst':min(xs),'best':max(xs),
        'top_ticker':c.most_common(1)[0][0],
        'top_ticker_count':c.most_common(1)[0][1],
        'top_ticker_share':c.most_common(1)[0][1]/len(xs),
        'unique_tickers':len(c),
    }

def remove_best(rs,k):
    return sorted(rs,key=lambda r:r['gross_return']-COST,reverse=True)[k:]

def remove_worst(rs,k):
    return sorted(rs,key=lambda r:r['gross_return']-COST)[k:]

def remove_tickers(rs,tickers):
    s=set(tickers)
    return [r for r in rs if r['ticker'] not in s]

def top_freq_tickers(rs,n):
    return [t for t,_ in Counter(r['ticker'] for r in rs).most_common(n)]

def winsor(xs,lo=.05,hi=.95):
    if not xs:return None
    a=sorted(xs); n=len(a)
    qlo=a[min(n-1,max(0,math.ceil(lo*n)-1))]
    qhi=a[min(n-1,max(0,math.ceil(hi*n)-1))]
    ys=[min(max(x,qlo),qhi) for x in xs]
    return {'q05':qlo,'q95':qhi,'mean':statistics.mean(ys),'median':statistics.median(ys)}

def trimmed(xs,frac=.05):
    if not xs:return None
    a=sorted(xs); k=int(len(a)*frac)
    b=a[k:len(a)-k] if k and len(a)>2*k else a
    return {'removed_each_tail':k,'n':len(b),'mean':statistics.mean(b),'median':statistics.median(b),'win_rate':wr(b)}

def quarter_key(d):
    y=int(d[:4]); m=int(d[5:7]); q=(m-1)//3+1
    return f'{y}Q{q}'

def month_key(d):
    return d[:7]

def grouped(rs,keyfn):
    g=defaultdict(list)
    for r in rs:g[keyfn(r['signal_date'])].append(r)
    return {k:basic(v) for k,v in sorted(g.items())}

# Selected O3 robustness by year.
selected={k:[r for r in o3.selected if in_period(r,p)] for k,p in PERIODS.items()}
rob={}
for label,rs in selected.items():
    xs=[r['gross_return']-COST for r in rs]
    top1=top_freq_tickers(rs,1); top3=top_freq_tickers(rs,3)
    rob[label]={
        'base':basic(rs),
        'ticker_frequency':Counter(r['ticker'] for r in rs).most_common(15),
        'leave_top_frequency_1_out':basic(remove_tickers(rs,top1)),
        'leave_top_frequency_3_out':basic(remove_tickers(rs,top3)),
        'remove_best_1_trade':basic(remove_best(rs,1)),
        'remove_best_3_trades':basic(remove_best(rs,3)),
        'remove_best_5_trades':basic(remove_best(rs,5)),
        'remove_worst_3_trades':basic(remove_worst(rs,3)),
        'winsor_5_95':winsor(xs),
        'trim_5pct_each_tail':trimmed(xs),
        'quarters':grouped(rs,quarter_key),
        'months':grouped(rs,month_key),
    }

# Pooled 2024+2025 concentration and tail dependence.
pre=[r for r in o3.selected if o3.DEV[0] <= r['signal_date'] <= o3.VAL[1]]
pre_x=[r['gross_return']-COST for r in pre]
pre_top1=top_freq_tickers(pre,1); pre_top3=top_freq_tickers(pre,3); pre_top5=top_freq_tickers(pre,5)
pooled={
    'base':basic(pre),
    'ticker_frequency':Counter(r['ticker'] for r in pre).most_common(20),
    'leave_top_frequency_1_out':basic(remove_tickers(pre,pre_top1)),
    'leave_top_frequency_3_out':basic(remove_tickers(pre,pre_top3)),
    'leave_top_frequency_5_out':basic(remove_tickers(pre,pre_top5)),
    'remove_best_1_trade':basic(remove_best(pre,1)),
    'remove_best_3_trades':basic(remove_best(pre,3)),
    'remove_best_5_trades':basic(remove_best(pre,5)),
    'remove_best_10_trades':basic(remove_best(pre,10)),
    'winsor_5_95':winsor(pre_x),
    'trim_5pct_each_tail':trimmed(pre_x),
}

# Base-rate / ranking decomposition. All eligible raw stock-days, then daily top-1, then threshold-selected.
def period_stats(rs,p):
    return basic([r for r in rs if in_period(r,p)])

base_rate={}
for label,p in PERIODS.items():
    all_rows=[r for r in o3.scored if in_period(r,p)]
    daily=[r for r in o3.daily if in_period(r,p)]
    sel=[r for r in o3.selected if in_period(r,p)]
    base_rate[label]={
        'all_eligible_stock_days':basic(all_rows),
        'daily_top1_by_o3_score':basic(daily),
        'threshold_selected':basic(sel),
        'daily_top1_lift_win_pp':(basic(daily)['win_rate']-basic(all_rows)['win_rate'])*100 if all_rows and daily else None,
        'selected_lift_win_pp':(basic(sel)['win_rate']-basic(all_rows)['win_rate'])*100 if all_rows and sel else None,
        'daily_top1_lift_mean_pp':(basic(daily)['mean']-basic(all_rows)['mean'])*100 if all_rows and daily else None,
        'selected_lift_mean_pp':(basic(sel)['mean']-basic(all_rows)['mean'])*100 if all_rows and sel else None,
    }

# Score monotonicity among the daily top-1 stream; fixed bins by within-year rank only for diagnosis.
def score_bands(rs,bins=5):
    if not rs:return []
    a=sorted(rs,key=lambda r:r['o3_score'])
    out=[]
    for i in range(bins):
        lo=math.floor(i*len(a)/bins); hi=math.floor((i+1)*len(a)/bins)
        g=a[lo:hi]
        if not g:continue
        b=basic(g)
        out.append({'band':i+1,'score_min':min(r['o3_score'] for r in g),'score_max':max(r['o3_score'] for r in g),**b})
    return out
score_monotonicity={label:score_bands([r for r in o3.daily if in_period(r,p)]) for label,p in PERIODS.items()}

# Market-state drift: selected-vs-all means of input features. No tuning/promotion is allowed from this audit.
def feature_means(rs):
    if not rs:return {}
    return {k:statistics.mean(r[k] for r in rs) for k in o3.FEATURES}
def feature_stdev(rs):
    if len(rs)<2:return {}
    return {k:statistics.pstdev(r[k] for r in rs) for k in o3.FEATURES}
regime={}
for label,p in PERIODS.items():
    allr=[r for r in o3.scored if in_period(r,p)]
    sel=[r for r in o3.selected if in_period(r,p)]
    regime[label]={
        'all_feature_mean':feature_means(allr),
        'all_feature_stdev':feature_stdev(allr),
        'selected_feature_mean':feature_means(sel),
        'selected_feature_stdev':feature_stdev(sel),
    }

# Conservative diagnostic flags; never a promotion decision.
pre_remove5=pooled['remove_best_5_trades']
pre_loo3=pooled['leave_top_frequency_3_out']
flags={
    'pre2026_mean_positive_after_removing_best5': pre_remove5['mean'] is not None and pre_remove5['mean']>0,
    'pre2026_win_rate_gte_0_60_after_removing_best5': pre_remove5['win_rate'] is not None and pre_remove5['win_rate']>=.60,
    'pre2026_mean_positive_after_removing_top3_frequent_tickers': pre_loo3['mean'] is not None and pre_loo3['mean']>0,
    'pre2026_win_rate_gte_0_60_after_removing_top3_frequent_tickers': pre_loo3['win_rate'] is not None and pre_loo3['win_rate']>=.60,
    '2026_selected_mean_positive': rob['2026_DIAGNOSTIC']['base']['mean'] is not None and rob['2026_DIAGNOSTIC']['base']['mean']>0,
    '2026_selected_win_rate_gte_0_55': rob['2026_DIAGNOSTIC']['base']['win_rate'] is not None and rob['2026_DIAGNOSTIC']['base']['win_rate']>=.55,
}

res={
    'status':'DIAGNOSTIC_ONLY_NO_MODEL_SELECTION',
    'source_run':40192720652,
    'source_artifact':12598747049,
    'source_status':o3.res['status'],
    'primary_cost':COST,
    'selected_robustness':rob,
    'pre2026_pooled_robustness':pooled,
    'base_rate_and_ranking_lift':base_rate,
    'daily_top1_score_monotonicity':score_monotonicity,
    'feature_regime_drift':regime,
    'diagnostic_flags':flags,
    'research_boundary':'Audit only. 2025/2026 are already exposed in the broader project. This script must not be used to claim a newly pristine holdout-qualified strategy or to tune a promoted rule.',
    'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('O3_AUDIT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
