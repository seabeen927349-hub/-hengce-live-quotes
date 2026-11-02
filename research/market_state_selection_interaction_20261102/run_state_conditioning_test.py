#!/usr/bin/env python3
import argparse, hashlib, json, zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

FEATURES=["TAIEX_R20","ELEC_EW_R20","ELEC_ADV_DEC_20","TAIEX_DD60","TAIEX_RV20","ELEC_XS_MAD_1","ELEC_VALUE_RATIO20","ELEC_VALUE_TOP10_SHARE","ELEC_SYNC20"]
CENTER=np.array([0.017845530636,0.017361922829,0.046683046683,-0.023182636759,0.150345114704,0.009115597798,1.005554874267,0.435390310132,0.516295466743])
SCALE=np.array([0.062992962803,0.072396439108,0.760480824426,0.050986651757,0.0765906461875,0.0031179637715000007,0.24576684497900025,0.0720344433765,0.18974732372750003])
CENTROIDS=np.array([
[0.18449241068885072,0.16353129045143633,0.15667609786274092,-0.033466432046358074,-0.019090744032355444,0.07374744303137937,0.180612043926747,-0.06932082313717959,-0.14717897865285812],
[-1.1825719260219003,-1.2972976701388452,-0.7791264901206559,-1.575202404098159,1.9430451748028719,0.8960545966913415,-0.06648220506421088,0.4676357905807229,1.2254495563902976]
])

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def num_series(s):
    return pd.to_numeric(s.astype(str).str.replace(',','',regex=False).str.strip(),errors='coerce')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input-dir',required=True)
    ap.add_argument('--output-json',required=True)
    args=ap.parse_args()
    base=Path(args.input_dir)

    es=[]; ss=[]; cs=[]; hashes={}
    for y in range(2018,2027):
        zp=base/f'TWSE_ELECTRONICS_{y}.zip'; hashes[str(y)]=sha256(zp)
        with zipfile.ZipFile(zp) as z:
            e=pd.read_csv(z.open(f'electronics_{y}.csv'),dtype=str)
            s=pd.read_csv(z.open(f'trading_sessions_{y}.csv'))
            c=pd.read_csv(z.open(f'corporate_actions_{y}.csv'),dtype=str)
        e['date']=pd.to_datetime(e['date']); s['date']=pd.to_datetime(s['date']); c['date']=pd.to_datetime(c['date'])
        e['ticker']=e['ticker'].str.zfill(4); c['ticker']=c['ticker'].str.zfill(4)
        for col in ['open','high','low','close','volume_shares','turnover_ntd','trades']:
            e[col]=num_series(e[col])
        c['ex_reference']=num_series(c['ex_reference'])
        es.append(e); ss.append(s); cs.append(c)
    e=pd.concat(es,ignore_index=True).sort_values(['date','ticker']).reset_index(drop=True)
    sessions=pd.concat(ss,ignore_index=True).drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)
    corp=pd.concat(cs,ignore_index=True).drop_duplicates(['date','ticker'],keep='last').sort_values(['date','ticker']).reset_index(drop=True)

    e['prior_close']=e.groupby('ticker',sort=False)['close'].shift(1)
    e=e.merge(corp[['date','ticker','ex_reference']],on=['date','ticker'],how='left',validate='many_to_one')
    e['ref_price']=np.where(e['ex_reference'].notna(),e['ex_reference'],e['prior_close'])
    ok=(e['close']>0)&(e['ref_price']>0)
    e['ret']=np.where(ok,np.log(e['close']/e['ref_price']),np.nan)

    dates=pd.DatetimeIndex(sessions['date']); tickers=np.array(sorted(e['ticker'].unique()))
    dmap={d:i for i,d in enumerate(dates)}; tmap={t:i for i,t in enumerate(tickers)}
    nD,nT=len(dates),len(tickers)
    close=np.full((nD,nT),np.nan); op=np.full((nD,nT),np.nan); turn=np.full((nD,nT),np.nan); ret=np.full((nD,nT),np.nan); member=np.zeros((nD,nT),bool)
    di=e['date'].map(dmap).to_numpy(int); ti=e['ticker'].map(tmap).to_numpy(int)
    close[di,ti]=e['close']; op[di,ti]=e['open']; turn[di,ti]=e['turnover_ntd']; ret[di,ti]=e['ret']; member[di,ti]=True

    liq20=pd.DataFrame(turn).rolling(20,min_periods=18).median().to_numpy()
    rdf=pd.DataFrame(ret); mom20=rdf.rolling(20,min_periods=20).sum().to_numpy(); valid20=rdf.rolling(20,min_periods=20).count().to_numpy()
    intraday=np.where((op>0)&(close>0),np.log(close/op),np.nan)
    csum=np.vstack([np.zeros((1,nT)),np.cumsum(np.nan_to_num(ret,nan=0.0),axis=0)])
    ccnt=np.vstack([np.zeros((1,nT),dtype=int),np.cumsum(np.isfinite(ret),axis=0)])
    h20=np.full((nD,nT),np.nan)
    for d in range(nD-19):
        sm19=csum[d+20]-csum[d+1]; ct19=ccnt[d+20]-ccnt[d+1]
        v=np.isfinite(intraday[d])&(ct19==19)
        h20[d,v]=np.expm1(intraday[d,v]+sm19[v])

    v3p=base/'HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V3.csv'; v3=pd.read_csv(v3p)
    v3['market_event_date']=pd.to_datetime(v3['market_event_date']); v3['observation_date']=pd.to_datetime(v3['observation_date'])
    sv=v3[FEATURES].notna().all(axis=1).to_numpy(); states=np.array(['UNKNOWN_FAIL_CLOSED']*len(v3),object)
    X=(v3.loc[sv,FEATURES].to_numpy(float)-CENTER)/SCALE; ds=np.sqrt(((X[:,None,:]-CENTROIDS[None,:,:])**2).sum(axis=2))
    states[sv]=np.where(ds.argmin(axis=1)==0,'DIFFUSE_NORMAL','SYNCHRONIZED_STRESS'); v3['state']=states

    rows=[]; audit=[]
    for _,z in v3[v3.state!='UNKNOWN_FAIL_CLOSED'].iterrows():
        sd,ed,st=z.market_event_date,z.observation_date,z.state; reason='PRIMARY_INCLUDED'
        if sd not in dmap or ed not in dmap or dmap[ed]!=dmap[sd]+1: reason='ENTRY_DATE_MISMATCH_OR_MISSING'
        else:
            d,entry=dmap[sd],dmap[ed]
            if entry+19>=nD: reason='HORIZON_UNAVAILABLE'
            else:
                elig=member[d]&np.isfinite(close[d])&np.isfinite(liq20[d])&(valid20[d]==20)&np.isfinite(mom20[d]); inds=np.flatnonzero(elig)
                if len(inds)<100: reason='U100_INSUFFICIENT'
                else:
                    u100=inds[np.lexsort((tickers[inds],-liq20[d,inds]))[:100]]
                    top5=u100[np.lexsort((tickers[u100],-liq20[d,u100],-mom20[d,u100]))[:5]]
                    outs=h20[entry,u100]; tops=h20[entry,top5]
                    if np.isfinite(tops).sum()<5: reason='TOP5_OUTCOME_INVALID'
                    elif np.isfinite(outs).sum()<95: reason='U100_OUTCOME_LT95'
                    else:
                        tm=float(np.nanmean(tops)); um=float(np.nanmean(outs))
                        rows.append({'signal_date':sd,'state':st,'top5_h20':tm,'u100_h20':um,'excess_h20':tm-um})
        audit.append({'signal_date':sd,'state':st,'reason':reason})
    r=pd.DataFrame(rows).sort_values('signal_date').reset_index(drop=True); r['stress']=(r.state=='SYNCHRONIZED_STRESS').astype(int)
    X=sm.add_constant(r['stress']); fit=sm.OLS(r['excess_h20'],X).fit().get_robustcov_results(cov_type='HAC',maxlags=20,use_correction=True)
    delta=float(r.loc[r.stress==1,'excess_h20'].mean()-r.loc[r.stress==0,'excess_h20'].mean())

    vals=r.excess_h20.to_numpy(); st=r.stress.to_numpy(); n=len(r); L=20; starts=np.arange(n-L+1); rng=np.random.default_rng(20261102); boot=np.empty(10000)
    for b in range(10000):
        idx=[]
        while len(idx)<n:
            s=int(rng.choice(starts)); idx.extend(range(s,s+L))
        idx=np.array(idx[:n]); boot[b]=vals[idx][st[idx]==1].mean()-vals[idx][st[idx]==0].mean()
    ci=np.quantile(boot,[.025,.975])
    r['period']=np.where(r.signal_date<=pd.Timestamp('2022-12-31'),'EARLY_2018_2022','LATE_2023_2026')
    temporal={}
    for p,g in r.groupby('period'):
        temporal[p]=float(g.loc[g.stress==1,'excess_h20'].mean()-g.loc[g.stress==0,'excess_h20'].mean())
    summ={}
    for state,g in r.groupby('state'):
        summ[state]={'n':len(g),'top5_mean_h20':float(g.top5_h20.mean()),'top5_median_h20':float(g.top5_h20.median()),'u100_mean_h20':float(g.u100_h20.mean()),'u100_median_h20':float(g.u100_h20.median()),'excess_mean_h20':float(g.excess_h20.mean()),'excess_median_h20':float(g.excess_h20.median()),'excess_positive_fraction':float((g.excess_h20>0).mean())}
    aud=pd.DataFrame(audit).groupby(['state','reason']).size().unstack(fill_value=0).to_dict('index')
    conclusion='CONDITIONING_ESTABLISHED' if (ci[0]>0 or ci[1]<0) and np.sign(temporal['EARLY_2018_2022'])==np.sign(delta) and np.sign(temporal['LATE_2023_2026'])==np.sign(delta) else 'INCONCLUSIVE'
    if conclusion=='CONDITIONING_ESTABLISHED' and abs(delta)>=.01: conclusion='ECONOMICALLY_MATERIAL_CANDIDATE'
    out={'archive_sha256':hashes,'state_matrix_sha256':sha256(v3p),'primary_sample':{'n':len(r),'first_signal_date':str(r.signal_date.min().date()),'last_signal_date':str(r.signal_date.max().date())},'state_summary':summ,'delta_stress_minus_normal':delta,'hac_lag20':{'se':float(fit.bse[1]),'t':float(fit.tvalues[1]),'p':float(fit.pvalues[1]),'ci95':[float(x) for x in fit.conf_int()[1]]},'moving_block_bootstrap':{'block_length':20,'resamples':10000,'seed':20261102,'mean':float(boot.mean()),'ci95':[float(x) for x in ci]},'temporal_delta':temporal,'outcome_gate_audit':aud,'formal_conclusion':conclusion,'authority':'RESEARCH_ONLY_NO_TRADING_OR_PRODUCTION_AUTHORITY'}
    Path(args.output_json).write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))

if __name__=='__main__': main()
