from __future__ import annotations

import importlib.util
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
OUT=HERE/'results/healthy_market_discovery_20261026'
OUT.mkdir(parents=True,exist_ok=True)

spec=importlib.util.spec_from_file_location('base',HERE/'frozen_3m_to_1y_20261026.py')
base=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(base)
START=pd.Timestamp('2026-07-22'); END=pd.Timestamp('2026-10-21'); COST=.004


def pf(s):
    s=pd.Series(s).dropna(); pos=s[s>0].sum(); neg=-s[s<0].sum()
    if neg==0: return math.inf if pos>0 else None
    return float(pos/neg)


def smry(e,cost=COST):
    if len(e)==0:return {'n':0,'dates':0,'mean':None,'wr':None,'pf':None}
    r=e.gross_ret-cost
    return {'n':int(len(e)),'dates':int(e.Date.nunique()),'mean':float(r.mean()),'median':float(r.median()),'wr':float((r>0).mean()),'pf':pf(r)}


def robustness(e):
    if len(e)==0:return {}
    z=e.assign(net=e.gross_ret-COST)
    dm=z.groupby('Date').net.mean().sort_values(ascending=False)
    rm=set(dm.head(min(3,len(dm))).index)
    dates=sorted(z.Date.unique()); half=len(dates)//2
    return {
      '100bp':smry(e,.010),
      'remove_best_3_dates':smry(e[~e.Date.isin(rm)],COST),
      'first_half_dates':smry(e[e.Date.isin(set(dates[:half]))],COST),
      'second_half_dates':smry(e[e.Date.isin(set(dates[half:]))],COST),
      'monthly':{str(m):smry(g,COST) for m,g in e.groupby(e.Date.dt.to_period('M'))}
    }


def enrich(x):
    x=x.sort_values(['Ticker','Date']).copy(); g=x.groupby('Ticker',group_keys=False)
    for n in [1,3,5,10,20]: x[f'ret{n}']=x.Close/g.Close.shift(n)-1
    for n in [5,10,20]:
        x[f'ma{n}']=g.Close.transform(lambda s,n=n:s.rolling(n,min_periods=n).mean())
        x[f'dist_ma{n}']=x.Close/x[f'ma{n}']-1
    x['ma20_slope5']=x.ma20/g.ma20.shift(5)-1
    x['prev_close']=g.Close.shift(1); x['gap']=x.Open/x.prev_close-1
    x['body']=x.Close/x.Open-1
    rng=(x.High-x.Low).replace(0,np.nan)
    x['close_loc']=(x.Close-x.Low)/rng
    x['range_pct']=rng/x.prev_close
    x['upper_wick']=(x.High-np.maximum(x.Open,x.Close))/rng
    x['lower_wick']=(np.minimum(x.Open,x.Close)-x.Low)/rng
    x['high20']=g.High.transform(lambda s:s.rolling(20,min_periods=20).max())
    x['dist_high20']=x.Close/x.high20-1
    x['volatility10']=g.ret1.transform(lambda s:s.rolling(10,min_periods=10).std())
    x['volatility20']=g.ret1.transform(lambda s:s.rolling(20,min_periods=20).std())
    if 'Volume' in x.columns:
        x['vol20']=g.Volume.transform(lambda s:s.rolling(20,min_periods=20).mean())
        x['vol_ratio20']=x.Volume/x.vol20
    # Cross-sectional relative strength vs same-date median.
    for n in [1,3,5,10,20]:
        med=x.groupby('Date')[f'ret{n}'].transform('median')
        x[f'rel{n}']=x[f'ret{n}']-med
    # future executable outcome
    x['entry_open_t1']=g.Open.shift(-1); x['exit_close_t5']=g.Close.shift(-5)
    x['gross_ret']=x.exit_close_t5/x.entry_open_t1-1
    # market breadth based on this formal TWSE electronics universe
    x['above_ma20']=x.Close>x.ma20
    x['breadth_ma20']=x.groupby('Date').above_ma20.transform('mean')
    return x


def main():
    y=base.load_2026(); x=enrich(y)
    x=x[x.Date.between(START,END)&(x.breadth_ma20>=.50)&x.gross_ret.notna()].copy()
    feats=['ret1','ret3','ret5','ret10','ret20','dist_ma5','dist_ma10','dist_ma20','ma20_slope5','gap','body','close_loc','range_pct','upper_wick','lower_wick','dist_high20','volatility10','volatility20','rel1','rel3','rel5','rel10','rel20']
    if 'vol_ratio20' in x.columns:feats.append('vol_ratio20')
    for f in feats:x[f+'_rank']=x.groupby('Date')[f].rank(pct=True,method='average')
    rows=[]; candidates=[]
    for f in feats:
        for side in ['LOW','HIGH']:
            e=x[x[f+'_rank']<=.20] if side=='LOW' else x[x[f+'_rank']>=.80]
            s=smry(e); rb=robustness(e)
            months=[v for v in rb.get('monthly',{}).values() if v['n']>=10]
            stable_months=sum(v['mean'] is not None and v['mean']>0 for v in months)
            rec={'feature':f,'side':side,**s,'months_with_10':len(months),'positive_months':stable_months,
                 'first_mean':rb.get('first_half_dates',{}).get('mean'),'second_mean':rb.get('second_half_dates',{}).get('mean'),
                 'remove3_mean':rb.get('remove_best_3_dates',{}).get('mean'),'cost100_mean':rb.get('100bp',{}).get('mean')}
            rows.append(rec)
            if (s['n']>=80 and s['mean'] and s['mean']>0 and s['pf'] and s['pf']>1.2 and
                rec['first_mean'] and rec['first_mean']>0 and rec['second_mean'] and rec['second_mean']>0 and
                rec['remove3_mean'] and rec['remove3_mean']>0 and rec['cost100_mean'] and rec['cost100_mean']>0 and
                len(months)>=2 and stable_months==len(months)):
                candidates.append((f,side,s['mean']))
    uni=pd.DataFrame(rows).sort_values(['mean','pf'],ascending=False); uni.to_csv(OUT/'univariate.csv',index=False)
    # Only if stable univariate factors exist: test simple intersections of the top 4, no threshold search.
    candidates=sorted(candidates,key=lambda z:z[2],reverse=True)[:4]
    combos=[]
    for k in [2,3]:
      for subset in itertools.combinations(candidates,k):
        mask=pd.Series(True,index=x.index); names=[]
        for f,side,_ in subset:
            mask &= (x[f+'_rank']<=.20) if side=='LOW' else (x[f+'_rank']>=.80)
            names.append(f'{f}:{side}')
        e=x[mask]; s=smry(e); rb=robustness(e)
        combos.append({'rule':' & '.join(names),**s,'first_mean':rb.get('first_half_dates',{}).get('mean'),
                       'second_mean':rb.get('second_half_dates',{}).get('mean'),'remove3_mean':rb.get('remove_best_3_dates',{}).get('mean'),
                       'cost100_mean':rb.get('100bp',{}).get('mean'),'monthly':rb.get('monthly',{})})
    pd.DataFrame([{k:v for k,v in r.items() if k!='monthly'} for r in combos]).to_csv(OUT/'combos.csv',index=False)
    result={'scope':'recent 3m only; breadth_ma20 >= 0.50 healthy market; t+1 open to t+5 close; 40bp','rows':int(len(x)),'dates':int(x.Date.nunique()),'stable_univariate':candidates,'top_univariate':uni.head(12).to_dict('records'),'combos':combos}
    (OUT/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True))

if __name__=='__main__':main()
