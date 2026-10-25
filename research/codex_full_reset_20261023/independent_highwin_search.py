#!/usr/bin/env python3
from __future__ import annotations

import contextlib, io, json, math, statistics
from pathlib import Path

# Shared PIT price/turnover loader only. No HENGCE score, factor weight, V6 ranking,
# X/V/HR signal, or prior model pick is used to generate trades below.
with contextlib.redirect_stdout(io.StringIO()):
    import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as data

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/INDEPENDENT_HIGHWIN_RESULT_20261025.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/independent_highwin_champion_events.jsonl'
DATES=data.dates; BY=data.by
DI={d:i for i,d in enumerate(DATES)}
TRAIN=('2024-01-01','2024-12-31'); VAL=('2025-01-01','2025-12-31'); PRE=('2024-01-01','2025-12-31'); TEST=('2026-01-01','2026-10-22')
TURNMIN=20_000_000.
HOLDS=(5,10,15,20)
MIN_YEAR_TRADES=30
MIN_PRE_TRADES=80
MAX_PRE_TRADES=125


def ranks(vals):
    # Ascending raw value -> percentile rank, so the largest score receives 1.0.
    a=sorted(vals.items(),key=lambda kv:(kv[1],kv[0])); n=len(a)
    if n<=1:return {t:.5 for t,v in a}
    return {t:i/(n-1) for i,(t,v) in enumerate(a)}

# Build generic daily cross-sectional state from raw returns/volatility/beta/turnover.
STATE={}
for d in DATES:
    e={t:r for t,r in BY[d].items() if not r.bad and r.r5 is not None and r.r20 is not None and r.r60 is not None and r.vol20 is not None and r.turn20 is not None and r.turn20>=TURNMIN}
    if len(e)<20:continue
    lowvol=ranks({t:-r.vol20 for t,r in e.items()}) # high = low vol
    mom20=ranks({t:r.r20 for t,r in e.items()})
    mom60=ranks({t:r.r60 for t,r in e.items()})
    pull5=ranks({t:-r.r5 for t,r in e.items()}) # high = recent pullback
    liq=ranks({t:math.log(max(r.turn20,1.0)) for t,r in e.items()})
    beta={t:(r.beta60 if r.beta60 is not None and math.isfinite(r.beta60) else 1.0) for t,r in e.items()}
    lowbeta=ranks({t:-abs(beta[t]-0.65) for t in e}) # center defensive beta ~0.65
    resid={t:(r.resid5 if r.resid5 is not None and math.isfinite(r.resid5) else r.r5) for t,r in e.items()}
    residpull=ranks({t:-resid[t] for t in e})
    breadth=sum(r.r20>0 for r in e.values())/len(e)
    STATE[d]={'elig':e,'breadth':breadth,'rank':{'lowvol':lowvol,'mom20':mom20,'mom60':mom60,'pull5':pull5,'liq':liq,'lowbeta':lowbeta,'residpull':residpull}}

# Finite hypotheses chosen before checking 2026. All are independent raw-market concepts.
FAMILIES={
 'LOWVOL':{'lowvol':1.0},
 'DEFENSIVE_TREND':{'lowvol':.45,'lowbeta':.20,'mom60':.35},
 'PULLBACK_IN_TREND':{'lowvol':.30,'mom60':.35,'pull5':.35},
 'RESIDUAL_PULLBACK':{'lowvol':.35,'mom60':.25,'residpull':.40},
 'STABLE_MOMENTUM':{'lowvol':.40,'mom20':.30,'mom60':.30},
 'LIQUID_DEFENSIVE':{'lowvol':.40,'lowbeta':.25,'liq':.15,'mom60':.20},
 'BALANCED_INDEPENDENT':{'lowvol':.25,'lowbeta':.15,'mom20':.20,'mom60':.20,'pull5':.20},
}
FILTERS={
 'NONE':lambda r,st:True,
 'R60_POS':lambda r,st:r.r60>0,
 'R20_POS':lambda r,st:r.r20>0,
 'R60_POS_R5_NEG':lambda r,st:r.r60>0 and r.r5<0,
 'R60_POS_R20_POS':lambda r,st:r.r60>0 and r.r20>0,
 'BREADTH_GE50':lambda r,st:st['breadth']>=.50,
 'BREADTH_GE45':lambda r,st:st['breadth']>=.45,
 'BETA_LE1':lambda r,st:r.beta60 is not None and r.beta60<=1.0,
 'TREND_BETA_LE1':lambda r,st:r.r60>0 and r.beta60 is not None and r.beta60<=1.0,
}


def pick(d,fam,flt):
    st=STATE.get(d)
    if not st:return None
    rr=st['rank']; e=st['elig']; w=FAMILIES[fam]; pred=FILTERS[flt]
    arr=[]
    for t,r in e.items():
        if not pred(r,st):continue
        s=sum(ww*rr[k][t] for k,ww in w.items())
        arr.append((s,t))
    if not arr:return None
    arr.sort(key=lambda x:(-x[0],x[1])); return arr[0][1]


