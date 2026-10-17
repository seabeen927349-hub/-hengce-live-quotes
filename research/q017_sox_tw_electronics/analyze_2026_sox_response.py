#!/usr/bin/env python3
from pathlib import Path
import json, math
import numpy as np
import pandas as pd

ROOT=Path('research/q017_sox_tw_electronics/archive_2026')
OUT=Path('research/q017_sox_tw_electronics/results_2026')
OUT.mkdir(parents=True,exist_ok=True)
COST=0.004


def num(s):
    return pd.to_numeric(s.astype(str).str.replace(',','',regex=False).str.replace('--','',regex=False).str.strip(),errors='coerce')

px=pd.read_csv(ROOT/'twse_electronics_membership_2026.csv',dtype={'ticker':str})
sox=pd.read_csv(ROOT/'sox_2026.csv')
px['date']=pd.to_datetime(px['date'])
sox['date']=pd.to_datetime(sox['date'])
for c in ['open','high','low','close','volume_shares','turnover_ntd']:
    px[c]=num(px[c])
sox['close']=pd.to_numeric(sox['close'],errors='coerce')
sox=sox.dropna().sort_values('date').drop_duplicates('date')
sox['sox_ret']=sox['close'].pct_change()

# Taiwan opens before the U.S. session of the same calendar date; only use latest completed SOX date strictly before TW date.
mapdf=pd.merge_asof(pd.DataFrame({'date':sorted(px['date'].unique())}),sox[['date','close','sox_ret']].rename(columns={'date':'sox_date','close':'sox_close'}),left_on='date',right_on='sox_date',direction='backward',allow_exact_matches=False)
px=px.merge(mapdf,on='date',how='left')
px=px.sort_values(['ticker','date'])
g=px.groupby('ticker',group_keys=False)
px['prev_close']=g['close'].shift(1)
px['gap']=px['open']/px['prev_close']-1
px['intraday']=px['close']/px['open']-1
px['cc']=px['close']/px['prev_close']-1
for h in [1,3,5]:
    px[f'close_p{h}']=g['close'].shift(-h)
    px[f'open_to_c{h}']=px[f'close_p{h}']/px['open']-1

valid=px.dropna(subset=['sox_ret','open','close','prev_close']).copy()

# Daily equal-weight electronic basket, so large membership days do not overweight the statistics.
aggcols=['gap','intraday','cc','open_to_c1','open_to_c3','open_to_c5']
daily=valid.groupby('date').agg({**{c:'mean' for c in aggcols},'sox_ret':'first','sox_date':'first','ticker':'count'}).rename(columns={'ticker':'n_stocks'}).reset_index()

def corr_beta(x,y):
    z=pd.DataFrame({'x':x,'y':y}).dropna()
    if len(z)<20:return (None,None)
    corr=float(z.x.corr(z.y))
    v=float(z.x.var(ddof=1))
    beta=float(z[['x','y']].cov().iloc[0,1]/v) if v>0 else None
    return corr,beta

basket_stats={}
for c in aggcols:
    corr,beta=corr_beta(daily['sox_ret'],daily[c])
    basket_stats[c]={'corr':corr,'beta_per_1pct_sox':beta,'n':int(daily[['sox_ret',c]].dropna().shape[0])}

bins=[-99,-.03,-.015,0,.015,.03,99]
labels=['<=-3%','-3~-1.5%','-1.5~0%','0~1.5%','1.5~3%','>=3%']
daily['sox_bin']=pd.cut(daily.sox_ret,bins=bins,labels=labels,right=False)
bin_rows=[]
for b,df in daily.groupby('sox_bin',observed=True):
    row={'sox_bin':str(b),'days':len(df),'sox_mean':df.sox_ret.mean()}
    for c in aggcols:
        row[c+'_mean']=df[c].mean(); row[c+'_median']=df[c].median(); row[c+'_positive_rate']=float((df[c]>0).mean())
    bin_rows.append(row)
bins_df=pd.DataFrame(bin_rows)
bins_df.to_csv(OUT/'sox_bins_basket_response.csv',index=False)

# Event-direction hit rates at several SOX thresholds.
events=[]
for thr in [0,.01,.015,.02,.03]:
    for side in ['UP','DOWN']:
        d=daily[daily.sox_ret>=thr] if side=='UP' else daily[daily.sox_ret<=-thr]
        if thr==0:
            d=daily[daily.sox_ret>0] if side=='UP' else daily[daily.sox_ret<0]
        if len(d)==0:continue
        for c in ['gap','intraday','cc','open_to_c1','open_to_c3','open_to_c5']:
            expected=(d[c]>0) if side=='UP' else (d[c]<0)
            events.append({'threshold':thr,'side':side,'outcome':c,'days':len(d),'mean':d[c].mean(),'median':d[c].median(),'direction_hit_rate':expected.mean(),'long_after_cost_mean':d[c].mean()-COST})
pd.DataFrame(events).to_csv(OUT/'sox_event_thresholds.csv',index=False)

