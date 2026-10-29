#!/usr/bin/env python3
"""Frozen T4-OR1 evaluator for late-2025 Monster V1 OOS events.

RESEARCH ONLY / NO PRODUCTION AUTHORITY / NO MODEL MUTATION.
Consumes an already-generated Monster V1 event CSV. Uses only official HENGCE
original-vessel TWSE parsers plus the verified ordinal TDCC parser.
"""
from __future__ import annotations
import argparse, json, math, time
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd, requests
import hengce_eod_incremental_ingest as vessel
import hengce_tdcc_monster_pit_backfill_runner as tdcc_runner

tdcc = tdcc_runner.m
TDCC_REFS=['20251031','20251107','20251114','20251121','20251128','20251205','20251212','20251219','20251226']

def n(v):
    try:return float(str(v).replace(',',''))
    except:return math.nan

def ticker_row(rows,t):
    for r in rows:
        if str(r.get('Ticker'))==str(t): return r
    return None

def eligible_refs(event_date):
    d=pd.Timestamp(event_date).date()
    out=[]
    for s in TDCC_REFS:
        r=datetime.strptime(s,'%Y%m%d').date()
        if r+timedelta(days=7) <= d: out.append(s)
    return out

def fetch_tdcc(session,ticker,ref):
    _,_,sm=tdcc.fetch_one(session,str(ticker),ref)
    return sm

def fetch_interval(ticker,s0,s1):
    # Attribution interval is (snap0, snap1] for flows; price uses snap0/snap1 closes.
    a=datetime.strptime(s0,'%Y%m%d').date(); b=datetime.strptime(s1,'%Y%m%d').date()
    days=[]; d=a
    while d<=b:
        if d.weekday()<5: days.append(d)
        d+=timedelta(days=1)
    px={}; inst_total=foreign=trust=dealer=0.0
    mbuy=msell=mcash=0.0; flow_days=0
    for d in days:
        ds=d.strftime('%Y%m%d'); iso=d.isoformat()
        try:p=vessel._price(ds,iso)
        except vessel.NotReady:continue
        pr=ticker_row(p,ticker)
        if pr: px[ds]=n(pr.get('Close'))
        if d<=a: continue
        ir=ticker_row(vessel._inst(ds,iso),ticker)
        mr=ticker_row(vessel._margin(ds,iso),ticker)
        if ir is None or mr is None: raise RuntimeError(f'MISSING_REQUIRED_LEG:{ds}:{ticker}')
        f=n(ir.get('ForeignNet')); tr=n(ir.get('TrustNet')); tot=n(ir.get('TotalNet'))
        if any(pd.isna(x) for x in (f,tr,tot)): raise RuntimeError(f'NULL_INST:{ds}:{ticker}')
        foreign+=f; trust+=tr; inst_total+=tot; dealer+=tot-f-tr
        bu=n(mr.get('MarginBuy')); se=n(mr.get('MarginSell')); ca=n(mr.get('MarginCashRepayment'))
        if any(pd.isna(x) for x in (bu,se,ca)): raise RuntimeError(f'NULL_MARGIN_FLOW:{ds}:{ticker}')
        mbuy+=bu*1000; msell+=se*1000; mcash+=ca*1000; flow_days+=1
    if s0 not in px or s1 not in px: raise RuntimeError(f'MISSING_SNAPSHOT_CLOSE:{ticker}:{s0}:{s1}')
    price_ret_pct=(px[s1]/px[s0]-1.0)*100.0
    market_net=mbuy-msell; supply=max(0.0,msell-mbuy)
    return dict(price_ret_pct=price_ret_pct,foreign=foreign,trust=trust,dealer=dealer,
                inst_total=inst_total,margin_buy_shares=mbuy,margin_sell_shares=msell,
                margin_cash_repay_shares=mcash,margin_market_net_shares=market_net,
                margin_market_supply_shares=supply,flow_days=flow_days)

def classify(x):
    base=(x['price_ret_pct']<0 and x['margin_market_supply_shares']>0 and x['inst_total']>0)
    if not base:return 'OTHER'
    if x['d_MidS']>0 and x['d_MidH']>=0 and x['d_Big1000S']<=0:return 'CLEAN_MID_RELAY'
    if x['d_MidS']<0 and x['d_Big1000S']>0:return 'WHALE_ABSORPTION'
    return 'OTHER'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--events',required=True); ap.add_argument('--out',required=True)
    a=ap.parse_args(); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    ev=pd.read_csv(a.events,dtype={'Ticker':str}); rows=[]
    sess=requests.Session(); sess.headers.update({'User-Agent':'Mozilla/5.0 HENGCE-T4-OR1-OOS/1.0','Referer':tdcc.ENDPOINT})
    for _,e in ev.iterrows():
        x=e.to_dict(); refs=eligible_refs(e['Date'])
        if len(refs)<2:
            x.update(T4_OR1_state='FAIL_CLOSED',status='FAIL_CLOSED_INSUFFICIENT_PIT_TDCC')
            rows.append(x); continue
        s0,s1=refs[-2],refs[-1]
        try:
            q0=fetch_tdcc(sess,e['Ticker'],s0); q1=fetch_tdcc(sess,e['Ticker'],s1)
            dB4H=q1['Big400Holders']-q0['Big400Holders']; dB4S=q1['Big400Shares']-q0['Big400Shares']
            dB1H=q1['Big1000Holders']-q0['Big1000Holders']; dB1S=q1['Big1000Shares']-q0['Big1000Shares']
            dMidH=dB4H-dB1H; dMidS=dB4S-dB1S
            flow=fetch_interval(e['Ticker'],s0,s1)
            x.update(status='OK',snap0=pd.to_datetime(s0).date().isoformat(),snap1=pd.to_datetime(s1).date().isoformat(),
                     d_Big400H=dB4H,d_Big400S=dB4S,d_Big1000H=dB1H,d_Big1000S=dB1S,d_MidH=dMidH,d_MidS=dMidS,**flow)
            x['T4_OR1_state']=classify(x)
        except Exception as ex:
            x.update(T4_OR1_state='FAIL_CLOSED',status=f'FAIL_CLOSED:{type(ex).__name__}:{ex}')
        rows.append(x); time.sleep(0.8)
    r=pd.DataFrame(rows); r.to_csv(out/'t4_or1_2025_oos_events.csv',index=False)
    ok=r[r['status']=='OK'] if 'status' in r else r.iloc[0:0]
    summary={'system':'HENGCE','artifact':'T4_OR1_2025_OOS','authority':'RESEARCH_ONLY_NO_PRODUCTION_AUTHORITY',
             'monster_v1_mutated':False,'t4_or1_mutated':False,'events':len(r),'ok':len(ok),
             'fail_closed':int((r['T4_OR1_state']=='FAIL_CLOSED').sum()),
             'states':r['T4_OR1_state'].value_counts(dropna=False).to_dict(),
             'frozen_definition':{'base':'price_ret_pct<0 AND margin_market_supply_shares>0 AND inst_total>0',
               'clean_mid_relay':'d_MidS>0 AND d_MidH>=0 AND d_Big1000S<=0',
               'whale_absorption':'d_MidS<0 AND d_Big1000S>0'},
             'pit_rule':'ReferenceDate+7 calendar days <= EventDate; latest two eligible snapshots; no forward fill'}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SUMMARY',json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
