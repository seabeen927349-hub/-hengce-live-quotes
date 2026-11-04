#!/usr/bin/env python3
"""HENGCE independent monthly N0-N3 historical price-only diagnostic.

FROZEN PREREG: research/selection_baseline_audit_20261104/PREREG_PRICE_ONLY_DIAGNOSTIC.md
NO production or Selection Core candidate authority. Never edit input archives.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,zipfile
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

YEARS=range(2018,2027)
COST=0.004
SEED=20261031
DRAWS=10000
CAPITAL=1_000_000.
TOP=100
K=5
SOURCE=Path('/mnt/data/files')
OUT=Path('/mnt/data/selection_baseline_audit_20261104')
PREREG=Path('/mnt/data/HENGCE_SELECTION_BASELINE_RESEARCH_PREREG_20261104.md')


def load():
    all_prices=[]; all_sess=[]; all_ca=[]; src={}
    for year in YEARS:
        p=SOURCE/f'TWSE_ELECTRONICS_{year}.zip'
        if not p.exists(): raise FileNotFoundError(p)
        with zipfile.ZipFile(p) as z:
            man=json.loads(z.read('MANIFEST.json'))
            for name,meta in man['data_files'].items():
                dat=z.read(name)
                if hashlib.sha256(dat).hexdigest()!=meta['sha256'] or len(dat)!=meta['bytes']:
                    raise ValueError('SOURCE_HASH_OR_SIZE_MISMATCH '+name)
            df=pd.read_csv(z.open(f'electronics_{year}.csv'),dtype={'ticker':str},low_memory=False)
            df=df.loc[df.ticker.str.fullmatch('[1-9][0-9]{3}',na=False),['date','ticker','open','close','turnover_ntd']]
            for k in ('open','close','turnover_ntd'):
                df[k]=pd.to_numeric(df[k].astype(str).str.replace(',', '', regex=False),errors='coerce').where(lambda x: x>0)
            sessions=pd.read_csv(z.open(f'trading_sessions_{year}.csv'))[['date','taiex_price_index']]
            ca=pd.read_csv(z.open(f'corporate_actions_{year}.csv'),dtype={'ticker':str})[['date','ticker','event_type']]
            all_prices.append(df);all_sess.append(sessions);all_ca.append(ca)
            src[str(year)]={'archive':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'source_days':len(sessions)}
    prices=pd.concat(all_prices,ignore_index=True)
    sessions=pd.concat(all_sess,ignore_index=True).sort_values('date').reset_index(drop=True)
    corp=pd.concat(all_ca,ignore_index=True)
    if prices.duplicated(['date','ticker']).any() or sessions.duplicated(['date']).any():raise ValueError('DUPLICATE_SIGNAL_KEYS')
    dates=sessions['date'].tolist()
    op=prices.pivot(index='date',columns='ticker',values='open').reindex(index=dates)
    cl=prices.pivot(index='date',columns='ticker',values='close').reindex(index=dates)
    to=prices.pivot(index='date',columns='ticker',values='turnover_ntd').reindex(index=dates)
    m=to.rolling(60,min_periods=50).median()
    n=to.rolling(60,min_periods=50).count()
    r20=cl.div(cl.shift(20)).sub(1)
    r5=cl.div(cl.shift(5)).sub(1)
    corp['exists']=1
    cp=corp.pivot_table(index='date',columns='ticker',values='exists',aggfunc='max').reindex(index=dates,columns=cl.columns).fillna(0).cumsum(axis=0)
    taiex=pd.Series(pd.to_numeric(sessions.taiex_price_index,errors='coerce').values,index=dates)
    return op,cl,m,n,r20,r5,cp,taiex,src


def picks(r:pd.Series,descending:bool,k=K):
    if descending:return sorted(r.dropna().items(),key=lambda x:(-x[1],x[0]))[:k]
    return sorted(r.dropna().items(),key=lambda x:(x[1],x[0]))[:k]


def clean_number(x):
    return float(x) if np.isfinite(x) else None


def sim_trade(capital,px,exitpx,cost,action):
    """Fixed 1/5 starting-capital budget, one board lot. No winner substitutions."""
    records=[];entry_budget=capital/K;new_cap=capital
    for ticker,openp,closep,flag in zip(px.index,px.values,exitpx.values,action.values):
        if not np.isfinite(openp) or openp<=0:
            records.append({'ticker':ticker,'lots':0,'entry_price':None,'exit_price':clean_number(closep),'pnl':0.,'status':'ENTRY_OPEN_MISSING','corporate_action':bool(flag)})
            continue
        lots=int(math.floor(entry_budget/(openp*1000.)))
        if lots<=0:
            records.append({'ticker':ticker,'lots':0,'entry_price':float(openp),'exit_price':clean_number(closep),'pnl':0.,'status':'PRICE_TOO_HIGH_FOR_FIXED_LOT_BUDGET','corporate_action':bool(flag)})
            continue
        if not np.isfinite(closep) or closep<=0:
            records.append({'ticker':ticker,'lots':lots,'entry_price':float(openp),'exit_price':None,'pnl':None,'status':'EXIT_CLOSE_MISSING_BLOCKED','corporate_action':bool(flag)})
            continue
        invested=lots*1000*openp
        p=lots*1000*(closep-openp)-cost*invested
        new_cap+=p
        records.append({'ticker':ticker,'lots':lots,'entry_price':float(openp),'exit_price':float(closep),'pnl':float(p),'status':'PRICE_ONLY','invested':float(invested),'corporate_action':bool(flag)})
    return new_cap,records


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    op,cl,median60,count60,r20,r5,ca,taiex,src=load()
    dates=cl.index.tolist()
    # 2026-10 is incomplete; do not infer 2026-10-27 as October month-end.
    complete_months={pd.Period(x,freq='M') for x in dates if int(x[:4])<2026}
    complete_months.update(pd.Period(f'2026-{m:02d}',freq='M') for m in range(1,10))
    last_by_month={}
    for j,d in enumerate(dates):
        mo=pd.Period(d,freq='M')
        if mo in complete_months:last_by_month[mo]=j
    monthly=sorted(last_by_month.values())
    N3cap40=np.full(DRAWS,CAPITAL)
    N3cap80=np.full(DRAWS,CAPITAL)
    N3blocked=np.zeros(DRAWS,dtype=bool)
    N3ca_exposed=np.zeros(DRAWS,dtype=bool)
    rng=np.random.Generator(np.random.PCG64(SEED))
    cap={'N1':CAPITAL,'N2':CAPITAL}
    cap80={'N1':CAPITAL,'N2':CAPITAL}
    ledger=[];stats=[];event_rows=[];taiex_stats=[]
    busy_through=-1
    for idx in monthly:
        if idx<59 or idx+20>=len(dates):continue
        if idx<busy_through:continue
        ds=dates[idx];entry=dates[idx+1];exitd=dates[idx+20]
        eligible=median60.iloc[idx].where((count60.iloc[idx]>=50)&cl.iloc[idx].gt(0)&op.iloc[idx].notna())
        # Do not require future open. Current-day open is not required to be eligible; only an EOD close.
        eligible=median60.iloc[idx].where((count60.iloc[idx]>=50)&cl.iloc[idx].gt(0))
        elig=[t for t,v in sorted(eligible.dropna().items(),key=lambda x:(-x[1],x[0]))[:TOP]]
        if len(elig)<TOP:continue
        pool20=r20.loc[ds,elig];pool5=r5.loc[ds,elig]
        n1=[x[0] for x in picks(pool20,True)]
        n2=[x[0] for x in picks(pool5,False)]
        if len(n1)!=K or len(n2)!=K:continue
        busy_through=idx+20
        pxa=op.loc[entry,elig];exita=cl.loc[exitd,elig]
        flags=(ca.loc[exitd,elig]-ca.loc[ds,elig])>0
        price_valid=pxa.gt(0)&exita.gt(0)
        unpriced=int((~price_valid).sum())
        # Event-level theoretical EW N0: incompleteness is a formal blocker; report available name coverage.
        gross=(exita/pxa-1).where(price_valid)
        N0=float(gross.mean()-COST) if price_valid.all() else None
        rawN0=float(gross.mean()-COST) if gross.notna().any() else None
        taiex_ret=(taiex.loc[exitd]/taiex.loc[ds]-1) if taiex.loc[ds]>0 else np.nan
        taiex_stats.append({'signal':ds,'exit':exitd,'price_index_close_to_close_return':clean_number(taiex_ret)})
        event={'signal':ds,'entry':entry,'exit':exitd,'num_eligible':len(elig),'price_complete_eligible':int(price_valid.sum()),'num_corporate_actions_eligible':int(flags.sum()),'n0_100_complete_case':N0,'n0_observed_names_only':rawN0,'taiex_price_index_signal_to_exit':clean_number(taiex_ret)}
        for strat,selected in [('N1',n1),('N2',n2)]:
            capstart=cap[strat]
            capnew,recs=sim_trade(capstart,pxa.loc[selected],exita.loc[selected],COST,flags.loc[selected])
            capnew80,recs80=sim_trade(cap80[strat],pxa.loc[selected],exita.loc[selected],.008,flags.loc[selected])
            blocked=any(rec['status']=='EXIT_CLOSE_MISSING_BLOCKED' for rec in recs)
            if blocked:
                # The portfolio event is indeterminate, and all later book values are only a shadow carry-forward.
                # Do not count partial profits from other names in a blocked event as realized portfolio PnL.
                for rec in recs:
                    rec['diagnostic_component_pnl_before_block']=rec.get('pnl')
                    rec['pnl']=None
                    if rec['status']=='PRICE_ONLY':rec['status']='OTHER_POSITION_IN_BLOCKED_PORTFOLIO_EVENT'
                capnew=None;capnew80=None
            else:
                cap[strat]=capnew;cap80[strat]=capnew80
            event[f'{strat}_tickers']=selected
            event[f'{strat}_capital_before']=capstart
            event[f'{strat}_event_pnl']=capnew-capstart if capnew is not None else None
            event[f'{strat}_corporate_action_positions']=sum(r['lots']>0 and r['corporate_action'] for r in recs)
            event[f'{strat}_entry_missing_count']=sum(r['status']=='ENTRY_OPEN_MISSING' for r in recs)
            event[f'{strat}_exit_missing_count']=sum(r['status']=='EXIT_CLOSE_MISSING_BLOCKED' for r in recs)
            for i,rec in enumerate(recs):
                rec.update({'signal':ds,'entry':entry,'exit':exitd,'strategy':strat,'rank':i+1})
                ledger.append(rec)
            stats.append({'signal':ds,'entry':entry,'exit':exitd,'strategy':strat,'capital':cap[strat],'capital80':cap80[strat], 'blocked':blocked,'price_only_pnl':event[f'{strat}_event_pnl']})
        # N3: random samples without replacement, no extra filtering based on future exits.
        N=len(elig);ids=np.empty((DRAWS,K),dtype=np.int32)
        for k in range(K):
            new=rng.integers(N,size=DRAWS)
            if k:
                dup=(ids[:,:k]==new[:,None]).any(axis=1)
                while dup.any():
                    new[dup]=rng.integers(N,size=int(dup.sum()))
                    dup=(ids[:,:k]==new[:,None]).any(axis=1)
            ids[:,k]=new
        ov=pxa.to_numpy(dtype='float64')[ids]
        ev=exita.to_numpy(dtype='float64')[ids]
        a=flags.to_numpy(dtype='bool')[ids]
        l=np.floor(N3cap40[:,None]/K/np.where(np.isfinite(ov)&(ov>0),ov*1000,np.inf))
        inv=l*1000*np.where(np.isfinite(ov),ov,0.)
        blocked=((l>0)&(~np.isfinite(ev)|(ev<=0))).any(axis=1)
        N3blocked|=blocked
        N3ca_exposed|=((l>0)&a).any(axis=1)
        pnl=(l*1000*(np.where(np.isfinite(ev),ev,0.)-np.where(np.isfinite(ov),ov,0.))-.004*inv)
        pnl[(l<=0)|~np.isfinite(ev)]=0.
        N3cap40+=pnl.sum(axis=1)
        l80=np.floor(N3cap80[:,None]/K/np.where(np.isfinite(ov)&(ov>0),ov*1000,np.inf))
        inv80=l80*1000*np.where(np.isfinite(ov),ov,0.)
        pnl80=l80*1000*(np.where(np.isfinite(ev),ev,0.)-np.where(np.isfinite(ov),ov,0.))-.008*inv80
        pnl80[(l80<=0)|~np.isfinite(ev)]=0.
        N3cap80+=pnl80.sum(axis=1)
        event['n3_new_blocked_draws']=int(blocked.sum())
        event_rows.append(event)
    if not event_rows:raise RuntimeError('ZERO_INVESTMENT_EVENTS')
    # Save precise research trace, excluding individual ticker IDs from random simulations.
    pd.DataFrame(event_rows).to_csv(OUT/'baseline_event_summary.csv',index=False)
    pd.DataFrame(ledger).to_csv(OUT/'baseline_trade_ledger.csv',index=False)
    pd.DataFrame(stats).to_csv(OUT/'baseline_equity_on_completed_exits.csv',index=False)
    results={'authority':'RESEARCH_PRICE_ONLY_NOT_FORMAL_ALPHA','premature_2026_oct_month_end_excluded':True,'period':[dates[0],dates[-1]],'trading_sessions':len(dates),'sources':src,'pre_registration_sha256':hashlib.sha256(PREREG.read_bytes()).hexdigest(), 'rules':{'universe':'PIT electronics archived days with >=50/60 nonmissing turnover, highest median Top100','monthly_signal':'last certified month session EOD','entry':'next-session open','exit':'20th-session close','top5':True,'initial_capital':CAPITAL,'cost40bp':COST,'n3_seed':SEED,'n3_draws':DRAWS},'event_count':len(event_rows),'corporate_action_total_positions':{},'strategies':{},'n0_theoretical':{},'n3':{},'formal_alpha_verdict':'INCONCLUSIVE','data_authority':'PIT_U_SECURITY_CLASS_AND_TOTAL_RETURN_REQUIRES_INDEPENDENT_CERTIFICATION'}
    es=pd.DataFrame(event_rows);le=pd.DataFrame(ledger); st=pd.DataFrame(stats)
    for strat in ['N1','N2']:
        part=le[le.strategy==strat]
        positions=part[part.lots>0]
        trading=positions[positions.pnl.notna()]
        act=int((positions.corporate_action==True).sum())
        missing=int((positions.status=='EXIT_CLOSE_MISSING_BLOCKED').sum())
        empty=int((part.status!='PRICE_ONLY').sum())
        exits=st[st.strategy==strat]
        capseries=np.r_[CAPITAL,exits.capital.values.astype(float)]
        peak=np.maximum.accumulate(capseries)
        mdd=float(np.nanmin(capseries/peak-1)) if np.isfinite(capseries).all() else None
        per_year={}
        for year,v in trading.groupby(trading.signal.str[:4]):
            per_year[year]={'positions':len(v),'pnl':float(v.pnl.sum()),'positive_positions':int((v.pnl>0).sum()),'corp_actions':int(v.corporate_action.sum())}
        b=trading.sort_values('pnl',ascending=False)
        results['strategies'][strat]={'event_count':int(len(exits)),'selected_positions':int(len(positions)),'total_price_only_pnl':float(trading.pnl.sum()), 'capital_final_price_only_shadow_carry':float(cap[strat]),'formal_terminal_capital':None if missing>0 else float(cap[strat]),'gross_capital_return':float(cap[strat]/CAPITAL-1), 'capital_final_price_only_80bp_shadow_carry':float(cap80[strat]),'positive_positions':int((trading.pnl>0).sum()),'corp_action_exposed_positions':act,'missing_exit_price_positions':missing,'unfilled_or_unpriced_selections':empty,'max_closed_event_drawdown_price_only':mdd,'top_one_pnl':float(b.iloc[0].pnl) if len(b) else None,'remove_best_1_3_5_price_only_pnl':{str(k):float(trading.pnl.sum()-b.head(k).pnl.sum()) for k in [1,3,5]}, 'by_year':per_year,'last_3m_price_only_pnl':float(trading[trading.exit>='2026-07-27'].pnl.sum()),'last_3m_completed_events':int((exits.exit>='2026-07-27').sum()),'mean_capital_deployed_ratio_on_events':float(part.groupby('signal').invested.sum().reindex(exits.signal).fillna(0).to_numpy().dot(1/exits.capital.clip(lower=1).to_numpy())/len(exits))}
    results['taiex_reference']={'all_event_close_to_close_price_index_capital_if_reinvested':float(CAPITAL*np.prod(1+es.taiex_price_index_signal_to_exit.dropna().values)), 'first_signal':es.signal.iloc[0], 'last_exit':es.exit.iloc[-1], 'return_convention':'TAIEX close_at_signal to close_at_exit, uninvestable timing and no transaction/total-return adjustment', 'not_equivalent_to_next_open':True}
    results['n0_theoretical']={'complete_100_name_event_count':int(es.n0_100_complete_case.notna().sum()), 'total_event_count':len(es),'mean_price_only_20_session_net_return_available_only':float(es.n0_observed_names_only.mean()),'notes':'Theoretical equal-weight cohort, not 1m executable. If any stock missing open/exit, complete-cohort value blocked.'}
    valid=N3cap40[~N3blocked];valid80=N3cap80[~N3blocked]
    results['n3']={'total_draws':DRAWS,'price_complete_paths':int(len(valid)),'blocked_paths':int(N3blocked.sum()),'corporate_action_exposed_paths':int(N3ca_exposed.sum()),'median_final_capital_price_only_complete_paths':clean_number(np.median(valid)) if len(valid) else None,'mean_final_capital_price_only_complete_paths':clean_number(np.mean(valid)) if len(valid) else None,'p05_p50_p95_final_capital_price_only_complete_paths':[clean_number(np.quantile(valid,p)) for p in [.05,.5,.95]] if len(valid) else None,'median_final_capital_price_only_80bp_complete_paths':clean_number(np.median(valid80)) if len(valid80) else None,'conditional_on_future_data':'YES: complete paths only; do not treat as certified or unbiased OOS'}
    for s in ['N1','N2']:
        value=results['strategies'][s]['capital_final_price_only_shadow_carry']
        results['strategies'][s]['N3_price_complete_empirical_percentile_only']=clean_number(np.mean(valid<value)) if len(valid) else None
    results['by_year_research_event_count']={str(k):int(v) for k,v in es.groupby(es.signal.str[:4]).size().to_dict().items()}
    results['diagnostic_warnings']=[
      'Unadjusted open-to-close price-only PnL does NOT include dividends, rights, split entitlements or complete corporate actions.',
      'If any required exit close is missing, entire N1 portfolio path is unverified; later shadow capital carry-forward excludes the blocked event rather than inventing a sale.',
      'Do not exclude corporate-action paths after observing returns; they remain in price-only ledger with explicit flags.',
      'Archive PIT membership is not independently certified legal security registry.',
      'Historical mixed-vintage sources not certified immutable as-of signal date.',
      'Random comparator complete-future-path conditioning can itself bias distribution; NOT formal N3.',
      'Monthly backtests 2018–2026 were not pre-launch prospective and do not validate trading alpha.',
      'TAIEX close-to-close price index is not a capital-matched next-open tradable benchmark.',
      'Selected event gross outcome treated as exposed model-performance history; never claim pristine OOS.',
      'Partial 2026 October excluded from month-end signals.'
    ]
    (OUT/'research_summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:results[k] for k in ['event_count','strategies','n0_theoretical','n3','formal_alpha_verdict']},ensure_ascii=False,indent=2))
    return results

if __name__=='__main__':main()