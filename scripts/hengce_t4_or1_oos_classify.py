#!/usr/bin/env python3
"""Apply the predeclared T4-OR1 ownership-transfer state machine to frozen OOS events.

RESEARCH ONLY. This classifier does not create/delete Monster V1 events and does
not tune any Monster/T4 threshold. TDCC is used as weekly ownership topology;
T86 and MI_MARGN are used for visible flow/funding evidence through the original
HENGCE vessel parsers.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

import hengce_eod_incremental_ingest as vessel


def fnum(x):
    if x is None:return math.nan
    s=str(x).strip().replace(',','').replace('＋','+').replace('－','-')
    if s in ('','--','---','N/A','nan','None'):return math.nan
    try:return float(s)
    except Exception:return math.nan


def weekdays(a,b):
    d=a
    while d<=b:
        if d.weekday()<5:yield d
        d+=timedelta(days=1)


def fetch_day(d):
    ds=d.strftime('%Y%m%d');iso=d.isoformat()
    try:p=vessel._price(ds,iso)
    except vessel.NotReady:return {'date':iso,'status':'NO_PRICE'}
    except Exception as e:return {'date':iso,'status':'ERROR','reason':f'PRICE:{type(e).__name__}:{e}'}
    try:i=vessel._inst(ds,iso)
    except Exception as e:return {'date':iso,'status':'ERROR','reason':f'INST:{type(e).__name__}:{e}'}
    try:m=vessel._margin(ds,iso)
    except Exception as e:return {'date':iso,'status':'ERROR','reason':f'MARGIN:{type(e).__name__}:{e}'}
    return {'date':iso,'status':'COMPLETE','price':p,'inst':i,'margin':m}


def fetch_dates(dates,workers):
    out=[]
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs={ex.submit(fetch_day,d):d for d in dates}
        for f in cf.as_completed(futs):
            r=f.result();out.append(r)
            if r['status']=='ERROR':print('FLOW_FETCH_ERROR',r,flush=True)
    out.sort(key=lambda x:x['date'])
    bad=[x for x in out if x['status']=='ERROR']
    if bad:raise RuntimeError('T4_ORIGINAL_VESSEL_FLOW_FETCH_ERROR:'+json.dumps(bad,ensure_ascii=False))
    return out


def rows_by_ticker(rows):
    return {str(r.get('Ticker')):r for r in rows}


def build_daily_map(records):
    result={}
    for r in records:
        if r['status']!='COMPLETE':continue
        p=rows_by_ticker(r['price']);i=rows_by_ticker(r['inst']);m=rows_by_ticker(r['margin'])
        result[r['date']]={'price':p,'inst':i,'margin':m}
    return result


def topology(d400,d1000,dmid,dmidh):
    if d1000>0 and dmid<0:return 'WHALE_CONCENTRATION'
    if d400>0 and dmid>0 and dmidh>=0:return 'FRESH_MID_BROADENING'
    if d400<=0 and dmid>0:return 'WHALE_FRAGMENTATION_TO_MID'
    if d400<0 and dmid<=0:return 'BIG400_DISTRIBUTION'
    return 'MIXED_STATIC'


def rotation(prior_mid,current_mid):
    if prior_mid<=0 and current_mid>0:return 'NEG_TO_POS'
    if prior_mid>0 and current_mid>0:return 'POS_TO_POS'
    if prior_mid>0 and current_mid<=0:return 'POS_TO_NEG'
    return 'NEG_TO_NEG'


def need_fields(row,fields,label):
    vals={k:fnum(row.get(k)) for k in fields}
    bad=[k for k,v in vals.items() if not math.isfinite(v)]
    if bad:raise RuntimeError(f'{label}_MISSING_FIELDS:{bad}')
    return vals


def summarize_flags(df,flags):
    out={}
    horizons=[20,40,60]
    for flag in flags:
        q=df[df[flag].eq(True)]
        z={'n_events':int(len(q))}
        for h in horizons:
            c=f'ret{h}_net40'
            if c not in q:continue
            s=pd.to_numeric(q[c],errors='coerce').dropna()
            z[str(h)]={'n':int(len(s)),'mean':float(s.mean()) if len(s) else None,
                       'median':float(s.median()) if len(s) else None,
                       'win':float((s>0).mean()) if len(s) else None}
        out[flag]=z
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--events',required=True)
    ap.add_argument('--tdcc',required=True)
    ap.add_argument('--eligibility',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--workers',type=int,default=3)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)

    ev=pd.read_csv(a.events,dtype={'Ticker':str})
    td=pd.read_csv(a.tdcc,dtype={'Ticker':str,'ReferenceDate':str})
    elig=pd.read_csv(a.eligibility,dtype={'Ticker':str})
    if not {'Date','Ticker'}.issubset(ev.columns):raise RuntimeError('EVENT_SCHEMA_BAD')
    ev['Date']=pd.to_datetime(ev['Date'],errors='raise')
    elig_key={(str(r.EventDate),str(r.Ticker)):str(r.T4Status) for r in elig.itertuples()}

    plans=[];all_dates=set()
    for r in ev.itertuples():
        ed=r.Date.date();key=(ed.isoformat(),str(r.Ticker));status=elig_key.get(key,'T4_FAIL_CLOSED_NO_ELIGIBILITY_ROW')
        if status!='ELIGIBLE':
            plans.append({'EventDate':ed.isoformat(),'Ticker':str(r.Ticker),'status':status});continue
        q=td[(td['EventDate'].astype(str)==ed.isoformat())&(td['Ticker'].astype(str)==str(r.Ticker))].copy()
        q['ReferenceDateDT']=pd.to_datetime(q['ReferenceDate'],format='%Y%m%d',errors='raise')
        q=q.sort_values('ReferenceDateDT')
        if len(q)<3:
            plans.append({'EventDate':ed.isoformat(),'Ticker':str(r.Ticker),'status':'T4_FAIL_CLOSED_INSUFFICIENT_VALID_TDCC_ROWS'});continue
        abc=q.iloc[-3:].copy();A=abc.iloc[0];B=abc.iloc[1];C=abc.iloc[2]
        b=B.ReferenceDateDT.date();c=C.ReferenceDateDT.date()
        for d in weekdays(b,c):all_dates.add(d)
        plans.append({'EventDate':ed.isoformat(),'Ticker':str(r.Ticker),'status':'ELIGIBLE','A':A,'B':B,'C':C,'Bdate':b,'Cdate':c})

    records=fetch_dates(sorted(all_dates),a.workers) if all_dates else []
    daily=build_daily_map(records)
    rows=[]
    for p in plans:
        ed=p['EventDate'];ticker=p['Ticker']
        base_row=ev[(ev['Date'].dt.strftime('%Y-%m-%d')==ed)&(ev['Ticker'].astype(str)==ticker)].iloc[0].to_dict()
        x={'EventDate':ed,'Ticker':ticker,'Name':base_row.get('Name',''),'T4Status':p['status']}
        for c in ('ret20_net40','ret40_net40','ret60_net40','mae20','mfe20','mae40','mfe40','mae60','mfe60'):
            if c in base_row:x[c]=base_row[c]
        if p['status']!='ELIGIBLE':rows.append(x);continue
        A,B,C=p['A'],p['B'],p['C']
        def own(r):
            z=need_fields(r,['Big400Shares','Big400Holders','Big1000Shares','Big1000Holders'],'TDCC')
            z['MidShares']=z['Big400Shares']-z['Big1000Shares'];z['MidHolders']=z['Big400Holders']-z['Big1000Holders'];return z
        oa,ob,oc=own(A),own(B),own(C)
        prior_mid=ob['MidShares']-oa['MidShares']; current_mid=oc['MidShares']-ob['MidShares']
        current_midh=oc['MidHolders']-ob['MidHolders']; d400=oc['Big400Shares']-ob['Big400Shares'];d1000=oc['Big1000Shares']-ob['Big1000Shares']
        top=topology(d400,d1000,current_mid,current_midh);rot=rotation(prior_mid,current_mid)
        b=p['Bdate'];c=p['Cdate']
        foreign=trust=dealer=total=0.0;margin_market=margin_cash=0.0
        close_b=close_c=math.nan;missing=[]
        for d in weekdays(b,c):
            iso=d.isoformat();day=daily.get(iso)
            if day is None:continue
            pr=day['price'].get(ticker);inst=day['inst'].get(ticker);mar=day['margin'].get(ticker)
            if pr is None or inst is None or mar is None:
                missing.append(iso);continue
            if d==b:close_b=fnum(pr.get('Close'))
            if d==c:close_c=fnum(pr.get('Close'))
            # Current interval flow excludes B endpoint and includes C endpoint: (B,C].
            if d>b:
                iv=need_fields(inst,['ForeignNet','TrustNet','DealerNet','TotalNet'],'T86')
                mv=need_fields(mar,['MarginBuy','MarginSell','MarginCashRepayment'],'MI_MARGN')
                foreign+=iv['ForeignNet'];trust+=iv['TrustNet'];dealer+=iv['DealerNet'];total+=iv['TotalNet']
                margin_market+=(mv['MarginBuy']-mv['MarginSell'])*1000.0
                margin_cash+=mv['MarginCashRepayment']*1000.0
        # endpoints are mandatory; every price day in (B,C] for this ticker must have T86+margin.
        expected=[]
        for d in weekdays(b,c):
            iso=d.isoformat();day=daily.get(iso)
            if day is None:continue
            if d>b:expected.append(iso)
        if missing or not math.isfinite(close_b) or not math.isfinite(close_c):
            x.update(T4Status='T4_FAIL_CLOSED_FLOW_OR_ENDPOINT_MISSING',MissingDates=';'.join(missing));rows.append(x);continue
        price_ret=close_c/close_b-1.0
        weak=price_ret<=0;msell=margin_market<0;vis=total>0;novis=total<=0
        x.update({
            'ReferenceA':A.ReferenceDate,'ReferenceB':B.ReferenceDate,'ReferenceC':C.ReferenceDate,
            'dBig400Shares':d400,'dBig1000Shares':d1000,'dMid400to1000Shares':current_mid,'dMid400to1000Holders':current_midh,
            'prior_dMid400to1000Shares':prior_mid,'CurrentTopology':top,'RotationDirection':rot,
            'IntervalPriceReturn':price_ret,'ForeignNetInterval':foreign,'TrustNetInterval':trust,'DealerNetInterval':dealer,'TotalNetInterval':total,
            'MarginMarketNetShares':margin_market,'MarginCashRepaymentShares':margin_cash,
            'Flag_CLEAN_MID_ABSORPTION':bool(weak and msell and vis and top=='FRESH_MID_BROADENING'),
            'Flag_VISIBLE_SPONSOR_STATIC':bool(weak and msell and vis and current_mid>0 and current_midh==0),
            'Flag_HIDDEN_CASH_IGNITION':bool(weak and margin_market<=0 and novis and top=='FRESH_MID_BROADENING' and current_midh>0),
            'Flag_WHALE_ABSORPTION_WARNING':bool(weak and msell and vis and top=='WHALE_CONCENTRATION'),
            'Flag_ROTATION_REVERSAL_WARNING':bool(rot=='POS_TO_NEG'),
            'Flag_PERSISTENT_CONCENTRATION_WARNING':bool(rot=='NEG_TO_NEG' and top=='WHALE_CONCENTRATION'),
        })
        rows.append(x)
    df=pd.DataFrame(rows);df.to_csv(out/'T4_OR1_OOS_EVENT_TABLE.csv',index=False)
    flags=[c for c in df.columns if c.startswith('Flag_')]
    summary={'system':'HENGCE','module':'T4_OR1','status':'RESEARCH_ONLY','event_count':int(len(df)),
             'eligible_count':int((df.T4Status=='ELIGIBLE').sum()) if 'T4Status' in df else 0,
             'fail_closed_count':int((df.T4Status!='ELIGIBLE').sum()) if 'T4Status' in df else int(len(df)),
             'fingerprints':summarize_flags(df,flags),'monster_v1_mutated':False,'no_oos_retuning':True}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    print('T4_SUMMARY',json.dumps(summary,ensure_ascii=False,default=str),flush=True)

if __name__=='__main__':main()
