#!/usr/bin/env python3
"""HENGCE G3 A1: locked 4-week TDCC Big400 vs foreign trading participation.

Retrospective aggregate behavior description, no price targets, no returns.
Version frozen after G2 protocol lock 2026-11-07.
"""
import hashlib,gzip,json,math,time,os
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
ROOT=Path('/mnt/data/hengce_behavior_audit')
D=ROOT/'HENGCE_FULL_MARKET_MOTHER_RESEARCH_2018_2026.csv.gz'
S=ROOT/'G1_TDCC_TWSE_DESCRIPTIVE_ELIGIBLE_2018_2026.csv.gz'
OUT=ROOT/'G3_A1_RESULTS';OUT.mkdir(exist_ok=True)
DAILY_HASH='b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93'
SCOPE_HASH='0d708990cafdc679a7f92ab0ca49363acbde93bf64490e446a81c2ffdb414cb6'
def filehash(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for v in iter(lambda:f.read(8*1024*1024),b''):h.update(v)
 return h.hexdigest()
def p(msg):print(msg,flush=True)
assert filehash(D)==DAILY_HASH and filehash(S)==SCOPE_HASH
p('G3_A1_SOURCE_HASH_PASS')
scope=pd.read_csv(S,compression='gzip',dtype={'SnapshotDate':str,'Ticker':str},low_memory=False)
assert len(scope)==443341
weeks=np.sort(scope['SnapshotDate'].unique())
# Source G1 candidate spans all 457 official TDCC weeks; confirm.
assert len(weeks)==457 and weeks[0]=='20180105' and weeks[-1]=='20261106'
idx={x:i for i,x in enumerate(weeks)}
scope['week_idx']=scope['SnapshotDate'].map(idx).astype(np.int32)
scope['Big400Pct']=pd.to_numeric(scope['Big400Pct'],errors='coerce')
scope['OfficialIdentityCaution']=scope['OfficialIdentityCaution'].fillna('')
# The registered primary A1 dataset retains current-roster conflict rows but presents
# a predeclared clean sensitivity excluding them; no present-survivor filter.
scope=scope[['Ticker','SnapshotDate','week_idx','Big400Pct','OfficialIdentityCaution']]
scope=scope[scope['week_idx']%4==0].copy()
p('G3_A1_TDCC_ROWS_ANCHOR '+str(len(scope)))
# Compute prior value only from four global weeks earlier.  NOTE: we must retrieve
# the entire scope for matching prior t-4, not only anchor weeks.
prev=pd.read_csv(S,compression='gzip',usecols=['SnapshotDate','Ticker','Big400Pct'],dtype={'SnapshotDate':str,'Ticker':str},low_memory=False)
prev['week_idx']=prev['SnapshotDate'].map(idx).astype(np.int32)+4
prev['prev_big400pct']=pd.to_numeric(prev['Big400Pct'],errors='coerce')
prev=prev[['Ticker','week_idx','prev_big400pct']]
scope=scope.merge(prev,on=['Ticker','week_idx'],how='left',validate='one_to_one')
scope['tdcc_delta_4w']=scope['Big400Pct']-scope['prev_big400pct']
# Daily original TWSE rows; no future returns, no close prices. Missing foreign
# numeric fields remain NaN. Data is reduced to weekly sums on known global
# reference-date boundaries, never using data after the weekly reference date.
p('G3_A1_LOAD_TWSE_DAILY_START')
daily=pd.read_csv(D,compression='gzip',usecols=['Date','Ticker','Volume','ForeignNet'],dtype={'Date':str,'Ticker':str,'Volume':str,'ForeignNet':str},low_memory=False)
assert len(daily)==2111682
idxdate=pd.to_datetime(weeks,format='%Y%m%d').to_numpy()
ddate=pd.to_datetime(daily['Date'],errors='coerce').to_numpy()
wi=np.searchsorted(idxdate,ddate,side='left')
daily['week_idx']=wi
# Dates later than the last TDCC snapshot cannot enter the weekly record.
daily=daily[daily['week_idx']<len(weeks)].copy()
for k in ['Volume','ForeignNet']:
 daily[k]=pd.to_numeric(daily[k].replace({'--':None,'':None}),errors='coerce')
daily['ForeignValid']=daily['ForeignNet'].notna().astype(np.int8)
daily['VolumeValid']=daily['Volume'].notna().astype(np.int8)
agg=daily.groupby(['Ticker','week_idx'],as_index=False,sort=True,observed=True).agg(
 foreign_sum=('ForeignNet','sum'),volume_sum=('Volume','sum'),n_days=('Date','size'),n_foreign_valid=('ForeignValid','sum'),n_volume_valid=('VolumeValid','sum'))
agg=agg.sort_values(['Ticker','week_idx']).reset_index(drop=True)
p('G3_A1_DAILY_WEEK_GROUPS '+str(len(agg)))
for col in ['foreign_sum','volume_sum','n_days','n_foreign_valid','n_volume_valid']:
 agg[col+'_4w']=agg.groupby('Ticker',sort=False)[col].transform(lambda s:s.rolling(4,min_periods=4).sum())
agg['week_idx_tminus3']=agg.groupby('Ticker',sort=False)['week_idx'].shift(3)
agg['foreign_flow_4w']=agg['foreign_sum_4w']/agg['volume_sum_4w']
complete=(agg['week_idx']-agg['week_idx_tminus3']==3)&(agg['n_days_4w']==agg['n_foreign_valid_4w'])&(agg['n_days_4w']==agg['n_volume_valid_4w'])&(agg['volume_sum_4w']>0)
agg.loc[~complete,'foreign_flow_4w']=np.nan
scope=scope.merge(agg[['Ticker','week_idx','foreign_flow_4w']],on=['Ticker','week_idx'],how='left',validate='one_to_one')
scope=scope[(scope['SnapshotDate']>='20180101')&(scope['SnapshotDate']<='20221231')&(scope['prev_big400pct'].notna())&(scope['foreign_flow_4w'].notna())].copy()
assert not scope.empty
# Rank-correlation within each non-overlapping anchor week; market means are
# conditioned away by within-week ranking. No forward price or future-return label.
RNG=np.random.default_rng(20261107)
week_groups=[];detail=[];annual={}
for week,g in scope.groupby('week_idx',sort=True):
 if len(g)<25:continue
 a=g['tdcc_delta_4w'].to_numpy(dtype=float)
 b=g['foreign_flow_4w'].to_numpy(dtype=float)
 x=rankdata(a,method='average');y=rankdata(b,method='average')
 x=x-x.mean();y=y-y.mean();den=np.linalg.norm(x)*np.linalg.norm(y)
 if den==0:continue
 x=x/np.linalg.norm(x);y=y/np.linalg.norm(y)
 rho=float(x@y)
 week_groups.append((x,y))
 detail.append({'snapshot_date':str(g['SnapshotDate'].iloc[0]),'year':str(g['SnapshotDate'].iloc[0])[:4],
                'week_idx':int(week),'stockweaks':int(len(g)),
                'spearman_tdcc400_change_vs_foreign_participation':rho,
                'absolute_tdcc_change_pp_median':float(np.median(abs(a))),
                'official_identity_caution_n':int((g['OfficialIdentityCaution']!='').sum())})
if not detail:raise RuntimeError('NO_ELIGIBLE_ANCHOR_WEEKS')
df=pd.DataFrame(detail)
for yr,v in df.groupby('year'):
 annual[yr]={'anchors':len(v),'total_stockepisodes':int(v['stockweaks'].sum()),
             'mean_rho':float(v['spearman_tdcc400_change_vs_foreign_participation'].mean()),
             'median_rho':float(v['spearman_tdcc400_change_vs_foreign_participation'].median())}
obs=float(df['spearman_tdcc400_change_vs_foreign_participation'].mean())
# Same-week label permutation preserves each market week's distribution exactly,
# destroying same-stock association. Market shock commonality is therefore controlled.
N=499
null=np.empty(N,float)
for i in range(N):
 null[i]=np.mean([float(x@RNG.permutation(y)) for x,y in week_groups])
if N: p('G3_A1_PERMUTATION_499_DONE')
p_empirical=(1+int((np.abs(null)>=abs(obs)).sum()))/(N+1)
p_conservative_holm_upper=min(1.0,p_empirical*6)
# Week-block bootstrap (anchors separated by non-overlapping 4w intervals).
week_rhos=df['spearman_tdcc400_change_vs_foreign_participation'].to_numpy()
boots=np.mean(RNG.choice(week_rhos,size=(999,len(week_rhos)),replace=True),axis=1)
ci=[float(x) for x in np.quantile(boots,[.025,.975])]
sgn=np.sign(obs)
same_sign=sum(np.sign(v['mean_rho'])==sgn for v in annual.values())
# Deterministic 'identity-caution' sensitivity, no tuning.
mask=scope['OfficialIdentityCaution']==''
clean_summary=[]
for t,g in scope[mask].groupby('week_idx'):
 if len(g)<25:continue
 x=g['tdcc_delta_4w'].rank().to_numpy();y=g['foreign_flow_4w'].rank().to_numpy()
 val=float(np.corrcoef(x,y)[0,1])
 if np.isfinite(val):clean_summary.append(val)
clean_mean=float(np.mean(clean_summary)) if clean_summary else None
registered_candidate=bool(abs(obs)>=.08 and same_sign>=4 and p_conservative_holm_upper<=.05)
receipt={
 'schema':'HENGCE_BEHAVIOR_ATLAS_G3_A1_RESULTS_V1',
 'status':'PASS_EXECUTED_RESEARCH_DESCRIPTIVE_ONLY',
 'pre_registered_experiment':'A1',
 'scope':'2018-2022 DISCOVERY ONLY',
 'no_forward_returns_computed':True,
 'future_price_targets_read':False,
 'point_in_time_predictive_authority':False,
 'source_daily_sha256':DAILY_HASH,
 'source_weekly_scope_sha256':SCOPE_HASH,
 'statistics':{'week_anchors':int(len(detail)),'stock_week_episodes':int(df['stockweaks'].sum()),
                'equal_weight_anchor_mean_spearman':obs,
                'anchor_median_spearman':float(np.median(week_rhos)),
                'week_anchor_bootstrap_95pct':ci,
                'within_week_ticker_shuffle_permutations':N,
                'two_sided_empirical_p':p_empirical,
                'conservative_six_test_bonferroni_p_upper':p_conservative_holm_upper,
                'same_sign_years_out_of_five':int(same_sign),
                'all_discovery_years':annual,
                'exclude_flagged_current_roster_identity_conflict_mean_rho':clean_mean,
                'total_flagged_identity_rows_in_experiments':int(df['official_identity_caution_n'].sum()),
                'pre_registered_candidate_qualifies':registered_candidate,
                'experiment_budget_used':1,'experiment_budget_max':6},
 'cautions':['Association not individual psychology and not causal','Correlation is not holding-to-return alpha',
             'No 2023-2024 replication inspected','Historical TDCC first-release time not known',
             'Even qualifying candidate must pass G4 to be called recurrent']}
(OUT/'A1_G3_RESULT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
df.to_csv(OUT/'A1_NONOVERLAPPING_WEEK_EPISODE_SCORES.csv',index=False)
print(json.dumps(receipt['statistics'],ensure_ascii=False,indent=2))
p('G3_A1_RESULT_SAVED '+str(OUT/'A1_G3_RESULT_RECEIPT.json'))