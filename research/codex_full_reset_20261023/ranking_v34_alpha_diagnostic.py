#!/usr/bin/env python3
from __future__ import annotations
import json,math,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13
import research.codex_full_reset_20261023.ranking_v30_fragile_strong_risk as v30

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v34_alpha_diagnostic_result.json'

SIGNAL_DATES=sorted(e['signal_date'] for e in v30.EV)
IDX={d:i for i,d in enumerate(v13.dates)}
NAMES=('residual_reversal','mom20','skip5_60','liquidity','lowvol')


def rank_values(vals):
    a=sorted(vals.items(),key=lambda kv:(kv[1],kv[0]));n=len(a);out={}
    if n<=1:return {k:.5 for k,v in a}
    i=0
    while i<n:
        j=i+1
        while j<n and a[j][1]==a[i][1]:j+=1
        pct=(((i+1)+j)/2-1)/(n-1)
        for k in range(i,j):out[a[k][0]]=pct
        i=j
    return out


def spearman(x,y):
    if len(x)<5:return None
    rx=rank_values({str(i):v for i,v in enumerate(x)})
    ry=rank_values({str(i):v for i,v in enumerate(y)})
    xs=[rx[str(i)] for i in range(len(x))];ys=[ry[str(i)] for i in range(len(y))]
    mx=statistics.mean(xs);my=statistics.mean(ys)
    den=math.sqrt(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))
    return sum((a-mx)*(b-my) for a,b in zip(xs,ys))/den if den>0 else None


def transforms(v):
    rr,m20,sk,liq,lv=v
    trend=(m20+sk)/2
    quality_floor=min(m20,sk,lv)
    consensus=(rr+m20+sk+lv)/4
    residual_trend=rr*trend
    residual_quality=rr*quality_floor
    base=.20*rr+.25*m20+.30*sk+.05*liq+.20*lv
    return {
      'BASE_V6':base,
      'TREND_CONSENSUS':trend,
      'QUALITY_FLOOR':quality_floor,
      'FOUR_FACTOR_CONSENSUS':consensus,
      'RESIDUAL_X_TREND':residual_trend,
      'RESIDUAL_X_QUALITY':residual_quality,
    }

rows=[];daily=[]
for d in SIGNAL_DATES:
    F=v13.features.get(d,{})
    vals=[]
    for t,feat in F.items():
        o=v13.outcome(t,IDX[d])
        if o is None:continue
        fut=o[0]
        tr=transforms(feat)
        row={'date':d,'year':d[:4],'ticker':t,'future_h20_return':fut,'features':dict(zip(NAMES,feat)),'transforms':tr}
        vals.append(row);rows.append(row)
    if len(vals)<20:continue
    rec={'date':d,'year':d[:4],'n':len(vals),'ics':{},'top_decile_spreads':{}}
    keys=list(vals[0]['transforms'])+list(NAMES)
    for k in keys:
        xx=[];yy=[]
        for r in vals:
            x=r['transforms'][k] if k in r['transforms'] else r['features'][k]
            xx.append(x);yy.append(r['future_h20_return'])
        rec['ics'][k]=spearman(xx,yy)
        order=sorted(range(len(xx)),key=lambda i:xx[i]);q=max(1,len(order)//10)
        bot=statistics.mean(yy[i] for i in order[:q]);top=statistics.mean(yy[i] for i in order[-q:])
        rec['top_decile_spreads'][k]=top-bot
    daily.append(rec)

keys=list(daily[0]['ics']) if daily else []
summary={}
for k in keys:
    byyear={}
    for y in ('2024','2025','2026'):
        z=[r['ics'][k] for r in daily if r['year']==y and r['ics'][k] is not None]
        s=[r['top_decile_spreads'][k] for r in daily if r['year']==y]
        byyear[y]={
          'dates':len(z),
          'mean_ic':statistics.mean(z) if z else None,
          'median_ic':statistics.median(z) if z else None,
          'positive_ic_rate':sum(x>0 for x in z)/len(z) if z else None,
          'mean_top_decile_spread':statistics.mean(s) if s else None,
        }
    allz=[r['ics'][k] for r in daily if r['ics'][k] is not None]
    alls=[r['top_decile_spreads'][k] for r in daily]
    summary[k]={
      'all':{
        'dates':len(allz),
        'mean_ic':statistics.mean(allz) if allz else None,
        'median_ic':statistics.median(allz) if allz else None,
        'positive_ic_rate':sum(x>0 for x in allz)/len(allz) if allz else None,
        'mean_top_decile_spread':statistics.mean(alls) if alls else None,
      },
      'years':byyear,
    }

# Stability score rewards positive IC and positive decile spread in every year, without evaluating a portfolio.
def stable_score(k):
    s=summary[k]
    ys=[s['years'][y] for y in ('2024','2025','2026')]
    if any(x['mean_ic'] is None for x in ys):return -999
    worst_ic=min(x['mean_ic'] for x in ys)
    worst_spread=min(x['mean_top_decile_spread'] for x in ys)
    return 2.0*worst_ic + 0.5*worst_spread + s['all']['mean_ic'] + .25*s['all']['positive_ic_rate']

ranking=sorted([{'name':k,'stability_score':stable_score(k),**summary[k]['all'],'years':summary[k]['years']} for k in keys],key=lambda x:(x['stability_score'],x['mean_ic'],x['mean_top_decile_spread']),reverse=True)
res={
 'status':'DIAGNOSTIC_ONLY_NO_PORTFOLIO_EVALUATION',
 'signal_dates':SIGNAL_DATES,
 'date_count':len(SIGNAL_DATES),
 'cross_section_rows':len(rows),
 'horizon_sessions':v13.H,
 'base_features':NAMES,
 'predeclared_transforms':['BASE_V6','TREND_CONSENSUS','QUALITY_FLOOR','FOUR_FACTOR_CONSENSUS','RESIDUAL_X_TREND','RESIDUAL_X_QUALITY'],
 'summary':summary,
 'stability_ranking':ranking,
 'new_model_evaluations':0,
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'Exposed-history signal diagnostics only. No portfolio selection or parameter sweep is performed here; any V34 portfolio rule must be frozen separately before evaluation.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
