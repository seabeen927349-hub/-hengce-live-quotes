#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, statistics
from pathlib import Path

# Import B1 only to reuse the exact same precomputed signal-date universe/outcome
# mechanics, making this an apples-to-apples control. B1 scores/selections are never used.
import research.codex_full_reset_20261023.nextday_b1_consensus_basket as b1

ROOT=Path(__file__).resolve().parents[2]
RESET=ROOT/'research'/'codex_full_reset_20261023'
OUT=RESET/'nextday_c0_random_basket_control_result.json'
PRIMARY_COST=0.002
COSTS=(0.0,0.002,0.004,0.006,0.008)
SEEDS=tuple(range(32))
BASKET_SIZE=5
PERIODS={'2024':b1.DEV,'2025':b1.VAL,'2026':b1.DIAG}


def hkey(seed,d,t):
    return hashlib.sha256(f'C0|{seed}|{d}|{t}'.encode()).digest()

def split(rs,p):return[r for r in rs if p[0]<=r['signal_date']<=p[1]]
def metric(rs,cost):
    xs=[r['gross_return']-cost for r in rs];n=len(xs);w=sum(x>0 for x in xs)
    return {'nights':n,'wins':w,'win_rate':w/n if n else None,'mean_return':statistics.mean(xs) if xs else None,'median_return':statistics.median(xs) if xs else None}

# Full-universe equal-weight benchmark: no stock selection at all.
market=[]
for d,p in sorted(b1.panels.items()):
    if d<b1.DEV[0]:continue
    xs=p['stocks']
    if len(xs)<BASKET_SIZE:continue
    market.append({'signal_date':d,'gross_return':statistics.mean(s['gross_return'] for s in xs),'count':len(xs)})

# 32 deterministic feature-blind five-stock portfolios. Membership is decided only
# by (seed, signal_date, ticker), never by prices, scores, or future return.
seed_rows={}
for seed in SEEDS:
    rs=[]
    for d,p in sorted(b1.panels.items()):
        if d<b1.DEV[0]:continue
        xs=p['stocks']
        if len(xs)<BASKET_SIZE:continue
        chosen=sorted(xs,key=lambda s:hkey(seed,d,s['ticker']))[:BASKET_SIZE]
        rs.append({'signal_date':d,'gross_return':statistics.mean(s['gross_return'] for s in chosen),'tickers':[s['ticker'] for s in chosen]})
    seed_rows[seed]=rs

res={'status':'CONTROL_ONLY','purpose':'Test whether B1-like five-stock overnight hit rates exceed pure diversification / market drift rather than merely reflecting a positive overnight base rate.',
     'basket_size':BASKET_SIZE,'seeds':len(SEEDS),'costs':COSTS,'periods':{},
     'important_limitation':'This shares B1 historical universe construction for apples-to-apples comparison; it is a diagnostic control, not a prospective strategy.'}
for label,p in PERIODS.items():
    full={str(c):metric(split(market,p),c) for c in COSTS}
    random_by_cost={}
    for c in COSTS:
        vals=[]
        for seed in SEEDS:
            m=metric(split(seed_rows[seed],p),c);vals.append({'seed':seed,**m})
        wr=[x['win_rate'] for x in vals if x['win_rate'] is not None];mr=[x['mean_return'] for x in vals if x['mean_return'] is not None]
        vals_sorted=sorted(vals,key=lambda x:(x['win_rate'],x['mean_return']))
        random_by_cost[str(c)]={
          'seed_results':vals,
          'win_rate_min':min(wr),'win_rate_median':statistics.median(wr),'win_rate_max':max(wr),
          'mean_return_min':min(mr),'mean_return_median':statistics.median(mr),'mean_return_max':max(mr),
          'best_seed_by_win_rate':vals_sorted[-1],
        }
    res['periods'][label]={'full_universe_equal_weight':full,'random_five_stock':random_by_cost}

OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('C0_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
