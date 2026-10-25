#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/h3_nonoverlap_robustness_audit_result.json'
V6=(.20,.25,.30,.05,.20)
START='2024-01-01'; END='2026-10-22'; H=3; GATE=.50
COSTS=(0.0,.002,.004,.008)
Z95=1.959963984540054
SEED=20261025; BOOT=10000; BLOCK=5


def wilson_lower(w,n,z=Z95):
    if n<=0:return None
    p=w/n;z2=z*z;den=1+z2/n
    center=p+z2/(2*n);rad=z*math.sqrt(p*(1-p)/n+z2/(4*n*n))
    return (center-rad)/den


def exact_binom_upper(w,n):
    if n<=0:return None
    return sum(math.comb(n,k) for k in range(w,n+1))/(2**n)


def top1(d):
    arr=[]
    for t,vals in v13.features.get(d,{}).items():
        arr.append((sum(V6[i]*vals[i] for i in range(5)),t))
    arr.sort(key=lambda z:(-z[0],z[1]))
    return arr[0] if arr else None


def trade(d,t,score,breadth):
    i=v13.dates.index(d)
    if i+1>=len(v13.dates) or i+H+1>=len(v13.dates):return None
    ed=v13.dates[i+1]; xd=v13.dates[i+H+1]
    e=v13.by[ed].get(t); x=v13.by[xd].get(t)
    if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0 or e.bad or x.bad:return None
    return {'signal_date':d,'entry_date':ed,'exit_date':xd,'ticker':t,'score':score,'breadth20':breadth,'gross_return':x.c/e.o-1}


def schedule():
    out=[];last_exit=None
    for d in v13.dates:
        if d<START or d>END:continue
        if last_exit is not None and d<last_exit:continue
        b=v13.breadth.get(d,0.0)
        if b<GATE:continue
        z=top1(d)
        if not z:continue
        s,t=z;r=trade(d,t,s,b)
        if not r:continue
        out.append(r);last_exit=r['exit_date']
    return out


def stats(rows,cost=0.0):
    xs=[r['gross_return']-cost for r in rows]
    n=len(xs);w=sum(x>0 for x in xs);nav=1.;peak=1.;mdd=0.;loss_streak=0;max_loss_streak=0
    for x in xs:
        nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
        if x<=0:loss_streak+=1;max_loss_streak=max(max_loss_streak,loss_streak)
        else:loss_streak=0
    return {'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,
            'wilson95_lower':wilson_lower(w,n) if n else None,
            'exact_binomial_one_sided_p_vs_50':exact_binom_upper(w,n) if n else None,
            'mean_return':statistics.mean(xs) if xs else None,'median_return':statistics.median(xs) if xs else None,
            'worst_return':min(xs) if xs else None,'best_return':max(xs) if xs else None,
            'compounded_return':nav-1 if n else 0.,'max_drawdown':mdd,'max_nonpositive_streak':max_loss_streak}


def q(sorted_x,p):
    if not sorted_x:return None
    pos=(len(sorted_x)-1)*p;lo=int(math.floor(pos));hi=int(math.ceil(pos))
    if lo==hi:return sorted_x[lo]
    return sorted_x[lo]*(hi-pos)+sorted_x[hi]*(pos-lo)


def bootstrap_mean(xs,cost,block_len=BLOCK):
    vals=[x-cost for x in xs];n=len(vals);rng=random.Random(SEED+int(cost*100000)+block_len)
    iid=[];blk=[]
    for _ in range(BOOT):
        iid.append(sum(vals[rng.randrange(n)] for _ in range(n))/n)
        sample=[]
        while len(sample)<n:
            start=rng.randrange(n)
            for j in range(block_len):
                sample.append(vals[(start+j)%n])
                if len(sample)>=n:break
        blk.append(sum(sample)/n)
    iid.sort();blk.sort()
    return {'iterations':BOOT,'seed':SEED,'block_length_trades':block_len,
            'iid_mean_ci90':[q(iid,.05),q(iid,.95)],'iid_mean_ci95':[q(iid,.025),q(iid,.975)],
            'moving_block_mean_ci90':[q(blk,.05),q(blk,.95)],'moving_block_mean_ci95':[q(blk,.025),q(blk,.975)],
            'moving_block_prob_mean_le_0':sum(x<=0 for x in blk)/BOOT}

