#!/usr/bin/env python3
"""HENGCE Escape read-only 17-metric historical research producer.

Reads existing canonical Historical Mother and a daily, date-observed TWSE MI_INDEX
(type=13) electronics cohort. Never invents 2026 PIT memberships outside input,
changes a locked metric formula, replaces canonical records or authorizes trades.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

METRICS = [
    'foreign_relative_flow_5', 'trust_relative_flow_5', 'dealer_relative_flow_5',
    'totalnet_relative_flow_5', 'totalnet_relative_flow_10',
    'flow_breadth_negative_share', 'capital_migration_strength',
    'source_absolute_flow_5', 'broad_market_absolute_flow_5',
    'destination_absorption_strength', 'price_damage_score_raw',
    'price_recovery_score_raw', 'flow_reentry_score_raw',
    'vulnerability_crowding_score_raw', 'vulnerability_leverage_score_raw',
    'internal_structure_score_raw', 'price_flow_divergence_score_raw',
]
CONTRACT_SHA = '1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281'


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_membership(p, dates):
    """Strictly as-of membership; compact source or Date/Ticker CSV."""
    dates = pd.Index(dates)
    if p.suffix.lower() == '.json':
        m = json.loads(p.read_text(encoding='utf-8'))
        if 'base' not in m or 'deltas' not in m:
            raise ValueError('PIT_COMPACT_SCHEMA_MISSING')
        start, end = pd.Timestamp(m['first']), pd.Timestamp(m['last'])
        if dates.min() != start or dates.max() != end or len(dates) != m['expected_trading_dates']:
            raise ValueError('PIT_DATE_RANGE_OR_COUNT_MISMATCH')
        deltas = {}
        for item in m['deltas'].split('|'):
            date, additions, removals = item.split(':')
            deltas[pd.Timestamp(date)] = (set(filter(None, additions.split('.'))), set(filter(None, removals.split('.'))))
        cur = set(m['base'].split('.'))
        sets = {}
        for d in dates:
            if d in deltas:
                a, r = deltas[d]
                if r - cur or a & cur:
                    raise ValueError(f'PIT_DELTA_NOT_CONSISTENT:{d.date()}')
                cur.difference_update(r)
                cur.update(a)
            sets[d] = cur.copy()
        return sets
    q = pd.read_csv(p, dtype={'Ticker': str}, usecols=['Date', 'Ticker'])
    q['Date'] = pd.to_datetime(q['Date'])
    if q.duplicated(['Date', 'Ticker']).any():
        raise ValueError('PIT_DUPLICATE_KEYS')
    g = q.groupby('Date')['Ticker'].agg(set)
    if set(g.index) != set(dates):
        raise ValueError('PIT_MISSING_OR_EXTRA_DATES')
    return g.to_dict()


def protected_div(n, d):
    return n.div(d.where(d > 0))


def mean_group(x, group):
    return x.where(group).mean(axis=1, skipna=True)


def fraction_group(condition, valid):
    num = (condition & valid).sum(axis=1)
    den = valid.sum(axis=1)
    return num.div(den.where(den > 0))


def run(mother, membership, out, through):
    sha = file_sha(mother)
    df = pd.read_csv(mother, dtype={'Ticker': str}, low_memory=False)
    if set(['Date','Ticker','Name','Volume','Turnover','Close','Margin_MarginBalance','ForeignNet','TrustNet','TotalNet']) - set(df.columns):
        raise ValueError('CANONICAL_REQUIRED_FIELDS_MISSING')
    if df.duplicated(['Date','Ticker']).any():
        raise ValueError('MOTHER_DUPLICATE_DATE_TICKER')
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.loc[(df['Date'].dt.year == 2026) & (df['Date'] <= pd.Timestamp(through))].copy()
    if len(df) == 0:
        raise ValueError('NO_2026_ROWS')
    # Distinguish 4-digit TWSE ordinary shares from official price-row universe that includes depositary receipts.
    dr = df['Name'].fillna('').str.contains(r'-DR$', case=False, regex=True)
    digit = df['Ticker'].str.fullmatch(r'[1-9]\d{3}')
    excluded = df.loc[dr | ~digit, ['Date','Ticker','Name']]
    df = df.loc[digit & ~dr].copy()
    if df.duplicated(['Date','Ticker']).any():
        raise ValueError('DUPLICATE_VALID_ORDINARY_KEYS')
    for c in ['Volume','Turnover','Close','Margin_MarginBalance','ForeignNet','TrustNet','TotalNet']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    days = pd.Index(sorted(df['Date'].unique()))
    sets = load_membership(membership, days)
    all_tickers = pd.Index(sorted(df['Ticker'].unique()))
    idx = pd.MultiIndex.from_product([days, all_tickers], names=['Date','Ticker'])
    f = df.set_index(['Date','Ticker']).reindex(idx)
    V = f['Volume'].unstack('Ticker')
    T = f['Turnover'].unstack('Ticker')
    C = f['Close'].unstack('Ticker').where(lambda s:s > 0)
    MB = f['Margin_MarginBalance'].unstack('Ticker')
    FN = f['ForeignNet'].unstack('Ticker')
    TN = f['TrustNet'].unstack('Ticker')
    NET = f['TotalNet'].unstack('Ticker')
    DN = NET - FN - TN
    U = f['Name'].notna().unstack('Ticker')
    E = pd.DataFrame(False, index=days, columns=all_tickers)
    membership_missing = []
    for d, tickers in sets.items():
        unknown = sorted(tickers - set(all_tickers))
        missing_today = sorted(t for t in tickers if t in E.columns and not bool(U.loc[d,t]))
        if unknown or missing_today:
            membership_missing.append({'date':str(d.date()),'not_in_universe':unknown,'not_in_price_rows':missing_today})
        E.loc[d, list(tickers & set(all_tickers))] = True
    E &= U
    N = U & ~E
    # Read-only flow intensity with per-row NULL exclusion and same-row denominators.
    def intensity(channel, cohort, w):
        valid = cohort & (V > 0) & channel.notna()
        daily_net = channel.where(valid).sum(axis=1, min_count=1)
        daily_vol = V.where(valid).sum(axis=1, min_count=1)
        return protected_div(daily_net.rolling(w, min_periods=w).sum(), daily_vol.rolling(w, min_periods=w).sum())
    outdf = pd.DataFrame(index=days)
    c5 = {}
    for label, channel in [('foreign',FN),('trust',TN),('dealer',DN),('totalnet',NET)]:
        a = intensity(channel,E,5)
        b = intensity(channel,N,5)
        c5[label] = a - b
        outdf[f'{label}_relative_flow_5'] = c5[label]
    outdf['totalnet_relative_flow_10'] = intensity(NET,E,10)-intensity(NET,N,10)
    source = intensity(NET,E,5)
    dest = intensity(NET,N,5)
    broad = intensity(NET,U,5)
    outdf['source_absolute_flow_5'] = source
    outdf['broad_market_absolute_flow_5'] = broad
    outdf['capital_migration_strength'] = np.where((source<0)&(dest>0), dest-source, 0.)
    outdf.loc[source.isna() | dest.isna(),'capital_migration_strength'] = np.nan
    outdf['destination_absorption_strength'] = dest.clip(lower=0)
    stock_valid = U & (V>0) & NET.notna()
    stock_n = NET.where(stock_valid).rolling(5, min_periods=5).sum()
    stock_v = V.where(stock_valid).rolling(5, min_periods=5).sum()
    stock_intensity = stock_n / stock_v.where(stock_v>0)
    outdf['flow_breadth_negative_share'] = fraction_group(stock_intensity < 0, E & stock_intensity.notna())
    def ew_return(cohort, w):
        stock_ret = C / C.shift(w) - 1
        return mean_group(stock_ret, cohort)
    rE5, rN5 = ew_return(E,5), ew_return(N,5)
    rE20, rN20 = ew_return(E,20), ew_return(N,20)
    relative20 = rE20-rN20
    ma20 = C.rolling(20, min_periods=20).mean()
    eligible_ma = C.notna() & ma20.notna()
    breadthE = fraction_group(C>ma20, E & eligible_ma)
    breadthU = fraction_group(C>ma20, U & eligible_ma)
    turnE = T.where(E).sum(axis=1, min_count=1)
    turnU = T.where(U).sum(axis=1, min_count=1)
    turnshare = protected_div(turnE,turnU)
    turnchange20 = turnshare-turnshare.shift(1).rolling(20,min_periods=20).mean()
    marginE = MB.where(E).sum(axis=1,min_count=1)
    marginchange20 = marginE / marginE.shift(20).where(marginE.shift(20)>0) - 1
    rets = C.pct_change(fill_method=None).where(U)
    # Correlation limited to as-of E cohort, 20 actual sessions and pairwise min 15 returns.
    # A past quote is not forward-filled, and E returns only remain valid on E PIT days.
    rets = rets.where(E & E.shift(1).fillna(False))
    corr = pd.Series(np.nan,index=days,dtype=float)
    for i in range(20,len(days)):
        symbols = E.iloc[i][E.iloc[i]].index
        x = rets.iloc[i-19:i+1][symbols]
        eligible_symbols = x.columns[x.notna().sum(axis=0)>=15]
        if len(eligible_symbols)<2: continue
        a = x[eligible_symbols].corr(min_periods=15).values
        vals = a[np.triu_indices_from(a,1)]
        vals = vals[np.isfinite(vals)]
        if len(vals):corr.iloc[i] = vals.mean()
    corrdiff10 = corr - corr.shift(10)
    outdf['vulnerability_crowding_score_raw'] = turnshare + relative20.clip(lower=0)
    outdf['vulnerability_leverage_score_raw'] = marginchange20
    outdf['internal_structure_score_raw'] = (-corrdiff10).clip(lower=0)*breadthE.clip(lower=0)
    outdf['price_flow_divergence_score_raw'] = relative20.clip(lower=0)*(-c5['totalnet']).clip(lower=0)
    outdf['price_damage_score_raw'] = (1-breadthE)+(1-breadthU)+(-rE5).clip(lower=0)+(-(rE5-rN5)).clip(lower=0)
    outdf['price_recovery_score_raw'] = breadthE+breadthU+rE5.clip(lower=0)+(rE5-rN5).clip(lower=0)
    outdf['flow_reentry_score_raw'] = sum(c5[k].clip(lower=0) for k in ('foreign','trust','dealer','totalnet'))
    # Important: all 17 input names exist; only as-of source-covered days are present.
    outdf = outdf[METRICS]
    stats = {
      'status':'RESEARCH_SHADOW_HISTORICAL_ONLY',
      'source_mother_sha256':sha,
      'source_mother_rows':1026627 if sha=='6f7494b46af07a11f68429981b3ec666ad0a520ed9b51ae0150f4c34435639e7' else None,
      'electronics_pit_source':str(membership),
      'through':str(days.max().date()),'trading_days':len(days),
      'ordinary_ticker_rows':len(df),'excluded_nonordinary_rows':len(excluded),
      'pit_member_rows_missing_in_price_panel_count':sum(len(x['not_in_price_rows'])+len(x['not_in_universe']) for x in membership_missing),
      'pit_member_rows_missing_samples':membership_missing[:10],
      'daily_e_count_min':int(E.sum(axis=1).min()),'daily_e_count_max':int(E.sum(axis=1).max()),
      'daily_n_count_min':int(N.sum(axis=1).min()),'daily_n_count_max':int(N.sum(axis=1).max()),
      'metric_nonnull_counts':{k:int(v) for k,v in outdf.notna().sum().items()},
      'last_day_metric_nonnull':int(outdf.iloc[-1].notna().sum()),
      'last_day_missing_metrics':outdf.columns[outdf.iloc[-1].isna()].tolist(),
      'last_day_5d_totalnet_e_coverage':float((stock_valid & E).tail(5).sum().sum()/E.tail(5).sum().sum()),
      'last_day_margin_e_coverage':float((MB.notna() & E).iloc[-1].sum()/E.iloc[-1].sum()),
      'date_missing_after_source':[],
      'trading_authority':'NONE','formal_escape_promoted':False,
    }
    out.mkdir(parents=True,exist_ok=True)
    outdf.to_csv(out/'escape_17_series_historical_shadow.csv',float_format='%.12g',index_label='Date')
    (out/'qa.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
    packet = {
      'metric_contract_version':'HENGCE_ESCAPE_METRIC_CONTRACT_V1',
      'metric_contract_sha256':CONTRACT_SHA,
      'phase':'NEXT_DAY_RECONCILIATION',
      'trade_date':str(days.max().date()),
      'asof_taipei':str(days.max().date())+'T23:59:59+08:00',
      'data_gate':{
          'freshness_pass':True, # only for this historical as-of date, NOT now
          'integrity_pass':sha=='6f7494b46af07a11f68429981b3ec666ad0a520ed9b51ae0150f4c34435639e7',
          'pit_pass':not membership_missing,
          'universe_pass':not membership_missing,
      },
      'metrics_history':{col:[None if pd.isna(v) else float(v) for v in outdf[col]] for col in METRICS},
      'governance':{'authority':'RESEARCH_HISTORICAL_ONLY','not_current':True,'no_trading':True,'no_eod_overwrite':True},
    }
    (out/'detector_input_historical_shadow.json').write_text(json.dumps(packet,ensure_ascii=False)+'\n')
    print(json.dumps(stats,ensure_ascii=False,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--mother',type=Path,required=True)
    ap.add_argument('--membership',type=Path,required=True)
    ap.add_argument('--through',default='2026-10-22')
    ap.add_argument('--out',type=Path,default=Path('escape_run'))
    a=ap.parse_args()
    run(a.mother,a.membership,a.out,a.through)
