#!/usr/bin/env python3
"""Causal performance health gate for research classifier.
Past labels usable only after 20 complete stock trading sessions; never future.
130-day window; minimum 100 decisive examples from >=20 event dates;
ROC AUC >=0.55. Experimental guard chosen after seeing 2026 failure;
NOT an independent OOS strategy proof.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score
import json
ROOT=Path(__file__).parent
MOTHER=Path('/mnt/data/hengce3042/HENGCE_2026_HIST_MOTHER.csv')
raw=pd.read_csv(MOTHER,usecols=['Date','Ticker'],dtype={'Ticker':str},parse_dates=['Date'])
raw=raw.sort_values(['Ticker','Date']).drop_duplicates(['Ticker','Date'])
raw['label_matured_on']=raw.groupby('Ticker').Date.shift(-20)
P=pd.read_csv(ROOT/'holdout_predictions.csv',parse_dates=['Date'],dtype={'Ticker':str})
P=P.merge(raw,on=['Ticker','Date'],how='left',validate='one_to_one')
assert P.label_matured_on.notna().all()
P['signal_ratio']=P.prob_TRUE_BOTTOM/(P.prob_TRUE_BOTTOM+P.prob_FAKE_BOTTOM)
P['decisive']=P.label.isin(['TRUE_BOTTOM','FAKE_BOTTOM'])
P[['Date','Ticker','label_matured_on','label','prob_TRUE_BOTTOM','prob_FAKE_BOTTOM','signal_ratio']].to_csv(ROOT/'health_matured_events.csv',index=False,encoding='utf-8-sig')
DAYS=sorted(P.Date.unique())
results=[]
for day in DAYS:
    prior=P.loc[(P.label_matured_on<day)&(P.label_matured_on>=day-pd.Timedelta(days=130))&P.decisive]
    n=len(prior);ud=prior.Date.nunique()
    auc=roc_auc_score(prior.label.eq('TRUE_BOTTOM'),prior.signal_ratio) if n>=100 and ud>=20 and prior.label.nunique()==2 else None
    pass_gate=auc is not None and auc>=.55
    current=P.loc[P.Date==day]
    ready=current.loc[current.prob_TRUE_BOTTOM>=.65]
    approved=ready if pass_gate else ready.iloc[:0]
    results.append({'date':str(pd.Timestamp(day).date()),'year':pd.Timestamp(day).year,
      'mature_prior_decisive_n':int(n),'mature_prior_event_dates':int(ud),
      'rolling_auc':round(float(auc),4) if auc is not None else None,
      'health':'PASS' if pass_gate else ('FAIL' if auc is not None else 'INSUFFICIENT_HISTORY'),
      'raw_high_confidence_n':len(ready),'raw_high_confidence_true_n':int(ready.label.eq('TRUE_BOTTOM').sum()),
      'raw_high_confidence_fake_n':int(ready.label.eq('FAKE_BOTTOM').sum()),
      'approved_n':len(approved),'approved_true_n':int(approved.label.eq('TRUE_BOTTOM').sum()),
      'approved_fake_n':int(approved.label.eq('FAKE_BOTTOM').sum())})
perdate=pd.DataFrame(results)
perdate.to_csv(ROOT/'health_by_date.csv',index=False)
summary=[]
for year,z in perdate.groupby('year'):
    for typ in ['raw','approved']:
        n=z[f'{typ}_high_confidence_n'].sum() if typ=='raw' else z['approved_n'].sum()
        success=z['raw_high_confidence_true_n'].sum() if typ=='raw' else z['approved_true_n'].sum()
        wrong=z['raw_high_confidence_fake_n'].sum() if typ=='raw' else z['approved_fake_n'].sum()
        summary.append({'year':int(year),'strategy':typ,'events':int(n),'true':int(success),'fake':int(wrong),
          'precision_all':round(success/n,4) if n else None,'fake_rate_all':round(wrong/n,4) if n else None,
          'pass_days':int(z.health.eq('PASS').sum()),'all_days':len(z)})
def external_health(day):
    day=pd.Timestamp(day)
    prior=P.loc[(P.label_matured_on<day)&(P.label_matured_on>=day-pd.Timedelta(days=130))&P.decisive]
    n=len(prior);ud=prior.Date.nunique()
    auc=roc_auc_score(prior.label.eq('TRUE_BOTTOM'),prior.signal_ratio) if n>=100 and ud>=20 and prior.label.nunique()==2 else None
    return {'asof':str(day.date()),'mature_decisive_events':int(n),'mature_signal_days':int(ud),
        'rolling_auc':round(float(auc),4) if auc is not None else None,
        'gate':('PASS' if auc>=.55 else 'FAIL') if auc is not None else 'INSUFFICIENT_HISTORY'}
report={'gate_rules':{'lookback_days':130,'min_decisive':100,'min_event_dates':20,'minimum_auc':.55,
         'confidence_threshold':.65,'label_matured':'Only after 20 subsequent stock sessions fully ended'},
        'posthoc_warning':'The gate conditions were designed AFTER looking at 2026 deterioration and are exploratory, not independent out-of-sample validation.',
        'retired':'NO_ACTIVE_MODEL',
        'by_year':summary,
        'asof_2026_10_21':external_health('2026-10-21'),
        'asof_2026_11_04':external_health('2026-11-04')}
(ROOT/'health_gate_evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
