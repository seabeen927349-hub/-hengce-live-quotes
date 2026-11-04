#!/usr/bin/env python3
"""Read-only HENGCE Escape 2026 full canonical mother / dated electronics archive audit.

Never builds an authorized Escape packet; reports as-of retrospective evidence only.
Runs frozen formula *research candidates* with explicit source and universe limitations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

METRICS = ['foreign_relative_flow_5','trust_relative_flow_5','dealer_relative_flow_5',
           'totalnet_relative_flow_5','totalnet_relative_flow_10','flow_breadth_negative_share',
           'capital_migration_strength','source_absolute_flow_5','broad_market_absolute_flow_5',
           'destination_absorption_strength','price_damage_score_raw','price_recovery_score_raw',
           'flow_reentry_score_raw','vulnerability_crowding_score_raw','vulnerability_leverage_score_raw',
           'internal_structure_score_raw','price_flow_divergence_score_raw']
EXPECTED_MOTHER_SHA='6f7494b46af07a11f68429981b3ec666ad0a520ed9b51ae0150f4c34435639e7'

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda: f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def divide(a,b):return a.div(b.where(b>0))
def group_mean(a, mask):return a.where(mask).mean(axis=1,skipna=True)
def group_frac(condition,valid):
 den=valid.sum(axis=1);return (condition & valid).sum(axis=1).div(den.where(den>0))

def main(args):
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 source_sha=sha(args.mother);archive_sha=sha(args.archive)
 mother=pd.read_csv(args.mother,dtype={'Ticker':str},parse_dates=['Date'],low_memory=False)
 if len(mother)!=946213:raise ValueError('REPAIRED_PANEL_ROW_COUNT_UNEXPECTED')
 if mother.duplicated(['Date','Ticker']).any():raise ValueError('MOTHER_DUPLICATE_DATE_TICKER')
 archive=pd.read_csv(args.archive,dtype={'ticker':str},parse_dates=['date'],low_memory=False)
 archive['ticker']=archive.ticker.astype(str)
 if archive.duplicated(['date','ticker']).any():raise ValueError('E_ARCHIVE_DUPLICATE_DATE_TICKER')
 # 2023-2026 daily PIT electronic cohorts from separately timestamped archives.
 # The 2026 archive ends 2026-10-27; neither infer nor backfill subsequent days.
 terminal=min(pd.Timestamp(args.through),archive.date.max())
 archive=archive.loc[archive.date.le(terminal)].copy()
 days=pd.Index(sorted(archive.date.unique()),name='Date')
 mother=mother.loc[(mother.Date.isin(days))].copy()
 if set(mother.Date.unique())!=set(days):raise ValueError('MOTHER_DATE_SCOPE_MISSING')
 normal=mother.Ticker.str.fullmatch(r'[1-9][0-9]{3}') & ~mother.Name.fillna('').str.contains('-DR$',regex=True,case=False)
 excluded_mother=mother.loc[~normal,['Date','Ticker','Name']].copy()
 mother=mother.loc[normal].copy()
 evalid=archive.ticker.str.fullmatch(r'[1-9][0-9]{3}')
 excluded_e=archive.loc[~evalid,['date','ticker','name']].copy()
 archive=archive.loc[evalid].copy()
 mapkeys=set(zip(mother.Date,mother.Ticker))
 ekeys=set(zip(archive.date,archive.ticker))
 unmatched=ekeys-mapkeys
 if unmatched:raise ValueError(f'PIT_E_NOT_IN_MOTHER:{sorted(unmatched)[:3]}')
 # Compare independent source archives without changing original mother bytes.
 joined=archive.merge(mother[['Date','Ticker','Volume','Turnover','Close']],left_on=['date','ticker'],right_on=['Date','Ticker'],how='left',validate='1:1')
 diffs={}
 mismatch_dates=set()
 for src,dst in [('close','Close'),('volume_shares','Volume'),('turnover_ntd','Turnover')]:
  a=pd.to_numeric(joined[src].astype(str).str.replace(',','',regex=False),errors='coerce')
  b=pd.to_numeric(joined[dst],errors='coerce')
  # zero tolerance for share counts/currency, quoted closes with decimal precision.
  mismatch=(a.notna() & b.notna() & (~np.isclose(a,b,atol=0.00000001,rtol=0)))
  diffs[src]={'mismatch_rows':int(mismatch.sum()),'by_date':{str(k.date()):int(v) for k,v in joined.loc[mismatch,'date'].value_counts().sort_index().items()},
              'sample':joined.loc[mismatch,['date','ticker',src,dst]].head(3).astype(str).to_dict('records')}
  mismatch_dates.update(joined.loc[mismatch,'date'].dt.strftime('%Y-%m-%d').tolist())
 tickers=pd.Index(sorted(mother.Ticker.unique()),name='Ticker')
 ix=pd.MultiIndex.from_product([days,tickers],names=['Date','Ticker'])
 frame=mother.set_index(['Date','Ticker']).reindex(ix)
 E=pd.DataFrame(False,index=days,columns=tickers,dtype=bool)
 for d,grp in archive.groupby('date'):
  E.loc[d,grp.ticker.tolist()]=True
 # U from dated mother's observed listed price rows is research proxy only.
 U=frame.Name.notna().unstack('Ticker').fillna(False).astype(bool)
 E &= U
 N=U & ~E
 def channel(name):return pd.to_numeric(frame[name],errors='coerce').unstack('Ticker')
 V=channel('Volume'); T=channel('Turnover'); C=channel('Close').where(lambda x:x>0)
 MB=channel('Margin_MarginBalance'); FN=channel('ForeignNet');TN=channel('TrustNet');TOT=channel('TotalNet');DN=TOT-FN-TN
 # Protect invariant: dealer is derived, not an invented fourth independent institution.
 def intensity(ch,cohort,n):
  valid=cohort & (V>0) & ch.notna()
  s=ch.where(valid).sum(axis=1,min_count=1).rolling(n,min_periods=n).sum()
  v=V.where(valid).sum(axis=1,min_count=1).rolling(n,min_periods=n).sum()
  return divide(s,v)
 metrics=pd.DataFrame(index=days)
 c5={}
 for p,ch in [('foreign',FN),('trust',TN),('dealer',DN),('totalnet',TOT)]:
  c5[p]=intensity(ch,E,5)-intensity(ch,N,5)
  metrics[p+'_relative_flow_5']=c5[p]
 metrics['totalnet_relative_flow_10']=intensity(TOT,E,10)-intensity(TOT,N,10)
 source=intensity(TOT,E,5);destination=intensity(TOT,N,5)
 metrics['source_absolute_flow_5']=source
 metrics['broad_market_absolute_flow_5']=intensity(TOT,U,5)
 migration=(destination-source).where((source<0)&(destination>0),0.0)
 metrics['capital_migration_strength']=migration.where(source.notna() & destination.notna())
 metrics['destination_absorption_strength']=destination.clip(lower=0)
 # Each stock must be an eligible E member in all of the stock's 5 dates.
 stock_valid=E & (V>0) & TOT.notna()
 stock_flow=divide(TOT.where(stock_valid).rolling(5,min_periods=5).sum(),V.where(stock_valid).rolling(5,min_periods=5).sum())
 metrics['flow_breadth_negative_share']=group_frac(stock_flow<0,E & stock_flow.notna())
 # Both endpoints must have been in the same observed PIT cohort.
 def stock_ret(cohort,w):
  good=cohort & cohort.shift(w).fillna(False) & C.notna() & C.shift(w).notna()
  return (C / C.shift(w)-1).where(good)
 rE5=group_mean(stock_ret(E,5),E)
 rN5=group_mean(stock_ret(N,5),N)
 rE20=group_mean(stock_ret(E,20),E)
 rN20=group_mean(stock_ret(N,20),N)
 relative20=rE20-rN20
 # The complete 20-session price window is required for breadth to avoid stale fills.
 cp=C.where(U)
 ma20=cp.rolling(20,min_periods=20).mean()
 eligible=ma20.notna() & C.notna()
 breadthE=group_frac(C>ma20,E & eligible)
 breadthU=group_frac(C>ma20,U & eligible)
 def fully_present(x,cohort):
  r=x.where(cohort)
  return r.sum(axis=1,min_count=1).where(r.notna().sum(axis=1).eq(cohort.sum(axis=1)) & cohort.sum(axis=1).gt(0))
 turnE=fully_present(T,E);turnU=fully_present(T,U)
 turnshare=divide(turnE,turnU)
 # Margin lacks a safe audited exemption list; no missing-as-zero.
 margin_coverage=(MB.notna() & E).sum(axis=1).div(E.sum(axis=1))
 marginE=fully_present(MB,E)
 marginchg=divide(marginE,marginE.shift(20))-1
 # 20-day Pearson pairwise correlations; include stock only when it was PIT E on both return days.
 rets=C.pct_change(fill_method=None)
 rets=rets.where(E & E.shift(1).fillna(False))
 corr=pd.Series(np.nan,index=days)
 for i in range(20,len(days)):
  d=days[i]
  symbols=E.iloc[i][E.iloc[i]].index
  rx=rets.iloc[i-19:i+1].loc[:,symbols]
  good=rx.columns[rx.notna().sum(axis=0)>=15]
  if len(good)<2:continue
  a=rx.loc[:,good].corr(min_periods=15).to_numpy()
  tri=a[np.triu_indices(len(a),1)]
  tri=tri[np.isfinite(tri)]
  if len(tri):corr.iloc[i]=float(tri.mean())
 metrics['vulnerability_crowding_score_raw']=turnshare+relative20.clip(lower=0)
 metrics['vulnerability_leverage_score_raw']=marginchg
 metrics['internal_structure_score_raw']=(- (corr-corr.shift(10))).clip(lower=0)*breadthE
 metrics['price_flow_divergence_score_raw']=relative20.clip(lower=0)*(-c5['totalnet']).clip(lower=0)
 metrics['price_damage_score_raw']=(1-breadthE)+(1-breadthU)+(-rE5).clip(lower=0)+(-(rE5-rN5)).clip(lower=0)
 metrics['price_recovery_score_raw']=breadthE+breadthU+rE5.clip(lower=0)+(rE5-rN5).clip(lower=0)
 metrics['flow_reentry_score_raw']=sum(c5[k].clip(lower=0) for k in ('foreign','trust','dealer','totalnet'))
 metrics=metrics[METRICS]
 # Official detection requires 40 PAST valid sessions for each metric; no same-day baseline.
 baseline_valid=pd.DataFrame(index=days)
 for k in METRICS:
  baseline_valid[k]=metrics[k].notna().shift(1,fill_value=False).rolling(60,min_periods=1).sum().ge(40)&metrics[k].notna()
 all_ready=baseline_valid.all(axis=1)
 # Future returns for evaluation only, not model inputs. No simulated trades.
 e_daily=group_mean(C.div(C.shift(1)).sub(1),E & E.shift(1).fillna(False))
 fwd={}
 for horizon in (5,10,20):
  arr=(1+e_daily).rolling(horizon).apply(np.prod,raw=True).shift(-horizon).add(-1)
  fwd[f'electronics_ew_daily_chain_fwd_{horizon}']=arr
 for k,v in fwd.items():metrics[k]=v
 metrics['complete_metric_count']=metrics[METRICS].notna().sum(axis=1)
 metrics['eligible_past40_17_count']=baseline_valid.sum(axis=1)
 metrics['all17_ready_research']=all_ready
 metrics['margin_e_coverage']=margin_coverage
 metrics['e_count']=E.sum(axis=1)
 metrics['u_count']=U.sum(axis=1)
 metrics['e_flow_coverage']=(TOT.notna() & E).sum(axis=1).div(E.sum(axis=1))
 metrics['source_archive_disagreement']=pd.Series([d.strftime('%Y-%m-%d') in mismatch_dates for d in days],index=days)
 # Caveat: passing counts are not PIT validation, revision resolution or predictive validation.
 results={
  'schema':'HENGCE_ESCAPE_REPAIRED_2023_2026_RESEARCH_REPLAY_V1',
  'status':'RESEARCH_SHADOW_ONLY_BLOCKED',
  'repaired_research_panel_sha256':source_sha,'original_canonical_mother_sha256':EXPECTED_MOTHER_SHA,'original_canonical_mother_mutated':False,
  'research_join_rows':len(mother),'research_panel_through':str(days[-1].date()),
  'archive_sha256':archive_sha,'archive_dates':[str(days.min().date()),str(days.max().date())],
  'trading_sessions':len(days),'archive_e_rows':int(len(archive)),
  'archive_excluded_nonordinary':int(len(excluded_e)),
  'mother_excluded_nonordinary':int(len(excluded_mother)),
  'universe_source':'CANONICAL_PRICE_ROWS_DATE_OBSERVED_COMMON_PROXY_NOT_INDEPENDENT_VERIFIED_PIT',
  'electronics_source':'TWSE_TYPE13_ARCHIVE_DAILY_MEMBERSHIP_RECONCILIATION_PENDING',
  'daily_e_count_min':int(E.sum(axis=1).min()),'daily_e_count_max':int(E.sum(axis=1).max()),
  'source_price_reconciliation':diffs,
  'source_disagreement_dates':sorted(mismatch_dates),
  'margin_e_coverage':{'min':float(margin_coverage.min()),'mean':float(margin_coverage.mean()),'max':float(margin_coverage.max()),
                       'complete_days':int((margin_coverage==1).sum()),'last_day':float(margin_coverage.iloc[-1])},
  'metric_nonnull_counts':{k:int(metrics[k].notna().sum()) for k in METRICS},
  'last_day':str(days[-1].date()),'last_day_nonnull':int(metrics.complete_metric_count.iloc[-1]),
  'last_day_missing':[k for k in METRICS if pd.isna(metrics[k].iloc[-1])],
  'past40_baseline_ready_all17_days':int(all_ready.sum()),
  'past40_baseline_ready_16plus_days':int((baseline_valid.sum(axis=1)>=16).sum()),
  'formal_detector_input_authority':False,'formal_escape_state_authority':False,
  'selection_authority':False,'trading_authority':'NONE',
  'blockers':['PIT_U_SECURITY_STATUS_NOT_INDEPENDENTLY_CONFIRMED',
              'HISTORICAL_SOURCE_REVISIONS_UNRECONCILED',
              'MARGIN_FULL_COHORT_INCOMPLETE',
              'NO_17_OF_17_BASELINE',
              'NO_FORMAL_OUT_OF_SAMPLE_SIGNAL_EVALUATION'],
 }
 # Track research diagnostics only; do not label those unverified days as real Escape alerts.
 metrics.to_csv(out/'historical_17_metric_research_shadow.csv',index_label='Date',float_format='%.12g')
 (out/'validation_summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 # A forbidden formal packet is intentionally made with all source gates FALSE.
 packet={'metric_contract_version':'HENGCE_ESCAPE_METRIC_CONTRACT_V1',
         'metric_contract_sha256':'1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281',
         'phase':'NEXT_DAY_RECONCILIATION','trade_date':str(days[-1].date()),
         'asof_taipei':str(days[-1].date())+'T23:59:59+08:00',
         'data_gate':{'freshness_pass':False,'integrity_pass':False,'pit_pass':False,'universe_pass':False},
         'metrics_history':{k:[None if not np.isfinite(v) else float(v) for v in metrics[k]] for k in METRICS},
         'governance':{'authority':'RESEARCH_SHADOW_ONLY','trading_authority':'NONE','no_eod_overwrite':True}}
 (out/'fail_closed_detector_packet.json').write_text(json.dumps(packet,ensure_ascii=False,allow_nan=False)+'\n')
 print(json.dumps(results,ensure_ascii=False,indent=2))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mother',required=True);ap.add_argument('--archive',required=True);ap.add_argument('--out',required=True);ap.add_argument('--through',default='2026-10-27');main(ap.parse_args())