# Per-stock full-period response diagnostics.
stocks=[]
for tic,d in valid.groupby('ticker'):
    if len(d)<80:continue
    nm=d['name'].iloc[-1]
    rec={'ticker':tic,'name':nm,'n':len(d),'turnover_median':d.turnover_ntd.median()}
    for c in ['gap','intraday','cc','open_to_c1','open_to_c3','open_to_c5']:
        corr,beta=corr_beta(d.sox_ret,d[c]); rec[c+'_corr']=corr; rec[c+'_beta']=beta
    stocks.append(rec)
stocks=pd.DataFrame(stocks)
stocks['tradable_sox_score']=stocks['gap_corr'].fillna(0)*0.35+stocks['intraday_corr'].fillna(0)*0.35+stocks['open_to_c1_corr'].fillna(0)*0.30
stocks=stocks.sort_values('tradable_sox_score',ascending=False)
stocks.to_csv(OUT/'per_stock_sox_response.csv',index=False)
stocks.head(50).to_csv(OUT/'top50_sox_sensitive_stocks.csv',index=False)

# Point-in-time rolling SOX beta: 60 prior observations, minimum 40, shifted by construction (uses [i-60:i]).
valid['beta60_prior']=np.nan
valid['corr60_prior']=np.nan
for tic,idx in valid.groupby('ticker').groups.items():
    ids=list(idx); d=valid.loc[ids].sort_values('date'); ids=list(d.index)
    x=d.sox_ret.to_numpy(); y=d.cc.to_numpy()
    for i in range(len(d)):
        st=max(0,i-60)
        xx=x[st:i]; yy=y[st:i]
        mask=np.isfinite(xx)&np.isfinite(yy)
        if mask.sum()<40:continue
        xx=xx[mask]; yy=yy[mask]
        vx=np.var(xx,ddof=1)
        if vx<=0:continue
        valid.loc[ids[i],'beta60_prior']=np.cov(xx,yy,ddof=1)[0,1]/vx
        valid.loc[ids[i],'corr60_prior']=np.corrcoef(xx,yy)[0,1]

# Each day top/bottom quintile of prior SOX beta; measure next outcomes without using future beta.
def qtag(s):
    if s.notna().sum()<20:return pd.Series(index=s.index,dtype='object')
    r=s.rank(pct=True,method='average')
    return pd.Series(np.where(r>=.8,'TOP20',np.where(r<=.2,'BOTTOM20','MID')),index=s.index)
valid['beta_bucket']=valid.groupby('date')['beta60_prior'].transform(lambda s:qtag(s))
pt=[]
for bucket,d in valid.dropna(subset=['beta_bucket']).groupby('beta_bucket'):
    for side,dd in [('SOX_UP',d[d.sox_ret>0]),('SOX_DOWN',d[d.sox_ret<0]),('SOX_UP_1_5',d[d.sox_ret>=.015]),('SOX_DOWN_1_5',d[d.sox_ret<=-.015])]:
        if len(dd)==0:continue
        # First average stocks per day, then average days.
        gd=dd.groupby('date')[aggcols].mean()
        rec={'beta_bucket':bucket,'event':side,'days':len(gd),'stock_rows':len(dd),'prior_beta_mean':dd.beta60_prior.mean(),'prior_corr_mean':dd.corr60_prior.mean()}
        for c in aggcols:
            rec[c+'_mean']=gd[c].mean();rec[c+'_positive_rate']=(gd[c]>0).mean();rec[c+'_net_long']=gd[c].mean()-COST
        pt.append(rec)
ptdf=pd.DataFrame(pt)
ptdf.to_csv(OUT/'pit_beta_bucket_response.csv',index=False)

# How much of SOX transmission is opening gap vs after-open continuation.
# Regression beta decomposition on daily EW basket: CC beta ~= gap beta + intraday beta (approximately additive for small returns).
decomp={k:basket_stats[k]['beta_per_1pct_sox'] for k in ['gap','intraday','cc','open_to_c1','open_to_c3','open_to_c5']}
if decomp['cc'] not in (None,0):
    decomp['gap_share_of_cc_beta']=decomp['gap']/decomp['cc']
    decomp['intraday_share_of_cc_beta']=decomp['intraday']/decomp['cc']

summary={
 'system':'HENGCE','study':'Q017 2026 SOX x Taiwan Electronics Response','status':'PASS',
 'scope':'TWSE-listed electronics via MI_INDEX type=13; OTC not included',
 'alignment':'Each Taiwan date uses latest completed SOX session strictly before Taiwan calendar date; no same-date U.S. lookahead',
 'cost_assumption_round_trip':COST,
 'tw_days':int(daily.date.nunique()),'stock_rows':int(len(valid)),'stocks':int(valid.ticker.nunique()),'sox_sessions':int(len(sox.dropna(subset=['sox_ret']))),
 'basket_stats':basket_stats,'beta_decomposition':decomp,
 'top10_sensitive':stocks.head(10)[['ticker','name','n','gap_corr','intraday_corr','cc_corr','open_to_c1_corr','tradable_sox_score']].replace({np.nan:None}).to_dict('records'),
 'files':['sox_bins_basket_response.csv','sox_event_thresholds.csv','per_stock_sox_response.csv','top50_sox_sensitive_stocks.csv','pit_beta_bucket_response.csv']
}
(OUT/'q017_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
