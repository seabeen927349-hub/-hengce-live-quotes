#!/usr/bin/env python3
"""Read-only audit of frozen N2 Top1 84 windows; does not select or trade securities.

Requires unmodified extracted HENGCE_N2_TOP1_5M_COMPLETE_HANDOFF_20261104.zip.
Usage: python n2_ca_execution_audit.py --input-dir /path/to/extracted_handoff --output-dir /path/to/new_output
"""
import argparse,csv,hashlib,json,zipfile,math,statistics
from pathlib import Path
import pandas as pd

BASE=5_000_000

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def verify(path,exp,size=None):
    if not path.is_file():raise FileNotFoundError(path)
    assert sha256(path)==exp,(str(path),sha256(path),exp)
    if size is not None:assert path.stat().st_size==size,(str(path),path.stat().st_size,size)

def run(inp,out):
    out.mkdir(parents=True,exist_ok=True)
    archive_manifest=json.loads((inp/'MANIFEST_SHA256.json').read_text())['files']
    for r in archive_manifest:verify(inp/r['path'],r['sha256'],r['size_bytes'])
    archives=json.loads((inp/'handoff/CANONICAL_ARCHIVE_SHA.json').read_text())
    for y in archives:verify(inp/y['file'],y['sha256'],y['size_bytes'])
    src=pd.read_csv(inp/'direct_artifacts/N2_TOP1_FIXED5M_ALL84_TRADES.csv',dtype={'ticker':str})
    assert len(src)==84 and src.signal.nunique()==84
    assert (src.initial_principal==BASE).all() and (src.budget==BASE).all()
    assert (src.shares%1000==0).all() and (src.lots*1000==src.shares).all()
    assert src.apply(lambda x: int(BASE//(float(x.entry_open)*1000))==int(x.lots),axis=1).all()
    assert (src.invested+src.unused_cash-BASE).abs().max()<1e-7
    assert (src.pnl_40bp-(src.shares*(src.exit_close-src.entry_open)-.004*src.invested)).abs().max()<.001
    assert (src.pnl_80bp-(src.shares*(src.exit_close-src.entry_open)-.008*src.invested)).abs().max()<.001
    selected=set(src.ticker)
    all_prices=[];actions=[];archives_checked=[]
    for a in archives:
        year=int(a['year'])
        with zipfile.ZipFile(inp/a['file']) as z:
            with z.open('MANIFEST.json') as f: man=json.load(f)
            # Archived manifest structure varies; retain as independent provenance, do not rewrite.
            with z.open(f'corporate_actions_{year}.csv') as f:
                c=pd.read_csv(f,dtype={'ticker':str,'date':str})
            with z.open(f'electronics_{year}.csv') as f:
                d=pd.read_csv(f,usecols=['date','ticker','close','open','high','volume_shares','turnover_ntd'],dtype={'date':str,'ticker':str})
        actions.append(c[c.ticker.isin(selected)].copy())
        all_prices.append(d[d.ticker.isin(selected)].copy())
        archives_checked.append({'year':year,'sha256':a['sha256'],'manifest_present':bool(man)})
    actions=pd.concat(actions,ignore_index=True).sort_values(['ticker','date'])
    prices=pd.concat(all_prices,ignore_index=True).sort_values(['ticker','date'])
    prices=prices.drop_duplicates(['ticker','date'])
    assert not prices.duplicated(['ticker','date']).any()
    price_groups={k:g.reset_index(drop=True) for k,g in prices.groupby('ticker')}
    rows=[];ca_events=[];entry_flags=[]
    for r in src.itertuples(index=False):
        ca=actions[(actions.ticker==r.ticker)&(actions.date>r.entry)&(actions.date<=r.exit)]
        assert len(ca)==int(r.corporate_action_count),(r.signal,r.ticker,len(ca),r.corporate_action_count)
        cash=0.0
        for c in ca.itertuples(index=False):
            # Only '息' permits mapping RIGHT+DIVIDEND amount to cash without share-ratio detail.
            kind=str(c.event_type)
            if kind=='息':
                per=float(c.rights_plus_dividend_value)
                cash+=int(r.shares)*per
            else:
                per=None
            ca_events.append({'signal':r.signal,'entry':r.entry,'exit':r.exit,'ticker':r.ticker,'ex_date':c.date,'event_type':kind,
                              'ex_previous_close':c.previous_close,'ex_reference':c.ex_reference,'raw_rights_plus_dividend_value':c.rights_plus_dividend_value,
                              'cash_per_share_proxy_when_cash_only':per,'shares':int(r.shares),'gross_cash_entitlement_proxy':int(r.shares)*per if per is not None else None,
                              'rights_stock_multiplier_certified':False,'official_distribution_record_certified':False,
                              'entitlement_status':'CASH_ONLY_EX_DATE_ENTITLEMENT_PROXY' if kind=='息' else 'RIGHTS_OR_COMBINED_DATA_BLOCKED'})
        assert all(str(x)=='息' for x in ca.event_type),f'Rights share adjustment blocked for {r.signal}'
        expected_pnl40=float(r.shares)*(float(r.exit_close)-float(r.entry_open))-.004*float(r.invested)
        expected_pnl80=float(r.shares)*(float(r.exit_close)-float(r.entry_open))-.008*float(r.invested)
        assert abs(expected_pnl40-float(r.pnl_40bp))<.001
        assert abs(expected_pnl80-float(r.pnl_80bp))<.001
        hist=price_groups[r.ticker];pos=hist.index[hist.date==r.signal].tolist()
        if len(pos)!=1: raise AssertionError(f'Missing signal {r.signal} {r.ticker}')
        ix=pos[0]
        cl=pd.to_numeric(hist.close.astype(str).str.replace(',','',regex=False),errors='coerce')
        def ret(back):
            if ix-back<0:return None
            here=float(cl.iloc[ix]);prev=float(cl.iloc[ix-back]);return float((here/prev-1)*100) if prev>0 and here>0 else None
        def dd(back):
            # 250-day high proxy only when enough observed trading days.
            if ix-back+1<0:return None
            vals=cl.iloc[ix-back+1:ix+1].dropna()
            return float((float(cl.iloc[ix])/vals.max()-1)*100) if len(vals)==back and vals.max()>0 else None
        # Signal lookback count check must respect five *stock trading observations* (not five calendar days)
        backdate=str(hist.iloc[ix-5]['date']) if ix>=5 else None
        look=actions[(actions.ticker==r.ticker)&(actions.date>backdate)&(actions.date<=r.signal)] if backdate else actions.iloc[:0]
        assert len(look)==int(r.signal_lookback_corporate_action_count),(r.signal,r.ticker,len(look),r.signal_lookback_corporate_action_count)
        raw_5=ret(5)
        # Diagnostic only: relative total return on pre-signal last 5 days, if only cash events (no re-selection).
        if backdate and len(look)>0 and all(look.event_type=='息'):
            gross_cash=float(look.rights_plus_dividend_value.sum())
            adjusted_5=float(((float(cl.iloc[ix])+gross_cash)/float(cl.iloc[ix-5])-1)*100)
        else:adjusted_5=raw_5 if len(look)==0 else None
        row={'signal':r.signal,'entry':r.entry,'exit':r.exit,'ticker':r.ticker,'shares':int(r.shares),'lots':int(r.lots),
          'price_only_pnl40':expected_pnl40,'price_only_pnl80':expected_pnl80,
          'holding_cash_events':len(ca),'holding_stock_or_mixed_events':sum(ca.event_type!='息'),
          'gross_cash_dividend_receivable_proxy':cash,'gross_dividend_accrual_pnl40':expected_pnl40+cash,
          'gross_dividend_accrual_pnl80':expected_pnl80+cash,
          'corporate_action_total_return_status':'CASH_ONLY_EX_DATES_MATCH__NET_TAX_AND_CORPORATE_REGISTRY_UNCERTIFIED' if len(ca) else 'NO_TWT49U_HOLDING_EVENT__OTHER_CORPORATE_ACTIONS_UNCERTIFIED',
          'open_fill_status':'EXECUTION_DATA_BLOCKED_NO_0900_AUCTION_TRADE_DEPTH',
          'entry_day_turnover_ntd_proxy':float(r.entry_daily_turnover_ntd),
          'entry_day_volume_shares_proxy':int(r.entry_daily_volume_shares),
          'daily_volume_participation_pct_NOT_open_fill':float(r.daily_volume_ratio)*100,
          'daily_turnover_participation_pct_NOT_open_fill':float(r.turnover_ratio)*100,
          'signal_5d_raw_price_return_pct':raw_5,
          'signal_5d_cash_only_diagnostic_return_pct':adjusted_5,
          'signal_5d_ex_cash_event_count':len(look),
          'prior_20trading_return_pct':ret(20),'prior_60trading_return_pct':ret(60),
          'prior_120trading_return_pct':ret(120),'prior_250trading_high_drawdown_pct':dd(250),
          'prior_60trading_high_drawdown_pct':dd(60)}
        rows.append(row)
        for x in look.itertuples(index=False):
            entry_flags.append({'signal':r.signal,'ticker':r.ticker,'ex_date':x.date,'event_type':x.event_type,
                'right_plus_cash_reference':x.rights_plus_dividend_value,'raw_5d_return_pct':raw_5,
                'ex_cash_diagnostic_5d_return_pct':adjusted_5,
                'signal_reselected':False})
    audit=pd.DataFrame(rows).sort_values('signal')
    events=pd.DataFrame(ca_events)
    signal_actions=pd.DataFrame(entry_flags)
    assert len(events)==4 and len(signal_actions)==9
    assert len(audit)==84 and audit.ticker.eq(src.sort_values('signal').ticker.values).all()
    assert abs(audit.price_only_pnl40.sum()-19_883_039)<.01
    assert abs(audit.price_only_pnl80.sum()-18_237_928)<.01
    assert not audit.gross_dividend_accrual_pnl40.isna().any()
    y2024=audit[audit.signal.str.startswith('2024')]
    assert len(y2024)==9 and abs(y2024.price_only_pnl40.sum()+2_643_856.4)<.01
    summary={'audit_date':'2026-11-04','scope':'READ_ONLY_FROZEN_N2_TOP1_84_FIXED_5M',
      'immutable_source':{'outer_manifest_members_checked':len(archive_manifest),'outer_manifest_mismatches':0,'annual_canonical_archives_verified':9,
        'reproduced_price_only_pnl_40bp':float(audit.price_only_pnl40.sum()),'reproduced_price_only_pnl_80bp':float(audit.price_only_pnl80.sum())},
      'holding_cash_events':len(events),'signal_lookback_ex_actions':len(signal_actions),
      'holding_rights_or_mixed_found_in_twt49u':int((events.event_type!='息').sum()),
      'dividend_adjustment':{'gross_cash_dividend_receivable_proxy_total':float(audit.gross_cash_dividend_receivable_proxy.sum()),
        'gross_cash_dividend_accrual_pnl_40bp':float(audit.gross_dividend_accrual_pnl40.sum()),
        'gross_cash_dividend_accrual_pnl_80bp':float(audit.gross_dividend_accrual_pnl80.sum()),
        'share_multipliers_for_holding_events':'all four ex-event types are cash only; held share count unchanged conditional on complete TWT49U data',
        'not_certified':'Investor after-tax cash, transaction tax/fees on exit proceeds, legal security registry, split/merger/reduction outside TWT49U, historical data availability and payment proofs'},
      'open_auction':{'individually_verified_5000000_open_fills':0,'data_blocked':84,
        'blocker':'No 09:00 auction matched quantity/price/order priority and opening bid/ask depth for historical dates; daily volume/turnover are ex-post proxies',
        'max_entry_day_turnover_fraction_pct':float(audit.daily_turnover_participation_pct_NOT_open_fill.max())},
      '2024':{'signals':len(y2024),'winners':int((y2024.price_only_pnl40>0).sum()),'losers':int((y2024.price_only_pnl40<0).sum()),
        'price_only_pnl40':float(y2024.price_only_pnl40.sum()),'cash_event_holding_count':int(y2024.holding_cash_events.sum()),
        'signal_lookback_ex_event_count':int(y2024.signal_5d_ex_cash_event_count.sum()),
        'largest_loss_signal':str(y2024.loc[y2024.price_only_pnl40.idxmin(),'signal']),
        'largest_loss_ticker':str(y2024.loc[y2024.price_only_pnl40.idxmin(),'ticker'])},
      'recommendation':'TRADING_NO_GO__ALPHA_INCONCLUSIVE__EXECUTION_DATA_BLOCKED'}
    audit.to_csv(out/'N2_TOP1_ALL84_DIVIDEND_EXECUTION_DIAGNOSTICS.csv',index=False,float_format='%.10f')
    events.to_csv(out/'HOLDING_4_CASH_DIVIDEND_ENTITLEMENTS.csv',index=False,float_format='%.10f')
    signal_actions.to_csv(out/'SIGNAL_9_EXDIVIDEND_LOOKBACK_DIAGNOSTICS.csv',index=False,float_format='%.10f')
    (out/'audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('\n2024 FEATURES:')
    print(y2024[['signal','ticker','price_only_pnl40','signal_5d_raw_price_return_pct','prior_20trading_return_pct','prior_60trading_return_pct','prior_250trading_high_drawdown_pct','signal_5d_ex_cash_event_count']].to_string(index=False))
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input-dir',required=True,type=Path);parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args();run(args.input_dir,args.output_dir)