rows=schedule();gross_returns=[r['gross_return'] for r in rows]
combined={str(c):stats(rows,c) for c in COSTS}
by_year={}
for y in ('2024','2025','2026'):
    yr=[r for r in rows if r['signal_date'].startswith(y)]
    by_year[y]={str(c):stats(yr,c) for c in COSTS}

half_year={}
for y in ('2024','2025','2026'):
    for half,months in [('H1',range(1,7)),('H2',range(7,13))]:
        rr=[r for r in rows if r['signal_date'].startswith(y) and int(r['signal_date'][5:7]) in months]
        half_year[f'{y}{half}']=stats(rr,0.0)

leave_one_year_out={}
for y in ('2024','2025','2026'):
    rr=[r for r in rows if not r['signal_date'].startswith(y)]
    leave_one_year_out[y]=stats(rr,0.0)

best_i=max(range(len(rows)),key=lambda i:rows[i]['gross_return']);worst_i=min(range(len(rows)),key=lambda i:rows[i]['gross_return'])
remove_best=stats([r for i,r in enumerate(rows) if i!=best_i],0.0)
remove_worst=stats([r for i,r in enumerate(rows) if i!=worst_i],0.0)
boot={str(c):bootstrap_mean(gross_returns,c) for c in (0.0,.002,.004)}

gross=combined['0.0'];c20=combined['0.002'];c40=combined['0.004']
directional_significant=(gross['wilson95_lower'] is not None and gross['wilson95_lower']>.50 and gross['exact_binomial_one_sided_p_vs_50']<.05)
return_magnitude_supported=(c20['mean_return']>0 and boot['0.002']['moving_block_mean_ci90'][0]>0)
remove_best_positive=(remove_best['mean_return'] is not None and remove_best['mean_return']>0 and remove_best['compounded_return']>0)
if directional_significant and return_magnitude_supported and remove_best_positive:
    diagnosis='H3_DIRECTION_AND_RETURN_SUPPORTED'
elif return_magnitude_supported and remove_best_positive:
    diagnosis='H3_RETURN_EDGE_ONLY_DIRECTION_NOT_SIGNIFICANT'
else:
    diagnosis='H3_ROBUSTNESS_NOT_CONFIRMED'

res={
 'status':'H3_NONOVERLAP_ROBUSTNESS_AUDIT_COMPLETE','diagnosis':diagnosis,
 'objective':'fixed H3 STRONG single-position robustness audit; quantify whether the observed 55% point win rate is statistically distinguishable from 50% and whether return magnitude survives dependence-aware stress',
 'fixed_rule':'V6 Top1 weights (0.20,0.25,0.30,0.05,0.20); breadth20>=0.50; signal after t close; enter t+1 open; exit t+4 close; strict single-position non-overlap',
 'period':f'{START} through {END}','combined':combined,'years':by_year,'half_years':half_year,
 'leave_one_year_out':leave_one_year_out,
 'sensitivity':{'remove_best_trade':remove_best,'removed_best_trade':rows[best_i],
                'remove_worst_trade':remove_worst,'removed_worst_trade':rows[worst_i]},
 'bootstrap_mean':boot,
 'tests':{'directional_significant_5pct':directional_significant,
          'return_magnitude_supported_90pct_block_bootstrap_after_20bp':return_magnitude_supported,
          'remove_best_trade_still_positive':remove_best_positive},
 'interpretation_guards':[
   'No signal, horizon, breadth gate, scheduler, cost level, or significance threshold is tuned in this audit.',
   'Exact binomial test addresses directional hit rate versus 50%; moving-block bootstrap with fixed 5-trade blocks addresses mean-return uncertainty under local serial dependence.',
   'This historical archive is already exposed; statistical support here is descriptive research evidence, not untouched future OOS and not a guarantee.'
 ],
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False}
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('===H3_NONOVERLAP_ROBUSTNESS_AUDIT===')
print(json.dumps(res,ensure_ascii=False,indent=2))
