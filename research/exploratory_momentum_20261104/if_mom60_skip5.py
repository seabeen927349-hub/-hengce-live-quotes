#!/usr/bin/env python3
"""Single, preregistered HENGCE 60-to-5d momentum hypothesis versus frozen controls.
Historical falsification diagnostic only; not OOS, actual fill or shareholder total return.
No changes to source archives, frozen 84 transactions, or trading engine.
"""
from __future__ import annotations
import argparse, hashlib, json, math, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

BASE=5_000_000
YEARS=range(2018,2027)
COLS=['date','ticker','open','close','turnover_ntd','volume_shares']
COSTS=(0.004,0.008)


def sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _number(s):
    return pd.to_numeric(s.astype(str).str.replace(',','',regex=False),errors='coerce')


def load(src:Path):
    px=[]; cal=[]; actions=[]; provenance={}
    for y in YEARS:
        f=src/f'TWSE_ELECTRONICS_{y}.zip'
        if not f.exists():raise FileNotFoundError(f)
        provenance[str(y)]={'name':f.name,'sha256':sha(f),'size_bytes':f.stat().st_size}
        with zipfile.ZipFile(f) as z:
            manifest=json.loads(z.read('MANIFEST.json'))
            for name,meta in manifest['data_files'].items():
                raw=z.read(name)
                if hashlib.sha256(raw).hexdigest()!=meta['sha256']:
                    raise ValueError(f'SOURCE_INNER_HASH_MISMATCH year={y} {name}')
            t=pd.read_csv(z.open(f'electronics_{y}.csv'),dtype={'ticker':str,'date':str},low_memory=False)
            t=t.loc[t.ticker.str.fullmatch(r'[1-9][0-9]{3}',na=False),COLS].copy()
            for c in ['open','close','turnover_ntd','volume_shares']:
                t[c]=_number(t[c]);t[c]=t[c].where(t[c]>0)
            px.append(t)
            sessions=pd.read_csv(z.open(f'trading_sessions_{y}.csv'),dtype={'date':str})
            cal.append(sessions[['date']])
            ca=pd.read_csv(z.open(f'corporate_actions_{y}.csv'),dtype={'date':str,'ticker':str})
            actions.append(ca)
    prices=pd.concat(px,ignore_index=True)
    sessions=sorted(pd.concat(cal,ignore_index=True).date.unique().tolist())
    assert not prices.duplicated(['date','ticker']).any()
    op=prices.pivot(index='date',columns='ticker',values='open').reindex(sessions)
    cl=prices.pivot(index='date',columns='ticker',values='close').reindex(sessions)
    turn=prices.pivot(index='date',columns='ticker',values='turnover_ntd').reindex(sessions)
    vol=prices.pivot(index='date',columns='ticker',values='volume_shares').reindex(sessions)
    acts=pd.concat(actions,ignore_index=True)
    ca=acts[['date','ticker']].drop_duplicates()
    ca['event']=1
    ca_count=ca.pivot(index='date',columns='ticker',values='event').reindex(index=sessions,columns=cl.columns).fillna(0).cumsum(axis=0)
    return {'op':op,'cl':cl,'turn':turn,'vol':vol,'ca':ca_count,'session_dates':sessions,'provenance':provenance}


def choose(pool:list[str],measure:pd.Series,descending:bool=True)->str|None:
    v=measure.reindex(pool).dropna()
    if len(v)==0: return None
    return sorted(v.items(),key=lambda kv:((-kv[1] if descending else kv[1]),kv[0]))[0][0]


def trade(openp,closep,cost,vol=None,ca_events=None):
    if not np.isfinite(openp) or openp<=0:
        return {'status':'ENTRY_DATA_BLOCKED','lots':None,'pnl':None,'invested':None,'entry_daily_volume_participation':None}
    lots=math.floor(BASE/(1000*openp*(1+cost)))
    if lots==0:
        return {'status':'UNAFFORDABLE_NO_TRADE','lots':0,'pnl':0.0,'invested':0.0,'entry_daily_volume_participation':0.0}
    if not np.isfinite(closep) or closep<=0:
        return {'status':'EXIT_DATA_BLOCKED','lots':lots,'pnl':None,'invested':lots*1000*openp,'entry_daily_volume_participation':None}
    amt=lots*1000*openp
    assert amt*(1+cost)<=BASE+1e-7
    return {'status':'PRICE_ONLY','lots':lots,'pnl':lots*1000*(closep-openp)-cost*amt,'invested':amt,
            'entry_daily_volume_participation':lots*1000/vol if vol is not None and np.isfinite(vol) and vol>0 else None}