def outcome(si,t,h,end):
    ei=si+1; xi=ei+h
    if xi>=len(DATES) or DATES[xi]>end:return None
    er=BY[DATES[ei]].get(t)
    if not er or er.o is None or er.o<=0:return None
    entry=er.o
    for j in range(ei+1,xi+1):
        r=BY[DATES[j]].get(t)
        if not r or r.c is None or r.c<=0 or r.bad:return None
        ret=r.c/entry-1
        if ret>0:return {'win':True,'entry_date':DATES[ei],'exit_date':DATES[j],'entry_open':entry,'exit_close':r.c,'gross_return':ret,'hold':j-ei,'exit_i':j}
    r=BY[DATES[xi]].get(t); ret=r.c/entry-1
    return {'win':ret>0,'entry_date':DATES[ei],'exit_date':DATES[xi],'entry_open':entry,'exit_close':r.c,'gross_return':ret,'hold':h,'exit_i':xi}


def wilson(w,n,z=1.959963984540054):
    if not n:return None
    p=w/n; den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/den


def simulate(rule,start,end,include=False):
    ev=[]; next_free=-1
    for i,d in enumerate(DATES):
        if d<start or d>end or i<next_free:continue
        t=pick(d,rule['family'],rule['filter'])
        if not t:continue
        o=outcome(i,t,rule['hold'],end)
        if not o:continue
        ev.append({'signal_date':d,'ticker':t,'breadth':STATE[d]['breadth'],**o}); next_free=o['exit_i']
    n=len(ev); w=sum(x['win'] for x in ev); rets=[x['gross_return'] for x in ev]
    m={'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson(w,n),
       'mean_gross_return':statistics.mean(rets) if rets else None,'median_gross_return':statistics.median(rets) if rets else None,
       'worst_gross_return':min(rets) if rets else None,'best_gross_return':max(rets) if rets else None,
       'mean_hold':statistics.mean(x['hold'] for x in ev) if ev else None}
    if include:m['events']=ev
    return m

rules=[{'family':f,'filter':g,'hold':h} for f in FAMILIES for g in FILTERS for h in HOLDS]
rows=[]
for rule in rules:
    a=simulate(rule,*TRAIN); b=simulate(rule,*VAL); p=simulate(rule,*PRE)
    if a['trades']<MIN_YEAR_TRADES or b['trades']<MIN_YEAR_TRADES or p['trades']<MIN_PRE_TRADES or p['trades']>MAX_PRE_TRADES:continue
    rows.append({'rule':rule,'development_2024':a,'validation_2025':b,'pre2026':p})

if not rows:raise RuntimeError('No rule met comparable-coverage constraints')
def key(x):
    a=x['development_2024']; b=x['validation_2025']; p=x['pre2026']
    return (min(a['win_rate'],b['win_rate']),b['win_rate'],p['win_rate'],p['wilson95_lower'],-abs(p['trades']-97))
rows.sort(key=key,reverse=True); champ=rows[0]
champ['historical_diagnostic_2026']=simulate(champ['rule'],*TEST)
full=simulate(champ['rule'],*PRE,include=True); tst=simulate(champ['rule'],*TEST,include=True)
with EVENTS.open('w',encoding='utf-8') as fh:
    for label,m in [('PRE2026',full),('2026_DIAGNOSTIC',tst)]:
        for e in m['events']:fh.write(json.dumps({'split':label,**e},ensure_ascii=False)+'\n')

base={'pre2026_trades':97,'pre2026_wins':78,'pre2026_win_rate':78/97,'diagnostic_2026_trades':40,'diagnostic_2026_wins':32,'diagnostic_2026_win_rate':.80}
res={'status':'INDEPENDENT_HIGHWIN_SEARCH_COMPLETE','objective':'independent signal generation maximizing stable gross directional hit rate at 80-125 pre-2026 trades, comparable to 97-trade reference',
 'independence':'Uses only PIT raw price/turnover-derived returns, volatility, beta, liquidity and cross-sectional ranks; does not use HENGCE/V/X/HR picks, scores, factor weights, or the 97 event identities.',
 'protocol':{'development':'2024','validation':'2025','historical_diagnostic':'2026-01-01..2026-10-22','min_trades_each_pre2026_year':MIN_YEAR_TRADES,'pre2026_trade_range':[MIN_PRE_TRADES,MAX_PRE_TRADES],'candidate_rules':len(rules),'selection_key':'maximize weaker of 2024/2025 hit rates, then 2025, pooled, Wilson lower, closeness to 97 trades','entry':'next trading-day open','exit':'first later close strictly above entry open else forced at max hold'},
 'baseline_97_reference':base,'champion':champ,'top20':rows[:20],
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'2026 is not untouched future OOS because the broader project has already exposed it; it is only a historical diagnostic.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('INDEPENDENT_HIGHWIN_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
