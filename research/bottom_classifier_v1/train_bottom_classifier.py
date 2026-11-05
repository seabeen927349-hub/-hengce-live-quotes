#!/usr/bin/env python3
"""HENGCE Bottom Discrimination Research V1 (not a stock recommendation).

Point-in-time daily-close features; future-labelled first-touch 20-session triple barrier.
Chronological train/validation/test splits; no 2024+ label information in model choice.
Underlying unadjusted TWSE canonical 2018--2026 mother vessel. No price claim of total return.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, statistics, time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (balanced_accuracy_score, confusion_matrix, log_loss,
     roc_auc_score, average_precision_score, classification_report, brier_score_loss)
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

VERSION='HENGCE_BOTTOM_DISCRIMINATION_RESEARCH_V1_20261105'
ASOF='2026-11-04'
L_HORIZON=20
UPSIDE=.12
DOWNSIDE=.08
DRAWDOWN_TRIGGER=.15
ROLL_COOLDOWN=5
SEED=20261105
CLASSES=['FAKE_BOTTOM','INCONCLUSIVE','TRUE_BOTTOM']
# No future-dependent values in these inputs.
FEATURES=['ret_1','ret_3','ret_5','ret_10','ret_20','ret_60',
    'dd_60','dd_120','above_ma_5','above_ma_20','above_ma_60',
    'slope_ma20_5','vol_5','vol_20','vol_ratio_1_20','vol_ratio_5_20',
    'turnover_20_log','candle_close_location','body_pct','low_retest_5',
    'low_vs_20low','down_days_5','market_breadth_ma20','market_ret1_median',
    'market_ret5_median','market_breadth_pos5','market_vol20_median']


def read_mother(path:Path)->pd.DataFrame:
    cols=['Date','Ticker','Name','Open','High','Low','Close','Volume','Turnover']
    df=pd.read_csv(path,usecols=cols,dtype={'Ticker':str},low_memory=False)
    for c in ['Open','High','Low','Close','Volume','Turnover']:
        df[c]=pd.to_numeric(df[c].astype(str).str.replace(',','',regex=False),errors='coerce')
    df['Date']=pd.to_datetime(df['Date'],errors='coerce')
    df=df.dropna(subset=['Date','Ticker','Close']).sort_values(['Ticker','Date']).reset_index(drop=True)
    df=df.loc[(df.Close>1)&(df.Close<10000)&df.Ticker.str.fullmatch(r'[0-9]{4}')]
    assert not df.duplicated(['Date','Ticker']).any(),'CANONICAL_DUPLICATE' 
    assert df.Date.min().year<=2018 and str(df.Date.max().date())==ASOF
    # Pre-2026 mother is mostly listed electronics (approx 400); 2026 contains
    # ~1,100 entire-market members. Restrict 2026 to the electronics candidates
    # seen in 2025. This introduces survivor/membership proxy bias, disclosed.
    elec=set(df.loc[df.Date.dt.year==2025,'Ticker'])
    df=df.loc[(df.Date.dt.year<=2025)|df.Ticker.isin(elec)].copy()
    # Basic impossible OHLC reject, do not fill prices.
    good=(df.High>=df.Low)&(df.Open>0)&(df.High>=df.Close)&(df.Low<=df.Close)&(df.High>=df.Open)&(df.Low<=df.Open)
    df=df.loc[good].copy()
    df=df.sort_values(['Ticker','Date']).reset_index(drop=True)
    return df


def feat_stocks(df:pd.DataFrame)->pd.DataFrame:
    """All features calculated from observed EOD information no later than t."""
    g=df.groupby('Ticker',sort=False)
    c=df.Close
    for k in [1,3,5,10,20,60]:
        df[f'ret_{k}']=g.Close.pct_change(periods=k,fill_method=None)
    for k in [5,20,60]:
        df[f'ma_{k}']=g.Close.transform(lambda s:s.rolling(k,min_periods=k).mean())
        df[f'above_ma_{k}']=c/df[f'ma_{k}']-1
    for k in [60,120]:
        df[f'dd_{k}']=c/g.Close.transform(lambda s:s.rolling(k,min_periods=k).max())-1
    df['slope_ma20_5']=df['ma_20']/df.groupby('Ticker')['ma_20'].shift(5)-1
    daily_ret=df['ret_1'].clip(-.3,.3)
    df['daily_ret_for_vol']=daily_ret
    for k in [5,20]:
        df[f'vol_{k}']=df.groupby('Ticker')['daily_ret_for_vol'].transform(lambda s:s.rolling(k,min_periods=k).std())
    volmean20=g.Volume.transform(lambda s:s.rolling(20,min_periods=20).mean())
    volmean5=g.Volume.transform(lambda s:s.rolling(5,min_periods=5).mean())
    df['vol_ratio_1_20']=df.Volume/volmean20-1
    df['vol_ratio_5_20']=volmean5/volmean20-1
    df['turnover_20_log']=np.log1p(g.Turnover.transform(lambda s:s.rolling(20,min_periods=20).mean()).clip(lower=0))
    df['candle_close_location']=(c-df.Low)/(df.High-df.Low).replace(0,np.nan)
    df['body_pct']=c/df.Open-1
    low5=g.Low.transform(lambda s:s.rolling(5,min_periods=5).min())
    low20=g.Low.transform(lambda s:s.rolling(20,min_periods=20).min())
    df['low_retest_5']=df.Low/low5-1
    df['low_vs_20low']=c/low20-1
    df['down_day']=np.where(df['ret_1']<0,1.,0.)
    df['down_days_5']=df.groupby('Ticker')['down_day'].transform(lambda s:s.rolling(5,min_periods=5).sum())
    df['eligible_turnover']=(volmean20>=100_000)&(df.Turnover>=1_000_000)&(g.Turnover.transform(lambda s:s.rolling(20,min_periods=20).mean())>=5_000_000)
    df['cand_raw']=(df['dd_60']<=-DRAWDOWN_TRIGGER)&(df['ret_5']<=.04)&(df['low_vs_20low']<=.13)&df.eligible_turnover&(df.vol_20>0)&df['above_ma_60'].notna()
    # A large daily price discontinuity (rights, splits, corrupt quote) in the
    # prior 120 sessions invalidates those features and cannot be safely used.
    df['action_discontinuity']=(df.ret_1.abs()>.2).fillna(False)
    df['prior120_discontinuity']=df.groupby('Ticker')['action_discontinuity'].transform(lambda s:s.rolling(120,min_periods=1).max()).astype(bool)
    df['cand_raw']&=~df['prior120_discontinuity']
    # Market breadth calculated at close t from available electronics cross-section.
    grp=df.groupby('Date',sort=True)
    market=grp.agg(market_breadth_ma20=('above_ma_20',lambda a:float((a>0).mean())),
        market_ret1_median=('ret_1','median'),market_ret5_median=('ret_5','median'),
        market_breadth_pos5=('ret_5',lambda a:float((a>0).mean())),
        market_vol20_median=('vol_20','median'),market_n=('Ticker','size')).reset_index()
    df=df.merge(market,on='Date',how='left',validate='many_to_one')
    return df


def sample_and_label(df:pd.DataFrame)->pd.DataFrame:
    """Build event indices with numpy, then gather features in one vectorized operation."""
    events=[]
    for t,g in df.groupby('Ticker',sort=False):
        closes=g.Close.to_numpy(dtype=float)
        highs=g.High.to_numpy(dtype=float)
        lows=g.Low.to_numpy(dtype=float)
        date_values=g.Date.to_numpy()
        global_index=g.index.to_numpy()
        gap=(g.Date.diff().dt.days.fillna(1).to_numpy()>10)
        discontinuity=g.action_discontinuity.to_numpy(dtype=bool)
        candidates=np.flatnonzero(g.cand_raw.to_numpy(dtype=bool))
        # Pre-compute all interval-bad flags, no repeated 20-bar slicing.
        bad=(gap|discontinuity).astype(int)
        badprefix=np.concatenate(([0],np.cumsum(bad)))
        last=-ROLL_COOLDOWN-1
        for i in candidates:
            if i-last<ROLL_COOLDOWN:continue
            if i+L_HORIZON>=len(g):continue
            if badprefix[i+L_HORIZON+1]-badprefix[i+1]>0:continue
            upper=closes[i]*(1+UPSIDE);lower=closes[i]*(1-DOWNSIDE)
            up=np.flatnonzero(highs[i+1:i+L_HORIZON+1]>=upper)
            down=np.flatnonzero(lows[i+1:i+L_HORIZON+1]<=lower)
            u=(up[0]+1) if up.size else 99
            dn=(down[0]+1) if down.size else 99
            if dn<=u and dn<=L_HORIZON:label='FAKE_BOTTOM';hit_day=dn
            elif u<dn and u<=L_HORIZON:label='TRUE_BOTTOM';hit_day=u
            else:label='INCONCLUSIVE';hit_day=None
            events.append((global_index[i],label,hit_day,
                closes[i+L_HORIZON]/closes[i]-1,
                lows[i+1:i+L_HORIZON+1].min()/closes[i]-1,
                highs[i+1:i+L_HORIZON+1].max()/closes[i]-1,int(i)))
            last=i
    print('SELECTED EVENTS',len(events),flush=True)
    idx=[z[0] for z in events]
    out=df.loc[idx,['Date','Ticker','Name','Close']+FEATURES].copy().reset_index(drop=True)
    out['label']=[z[1] for z in events]
    out['first_barrier_day']=[z[2] for z in events]
    out['forward20_close_return']=[z[3] for z in events]
    out['forward20_worst_low_return']=[z[4] for z in events]
    out['forward20_best_high_return']=[z[5] for z in events]
    out['event_index']=[z[6] for z in events]
    return out.sort_values(['Date','Ticker']).reset_index(drop=True)


def split_data(e:pd.DataFrame)->dict:
    # 20 days purged at calendar boundary in training: prior label's entire
    # horizon must end before validation/test period.
    trains=e.loc[e.Date<'2022-11-25'].copy() # train years 2018-22, 2022 late purged
    validate=e.loc[(e.Date>='2023-01-01')&(e.Date<'2023-11-25')].copy()
    test2024=e.loc[(e.Date>='2024-01-01')&(e.Date<'2024-11-25')].copy()
    test2025=e.loc[(e.Date>='2025-01-01')&(e.Date<'2025-11-25')].copy()
    diag2026=e.loc[(e.Date>='2026-01-01')&(e.Date<=pd.Timestamp(ASOF))].copy()
    # 2026 cases are label-matured by construction. No tuning to 2024+.
    return {'train_2018_2022':trains,'validation_2023':validate,
        'test_2024':test2024,'test_2025':test2025,'diagnostic_2026':diag2026}


def models():
    return {
       'logistic':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),
                LogisticRegression(C=.15,max_iter=500,random_state=SEED)),
       'forest':make_pipeline(SimpleImputer(strategy='median'),
                RandomForestClassifier(n_estimators=90,max_depth=9,min_samples_leaf=55,
                max_features=.65,class_weight=None,n_jobs=4,random_state=SEED))
    }


def get_proba(model,x):
    p=model.predict_proba(x[FEATURES]);cls=list(model.classes_)
    return pd.DataFrame({k:p[:,cls.index(k)] for k in CLASSES},index=x.index)


def base_metrics(d,p,threshold):
    y=d.label.values
    probs=p[CLASSES].to_numpy()
    result={'n':len(d),'class_counts':{k:int((y==k).sum()) for k in CLASSES},
        'macro_f1':None,'multiclass_log_loss':None,
        'true_vs_false_auc':None,'true_vs_false_avg_precision':None,
        'true_base_rate_decisive':None,'pred_true_n':0,'pred_true_precision':None,
        'pred_true_recall':None,'pred_true_false_fraction':None,
        'pred_fake_n':0,'pred_fake_precision':None}
    if not len(d):return result
    from sklearn.metrics import f1_score
    result['macro_f1']=round(float(f1_score(y,np.array(CLASSES)[np.argmax(probs,axis=1)],labels=CLASSES,average='macro',zero_division=0)),4)
    result['multiclass_log_loss']=round(float(log_loss(y,probs,labels=CLASSES)),5)
    decisive=np.isin(y,['TRUE_BOTTOM','FAKE_BOTTOM'])
    if decisive.sum() and (y[decisive]=='TRUE_BOTTOM').sum() and (y[decisive]=='FAKE_BOTTOM').sum():
        z=(y[decisive]=='TRUE_BOTTOM').astype(int)
        score=p.TRUE_BOTTOM.to_numpy()[decisive]/(p.TRUE_BOTTOM.to_numpy()[decisive]+p.FAKE_BOTTOM.to_numpy()[decisive]+1e-12)
        result['true_vs_false_auc']=round(float(roc_auc_score(z,score)),4)
        result['true_vs_false_avg_precision']=round(float(average_precision_score(z,score)),4)
        result['true_base_rate_decisive']=round(float(z.mean()),4)
    flag=(p.TRUE_BOTTOM.to_numpy()>=threshold) & (p.TRUE_BOTTOM.to_numpy()>p.FAKE_BOTTOM.to_numpy())
    falseflag=(p.FAKE_BOTTOM.to_numpy()>=threshold) & (p.FAKE_BOTTOM.to_numpy()>p.TRUE_BOTTOM.to_numpy())
    result['pred_true_n']=int(flag.sum())
    if flag.sum():
        result['pred_true_precision']=round(float((y[flag]=='TRUE_BOTTOM').mean()),4)
        result['pred_true_false_fraction']=round(float((y[flag]=='FAKE_BOTTOM').mean()),4)
    if (y=='TRUE_BOTTOM').sum():result['pred_true_recall']=round(float(((y=='TRUE_BOTTOM')&flag).sum()/(y=='TRUE_BOTTOM').sum()),4)
    result['pred_fake_n']=int(falseflag.sum())
    if falseflag.sum():result['pred_fake_precision']=round(float((y[falseflag]=='FAKE_BOTTOM').mean()),4)
    return result


def choose_threshold(y,p):
    # Only 2023 validation; require 10+ signals to avoid one lucky estimate.
    # Avoid extreme threshold cherry-picking; predeclared grid.
    grid=[.50,.55,.60,.65,.70]
    tested=[]
    for th in grid:
        m=base_metrics(y,p,th);tested.append({'threshold':th,'n':m['pred_true_n'],
              'precision':m['pred_true_precision'],'false_fraction':m['pred_true_false_fraction']})
    viable=[x for x in tested if x['n']>=10 and x['precision'] is not None]
    if viable:
        # optimize precision * coverage^0.25, penalize false calls, validation only.
        best=max(viable,key=lambda x:(x['precision']-.5*(x['false_fraction'] or 0))*(x['n']**.25))
    else:best={'threshold':.65,'n':0,'precision':None,'false_fraction':None}
    return float(best['threshold']),tested


def score_requested_cases(all_df,e,model):
    scores=[]
    for tk,d in [('8150','2026-10-20'),('8150','2026-10-21'),('3055','2026-10-21'),('7795','2026-10-21'),('8150','2026-11-04')]:
        row=all_df.loc[(all_df.Ticker==tk)&(all_df.Date==pd.Timestamp(d))]
        if row.empty:continue
        p=model.predict_proba(row[FEATURES])[0]
        cls=model.classes_
        score={'ticker':tk,'date':d,'observation_at':'AFTER_CLOSE_ONLY',
               'event_trigger_raw':bool(row.iloc[0].cand_raw),
               'close':round(float(row.iloc[0].Close),3),
               'probability':{k:round(float(p[list(cls).index(k)]),4) for k in CLASSES}}
        actual=e.loc[(e.Ticker==tk)&(e.Date==pd.Timestamp(d))]
        score['historical_event_label']=str(actual.iloc[0].label) if not actual.empty else None
        scores.append(score)
    return scores


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mother',required=True);ap.add_argument('--out',required=True);ap.add_argument('--events-only',action='store_true')
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    start=time.time();source=Path(args.mother);checksum=hashlib.sha256(source.read_bytes()).hexdigest()
    df=read_mother(source)
    print('INPUT',len(df),'tickers',df.Ticker.nunique(),'years',df.Date.min(),df.Date.max(),flush=True)
    df=feat_stocks(df)
    print('FEATURES',len(df),'raw candidates',df.cand_raw.sum(),'elapsed',round(time.time()-start,1),flush=True)
    e=sample_and_label(df)
    e.to_pickle(out/'events_features.pkl')
    if args.events_only:
        print('EVENTS_SAVED',len(e),flush=True)
        return
    splits=split_data(e)
    print('EVENTS',len(e),'labels',e.label.value_counts().to_dict(),'splits',{k:len(v) for k,v in splits.items()},'elapsed',round(time.time()-start,1),flush=True)
    train=splits['train_2018_2022'];valid=splits['validation_2023']
    assert min(len(train),len(valid),len(splits['test_2024']),len(splits['test_2025']))>50
    fitted={};vperf={}
    for k,m in models().items():
        m.fit(train[FEATURES],train.label)
        p=get_proba(m,valid)
        perf=base_metrics(valid,p,.6)
        vperf[k]=perf;fitted[k]=m
        print('VALID',k,perf,'elapsed',round(time.time()-start,1),flush=True)
    # Only use 2023 to pick one model. Freeze before looking at 2024/25/26.
    winner=min(vperf,key=lambda k:vperf[k]['multiclass_log_loss'])
    model=fitted[winner]
    threshold,thresholds=choose_threshold(valid,get_proba(model,valid))
    report={'study':VERSION,'status':'RESEARCH_ONLY_NOT_TRADEABLE',
        'asof':ASOF,'source':str(source),'canonical_sha256':checksum,
        'data_rows':int(len(df)),'stock_count':int(df.Ticker.nunique()),
        'event_count':int(len(e)),'event_counts_by_year':{str(k):int(v) for k,v in e.Date.dt.year.value_counts().sort_index().items()},
        'predefined_event_trigger':{'drawdown_60_min':-DRAWDOWN_TRIGGER,'recent_5day_ret_max':.04,'distance_to_20d_low_max':.13,'cooldown_sessions':ROLL_COOLDOWN},
        'predefined_label':{'horizon_sessions':L_HORIZON,'true':'future HIGH +12% before future LOW -8%',
          'fake':'future LOW -8% before future HIGH +12%','inconclusive':'neither barrier hit',
          'same_day_barrier_collision':'FAKE (conservative, unknown intraday order)'},
        'training_provenance':{'train':'events before 2022-11-25','validation':'2023 through 2023-11-24',
              'test_2024':'2024 through 2024-11-24','test_2025':'2025 through 2025-11-24',
              'diagnostic_2026':'label-matured events to 2026-11-04'},
        'time_leakage_guard':'All indicators up to event close; labels use next 20 bars only; no labels beyond the 20-session data horizon; no tuning on 2024+',
        'model_candidates':['logistic','forest'],'validation_metrics':vperf,'winner':winner,
        'validation_threshold_search':thresholds,'decision_threshold':threshold,
        'results':{},'case_studies':[],
        'disclaimers':['Research outcome classification is not proof of a market bottom or a probability of future price appreciation.',
             'Original 09:01 Q017 decisions cannot be replayed using daily-close features; this is a new research model, not a Q017 live upgrade.',
             'Corporate action adjustment is unavailable; events with discontinuities >20% in lookback/forward barred, but some dividend/ex-right effects can remain.',
             '2026 universe restricted to 2025 electronics membership to avoid change from 400 stocks to all 1100; this has membership/survivorship bias.',
             'Events within tickers and dates correlated; simple counts/precision may overstate effective independent sample size.',
             'Models selected using 2023, tested 2024 and 2025; 2026 diagnostics not an untouched truly OOS due prior 2026 study context.',
             'No trading authority and no broker orders.']}
    preds=[]
    for name,sub in splits.items():
        p=get_proba(model,sub);rep=base_metrics(sub,p,threshold)
        report['results'][name]=rep
        print('TEST',name,rep,flush=True)
        if name in ['test_2024','test_2025','diagnostic_2026']:
            dat=sub[['Date','Ticker','Name','Close','label','first_barrier_day','forward20_close_return','forward20_worst_low_return']].copy()
            dat=dat.reset_index(drop=True)
            for k in CLASSES:dat['prob_'+k]=p[k].to_numpy()
            dat['decision']=np.where(dat['prob_TRUE_BOTTOM']>=threshold,'BOTTOM_CANDIDATE',
               np.where(dat['prob_FAKE_BOTTOM']>=threshold,'FAKE_BOTTOM_RISK','UNCERTAIN'))
            dat['split']=name
            preds.append(dat)
    report['case_studies']=score_requested_cases(df,e,model)
    pred=pd.concat(preds,ignore_index=True);pred.to_csv(out/'holdout_predictions.csv',index=False,encoding='utf-8-sig')
    # Transparent model package: logistic version serializes coefficients; HGB
    # is serialized via joblib with checksum; only load trusted model artifacts.
    import joblib
    model_file=out/'bottom_classifier_research.joblib'
    joblib.dump({'model':model,'features':FEATURES,'class_names':CLASSES,'threshold':threshold,
       'version':VERSION,'asof':ASOF,'source_sha256':checksum},model_file,compress=3)
    report['model_file_sha256']=hashlib.sha256(model_file.read_bytes()).hexdigest()
    report['elapsed_sec']=round(time.time()-start,1)
    (out/'evidence_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    print('SAVED',out,'winner',winner,'th',threshold,'elapsed',report['elapsed_sec'],flush=True)

if __name__=='__main__':main()