def run(src:Path,ledger:Path,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    data=load(src)
    op,cl,turn,vol,ca=(data[x] for x in ('op','cl','turn','vol','ca'))
    date_idx={d:i for i,d in enumerate(data['session_dates'])}
    med=turn.rolling(60,min_periods=50).median()
    count=turn.rolling(60,min_periods=50).count()
    ret5=cl.div(cl.shift(5)).sub(1)
    ret20=cl.div(cl.shift(20)).sub(1)
    ret60_5=cl.shift(5).div(cl.shift(60)).sub(1)
    frozen=pd.read_csv(ledger,dtype={'ticker':str,'signal':str,'entry':str,'exit':str})
    assert len(frozen)==84 and frozen.signal.nunique()==84
    records=[]; candidate_pools=[]; selection_mismatch=[]
    for event in frozen.itertuples(index=False):
        signal,entry,exitdate=event.signal,event.entry,event.exit
        assert signal in date_idx and entry in date_idx and exitdate in date_idx
        i=date_idx[signal]
        assert data['session_dates'][i+1]==entry and data['session_dates'][i+20]==exitdate
        elig=med.loc[signal].where(count.loc[signal].ge(50)&cl.loc[signal].gt(0)).dropna()
        pool=[k for k,v in sorted(elig.items(),key=lambda kv:(-kv[1],kv[0]))[:100]]
        if len(pool)!=100: raise AssertionError(('TOP100_POOL_DATA_BLOCKED',signal,len(pool)))
        n2=choose(pool,ret5.loc[signal],descending=False)
        if n2!=event.ticker:selection_mismatch.append({'signal':signal,'original':event.ticker,'reconstructed':n2})
        # Frozen baseline is never substituted even if independent reconstruction mismatches.
        rules={'N2_FROZEN':event.ticker,
               'MOM60_SKIP5':choose(pool,ret60_5.loc[signal],True),
               'MOM20_SIMPLE':choose(pool,ret20.loc[signal],True)}
        for strategy,ticker in rules.items():
            if ticker is None:
                for cost in COSTS:
                    records.append({'signal':signal,'entry':entry,'exit':exitdate,'strategy':strategy,'ticker':None,'cost':cost,'status':'SIGNAL_DATA_BLOCKED','pnl':None})
                continue
            openp=float(op.loc[entry,ticker]);closep=float(cl.loc[exitdate,ticker])
            v=vol.loc[entry,ticker]
            # signal lookback for selected corporate actions, plus holding period actions
            pre_ca=int(ca.loc[signal,ticker]-ca.loc[data['session_dates'][max(0,i-60)],ticker])
            hold_ca=int(ca.loc[exitdate,ticker]-ca.loc[signal,ticker])
            for cost in COSTS:
                tr=trade(openp,closep,cost,vol=v)
                records.append({'signal':signal,'entry':entry,'exit':exitdate,'strategy':strategy,'ticker':ticker,'cost':cost,
                                'entry_open':openp,'exit_close':closep,'prior_60_to_5_momentum':ret60_5.loc[signal,ticker],
                                'prior_20_momentum':ret20.loc[signal,ticker], 'pre_60d_company_action_count':pre_ca,
                                'holding_company_action_count':hold_ca,'nominal_open_execution':'EXECUTION_DATA_BLOCKED',
                                **tr})
        # Every potential random candidate included; no look-ahead survival filtering or replacement
        pv=[]
        for ticker in pool:
            p=float(op.loc[entry,ticker]);q=float(cl.loc[exitdate,ticker]);v=vol.loc[entry,ticker]
            pv.append({'ticker':ticker,'pnl40':trade(p,q,.004,vol=v)['pnl'], 'pnl80':trade(p,q,.008,vol=v)['pnl']})
        candidate_pools.append({'signal':signal,'rows':pv})
    assert not selection_mismatch, f'Cannot reproduce frozen 84 original Top1 selections: {selection_mismatch[:5]}'
    df=pd.DataFrame(records).sort_values(['signal','strategy','cost'])
    df.to_csv(out/'all84_three_strategies_40_80bp.csv',index=False,float_format='%.10g')
    # Fair analytic random expectation only if all 100 price paths are priced; no survivorship substitution
    random_rows=[]
    for ev in candidate_pools:
        for cost,key in ((.004,'pnl40'),(.008,'pnl80')):
            arr=pd.Series([a[key] for a in ev['rows']],dtype=float)
            random_rows.append({'signal':ev['signal'],'cost':cost,'pool_size':100,'priced_pool':int(arr.notna().sum()),
                                'unpriced_pool':int(arr.isna().sum()),'random_expected_pnl_if_complete':float(arr.mean()) if arr.notna().all() else None,
                                'observed_names_mean_diagnostic_not_fair':float(arr.mean()) if arr.notna().any() else None})
    rnd=pd.DataFrame(random_rows)
    rnd.to_csv(out/'random_null_pool_coverage.csv',index=False,float_format='%.10g')
    records=[]
    for (strategy,cost),g in df.groupby(['strategy','cost']):
        pnl=g.pnl.dropna()
        priced=bool(len(pnl)==len(g))
        firsts=sorted(pnl,reverse=True)
        records.append({'strategy':strategy,'cost':cost,'total_windows':len(g),'priced_windows':len(pnl),'blocked_windows':int(len(g)-len(pnl)),
                        'total_pnl_if_complete':float(pnl.sum()) if priced else None,
                        'partial_priced_pnl_NOT_COMPARABLE':float(pnl.sum()),
                        'mean_pnl_if_complete':float(pnl.mean()) if priced else None,
                        'win_rate_among_priced':float((pnl>0).mean()) if len(pnl) else None,
                        'pnl_excluding_largest1_if_complete':float(pnl.sum()-firsts[0]) if priced else None,
                        'pnl_excluding_largest3_if_complete':float(pnl.sum()-sum(firsts[:3])) if priced else None,
                        'holding_company_action_events':int(g.holding_company_action_count.fillna(0).gt(0).sum()),
                        'signal_last60d_company_action_events':int(g.pre_60d_company_action_count.fillna(0).gt(0).sum()),
                        'execution_data_blocked_windows':len(g)})
    summary=pd.DataFrame(records).sort_values(['strategy','cost'])
    summary.to_csv(out/'strategy_summary.csv',index=False,float_format='%.10g')
    year=df.assign(year=df.signal.str[:4]).groupby(['strategy','cost','year']).agg(trades=('signal','size'),priced=('pnl','count'),wins=('pnl',lambda a:int((a>0).sum())),pnl_priced=('pnl','sum')).reset_index()
    year['year_total_pnl_if_complete']=year.pnl_priced.where(year.trades==year.priced)
    year.to_csv(out/'yearly_pnl.csv',index=False,float_format='%.10g')
    compare=[]
    a=df[df.cost.eq(.004)].pivot(index='signal',columns='strategy',values='pnl')
    for strat in ('N2_FROZEN','MOM20_SIMPLE'):
        v=a[['MOM60_SKIP5',strat]].dropna()
        compare.append({'comparator':strat,'pairwise_priced_windows':len(v),'wins_candidate':int((v.MOM60_SKIP5>v[strat]).sum()),
                        'losses_candidate':int((v.MOM60_SKIP5<v[strat]).sum()),
                        'excess_pnl_on_priced_pairs_NOT_ALL84':float((v.MOM60_SKIP5-v[strat]).sum()),
                        'all84_pairs_priced':bool(len(v)==84)})
    pd.DataFrame(compare).to_csv(out/'pairwise_benchmarks.csv',index=False)
    pkg={'status':'EXPLORATORY_HISTORIC_NO_TRADING_PROMOTION','preregistered_git_commit':'fed0992266ae78e3c24c1067aa351d4748220575',
         'years':'2018-2026 historical already exposed, NOT OOS','frozen_events':84,
         'n2_84_selections_reconstructed':len(selection_mismatch)==0,
         'input_ledger_sha256':sha(ledger),'input_annual_zip_sha256':data['provenance'],
         'strategy_summary':summary.where(pd.notna(summary),None).to_dict(orient='records'),
         'pairwise':compare,
         'random_full_40bp_windows':int(rnd.loc[rnd.cost.eq(.004),'random_expected_pnl_if_complete'].count()),
         'selection_engineering':'CHECKED_FROZEN_N2_PARITY_84_OF_84',
         'pit_classification':'ARCHIVED_PIT_CLAIM_NOT_INDEPENDENTLY_VERIFIED',
         'corporate_actions':'NOT_TOTAL_RETURN_CERTIFIED','opening_fills':'DATA_BLOCKED_ALL',
         'future_oos':'NOT_AVAILABLE',
         'policy':'NO_GOLDEN_BACKTEST; STOP/NO-GO absent robust forward evidence and execution data'}
    (out/'summary.json').write_text(json.dumps(pkg,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(summary.to_string(index=False));print(pd.DataFrame(compare).to_string(index=False));print('Random full coverage windows:',pkg['random_full_40bp_windows'])
    return pkg


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,default=Path('/mnt/data/n2_work/handin/canonical_2018_2026'))
    ap.add_argument('--ledger',type=Path,default=Path('/mnt/data/n2_top1_fixed5m_20261104/all84_trades_fixed5m.csv'))
    ap.add_argument('--out',type=Path,default=Path('/mnt/data/n2_work/if_mom60_skip5'))
    a=ap.parse_args()
    run(a.source,a.ledger,a.out)
