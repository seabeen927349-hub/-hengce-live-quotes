#!/usr/bin/env python3
"""HENGCE Monster BUY V1 historical replay through the locked original vessel parsers.

RESEARCH ONLY. No production authority. No model mutation.

Safety / governance:
- Reuse scripts/hengce_eod_incremental_ingest.py official TWSE parsers.
- Missing required leg => fail closed; no alternate source or synthesis.
- Reconstruct the frozen 2026 Date x Ticker event ledger before any 2025 OOS output.
- A small, predeclared set of *reconstruction semantics* may be compared only against
  the frozen 2026 event identity. They are NOT selected on returns.
- Monster BUY thresholds remain exactly frozen.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

import hengce_eod_incremental_ingest as vessel

FROZEN_EVENTS = [
('2026-01-30','1303'),('2026-01-30','2312'),('2026-02-04','1802'),
('2026-02-25','8021'),('2026-03-09','2455'),('2026-03-10','2345'),
('2026-03-10','8150'),('2026-03-11','5234'),('2026-03-13','2492'),
('2026-03-23','2495'),('2026-03-25','6415'),('2026-03-26','2337'),
('2026-03-31','6285'),('2026-04-07','8112'),('2026-04-16','6116'),
('2026-04-24','4764'),('2026-04-29','6139'),('2026-05-08','8271'),
('2026-05-13','3042'),('2026-05-18','2337'),('2026-05-20','2451'),
('2026-05-27','1590'),('2026-05-29','2312'),('2026-05-29','8131'),
('2026-06-02','4571'),('2026-06-05','2408'),('2026-06-05','8021'),
('2026-06-30','6213'),('2026-07-17','2483'),('2026-07-22','2493'),
('2026-07-28','3055'),('2026-08-05','1597'),('2026-08-17','2351'),
('2026-08-17','6526'),('2026-08-20','6278'),('2026-08-25','6531'),
('2026-09-04','6271'),('2026-09-08','2360'),('2026-10-05','2305'),
('2026-10-05','2478'),
]
FROZEN_SET = set(FROZEN_EVENTS)

# Key frozen diagnostic row: not used for selection, only reported after event identity match.
FROZEN_6415 = {
    'Date':'2026-03-25','Ticker':'6415','inc30max':0.9968387776606956,
    'markup_pct':0.9136316337148804,'since_inc97':12.0,
    'ret20':0.0298245614035088,'dd60':-0.020033388981636,
    'foreign20_ratio':0.0356210134142353,'trust20_ratio':-0.0023899037614912,
    'total20_ratio':0.0319264133426877,'margin_chg20':-0.130703900964445,
    'absorb20_count':2.0,'bridge20_count':2.0,'lev_absorb20_count':2.0,
    'turnover20_med':1626873960.5,
}

@dataclass(frozen=True)
class ReconVariant:
    name: str
    dd_mode: str          # current60 or prior60
    rank_scope: str       # available or complete
    episode_mode: str     # dilation30, high_episode, candidate_edge

VARIANTS = [
    ReconVariant('V1_current60_available_dilation30','current60','available','dilation30'),
    ReconVariant('V2_prior60_available_dilation30','prior60','available','dilation30'),
    ReconVariant('V3_current60_complete_dilation30','current60','complete','dilation30'),
    ReconVariant('V4_prior60_complete_dilation30','prior60','complete','dilation30'),
    ReconVariant('V5_current60_available_high_episode','current60','available','high_episode'),
    ReconVariant('V6_current60_available_candidate_edge','current60','available','candidate_edge'),
]

NUMERIC = [
    'VolumeShares','TurnoverTWD','Open','High','Low','Close',
    'ForeignNet','TrustNet','TotalNet','MarginBalance'
]


def num(s):
    if s is None: return math.nan
    x=str(s).strip().replace(',','').replace('＋','+').replace('－','-')
    if x in ('','--','---','N/A','nan','None'): return math.nan
    try: return float(x)
    except Exception: return math.nan


def weekdays(a: date, b: date):
    d=a
    while d<=b:
        if d.weekday()<5: yield d
        d += timedelta(days=1)


def fetch_day(d: date):
    ds=d.strftime('%Y%m%d'); iso=d.isoformat()
    # Price is the market-day authority: if not published, treat as holiday/non-trading day.
    for attempt in range(4):
        try:
            p=vessel._price(ds,iso)
            break
        except vessel.NotReady as e:
            return {'date':iso,'status':'NO_PRICE','reason':str(e),'price':None,'inst':None,'margin':None}
        except Exception as e:
            if attempt==3: return {'date':iso,'status':'ERROR','reason':f'PRICE:{type(e).__name__}:{e}'}
            time.sleep(1.2*(attempt+1))
    out={'date':iso,'price':p}
    for key,fn in [('inst',vessel._inst),('margin',vessel._margin)]:
        last=None
        for attempt in range(5):
            try:
                out[key]=fn(ds,iso); last=None; break
            except Exception as e:
                last=e; time.sleep(1.4*(attempt+1))
        if last is not None:
            return {'date':iso,'status':'ERROR','reason':f'{key.upper()}:{type(last).__name__}:{last}',
                    'price':p,'inst':out.get('inst'),'margin':out.get('margin')}
    out['status']='COMPLETE'
    return out


def fetch_range(start: date, end: date, workers: int):
    days=list(weekdays(start,end)); records=[]
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs={ex.submit(fetch_day,d):d for d in days}
        for i,f in enumerate(cf.as_completed(futs),1):
            r=f.result(); records.append(r)
            if i%25==0 or r['status']=='ERROR':
                print('FETCH_PROGRESS',i,'/',len(days),r['date'],r['status'],flush=True)
    records.sort(key=lambda x:x['date'])
    return records


def merge_records(records):
    frames=[]; coverage=[]; fatal=[]
    for r in records:
        cov={'Date':r['date'],'status':r['status'],'price_rows':0,'institutional_rows':0,'margin_rows':0,'reason':r.get('reason','')}
        if r['status']=='NO_PRICE': coverage.append(cov); continue
        if r['status']!='COMPLETE': fatal.append(r); coverage.append(cov); continue
        p=pd.DataFrame(r['price']); inst=pd.DataFrame(r['inst']); m=pd.DataFrame(r['margin'])
        cov.update(price_rows=len(p),institutional_rows=len(inst),margin_rows=len(m))
        coverage.append(cov)
        # Preserve the price universe and exact Date x Ticker matching. Missing legs remain NaN.
        inst_cols=['Date','Ticker','ForeignNet','TrustNet','TotalNet']
        m_cols=['Date','Ticker','MarginBalance']
        x=p.merge(inst[inst_cols],on=['Date','Ticker'],how='left',validate='one_to_one')
        x=x.merge(m[m_cols],on=['Date','Ticker'],how='left',validate='one_to_one')
        frames.append(x)
    if fatal:
        raise RuntimeError('OFFICIAL_THREE_LEG_FETCH_ERRORS:' + json.dumps(
            [{'date':x['date'],'reason':x.get('reason')} for x in fatal],ensure_ascii=False))
    if not frames: raise RuntimeError('NO_COMPLETE_TRADING_DAYS')
    df=pd.concat(frames,ignore_index=True)
    for c in NUMERIC: df[c]=df[c].map(num)
    df['Ticker']=df['Ticker'].astype(str)
    df['Date']=pd.to_datetime(df['Date'])
    df=df.sort_values(['Ticker','Date']).reset_index(drop=True)
    return df,pd.DataFrame(coverage)


def rolling_sum(g, c, n): return g[c].rolling(n,min_periods=n).sum().reset_index(level=0,drop=True)
def rolling_med(g, c, n): return g[c].rolling(n,min_periods=n).median().reset_index(level=0,drop=True)
def rolling_count(g,c,n): return g[c].rolling(n,min_periods=n).count().reset_index(level=0,drop=True)


def prepare_base(df, dd_mode):
    z=df.copy(); g=z.groupby('Ticker',group_keys=False,sort=False)
    z['ret1']=g['Close'].pct_change(1,fill_method=None)
    z['ret20']=g['Close'].pct_change(20,fill_method=None)
    z['margin_chg1']=g['MarginBalance'].pct_change(1,fill_method=None)
    z['margin_chg20']=g['MarginBalance'].pct_change(20,fill_method=None)
    v20=rolling_sum(g,'VolumeShares',20)
    z['foreign20_ratio']=rolling_sum(g,'ForeignNet',20)/v20
    z['trust20_ratio']=rolling_sum(g,'TrustNet',20)/v20
    z['total20_ratio']=rolling_sum(g,'TotalNet',20)/v20
    z['dealer20_ratio']=z['total20_ratio']-z['foreign20_ratio']-z['trust20_ratio']
    z['turnover20_med']=rolling_med(g,'TurnoverTWD',20)
    if dd_mode=='current60':
        hi=g['Close'].rolling(60,min_periods=60).max().reset_index(level=0,drop=True)
    elif dd_mode=='prior60':
        hi=g['Close'].transform(lambda s:s.shift(1).rolling(60,min_periods=60).max())
    else: raise ValueError(dd_mode)
    z['dd60']=z['Close']/hi-1.0
    # fail-closed 20-session leg completeness; this reproduces the 2026-10-07 gap policy.
    req=['Close','VolumeShares','TurnoverTWD','ForeignNet','TrustNet','TotalNet','MarginBalance']
    ok=pd.Series(True,index=z.index)
    for c in req:
        ok &= rolling_count(g,c,20).eq(20)
    z['complete20']=ok
    z['complete60']=rolling_count(g,'Close',60).eq(60)
    z['score_complete']=z['complete20'] & z['complete60'] & z[['ret20','dd60','foreign20_ratio','trust20_ratio','total20_ratio','margin_chg20']].notna().all(axis=1)
    daily_req=z[['ret1','ForeignNet','TrustNet','TotalNet','MarginBalance']].notna().all(axis=1)
    z['dealer_proxy']=z['TotalNet']-z['ForeignNet']-z['TrustNet']
    supply=(z['ret1']>=0.03)&(z['TotalNet']<0)&daily_req
    bridge=supply&(z['ForeignNet']<0)&(z['dealer_proxy']>0)
    lev=supply&(z['margin_chg1']>=0.01)
    # NaN on incomplete daily evidence so rolling min_periods=20 is truly fail closed.
    z['_supply']=supply.astype(float).where(daily_req)
    z['_bridge']=bridge.astype(float).where(daily_req)
    z['_lev']=lev.astype(float).where(daily_req & z['margin_chg1'].notna())
    g2=z.groupby('Ticker',group_keys=False,sort=False)
    z['absorb20_count']=rolling_sum(g2,'_supply',20)
    z['bridge20_count']=rolling_sum(g2,'_bridge',20)
    z['lev_absorb20_count']=rolling_sum(g2,'_lev',20)
    return z


def rank_pct(s): return s.rank(method='average',pct=True)


def score_daily(base, rank_scope):
    z=base.copy()
    parts=[]
    for _,d in z.groupby('Date',sort=True):
        q=d.copy(); complete=q['score_complete']
        if rank_scope=='complete':
            def rp(c, inv=False):
                s=q[c].where(complete); return rank_pct(-s if inv else s)
        elif rank_scope=='available':
            def rp(c, inv=False):
                s=q[c]; return rank_pct(-s if inv else s)
        else: raise ValueError(rank_scope)
        q['r_ret20']=rp('ret20')
        q['_inc_raw']=(rp('dd60',True)+rp('foreign20_ratio')+rp('trust20_ratio',True)+rp('margin_chg20',True))/4.0
        q['_markup_raw']=(q['r_ret20']+rp('foreign20_ratio')+rp('total20_ratio')+rp('margin_chg20',True))/4.0
        q.loc[~complete,['_inc_raw','_markup_raw']]=math.nan
        q['incubation_pct']=rank_pct(q['_inc_raw'])
        q['markup_pct']=rank_pct(q['_markup_raw'])
        parts.append(q)
    z=pd.concat(parts,ignore_index=True).sort_values(['Ticker','Date']).reset_index(drop=True)
    g=z.groupby('Ticker',group_keys=False,sort=False)
    z['inc30max']=g['incubation_pct'].rolling(30,min_periods=1).max().reset_index(level=0,drop=True)
    # sessions since most recent daily Incubation >=P97
    since=[]
    for _,d in z.groupby('Ticker',sort=False):
        last=None
        for i,flag in enumerate((d['incubation_pct']>=0.97).fillna(False).tolist()):
            if flag:last=i
            since.append(math.nan if last is None else float(i-last))
    z['since_inc97']=since
    z['candidate']=(
        z['score_complete'] & (z['inc30max']>=0.97) & (z['markup_pct']>=0.90) &
        (z['absorb20_count']>=1) & (z['bridge20_count']>=1) &
        (z['margin_chg20']<0) & (z['lev_absorb20_count']>=1) &
        (z['turnover20_med']>=50_000_000)
    )
    return z


def emit_events(z, mode):
    out=[]
    for ticker,d in z.groupby('Ticker',sort=False):
        d=d.sort_values('Date').copy()
        if mode=='candidate_edge':
            e=d['candidate'] & ~d['candidate'].shift(1,fill_value=False)
        elif mode=='dilation30':
            # One event per connected recent-30 Incubation episode; reset only once the
            # recent-30 anchor condition is absent. This is the natural frozen episode rule.
            emitted=False; vals=[]
            for active,cand in zip((d['inc30max']>=0.97).fillna(False),d['candidate'].fillna(False)):
                if not active: emitted=False
                fire=bool(active and cand and not emitted)
                if fire: emitted=True
                vals.append(fire)
            e=pd.Series(vals,index=d.index)
        elif mode=='high_episode':
            # Episode starts on a fresh daily crossing into Incubation >=P97; first later
            # candidate within 30 sessions may fire once for that episode.
            high=(d['incubation_pct']>=0.97).fillna(False)
            starts=high & ~high.shift(1,fill_value=False)
            current_start=None; emitted=False; vals=[]
            for i,(st,cand) in enumerate(zip(starts,d['candidate'].fillna(False))):
                if st: current_start=i; emitted=False
                if current_start is not None and i-current_start>29:
                    current_start=None; emitted=False
                fire=bool(current_start is not None and cand and not emitted)
                if fire: emitted=True
                vals.append(fire)
            e=pd.Series(vals,index=d.index)
        else: raise ValueError(mode)
        if e.any(): out.append(d.loc[e])
    if not out: return z.iloc[0:0].copy()
    return pd.concat(out,ignore_index=True).sort_values(['Date','Ticker']).reset_index(drop=True)


def compare(events, validation_end):
    e=events[events['Date']<=pd.Timestamp(validation_end)]
    got=set((d.strftime('%Y-%m-%d'),str(t)) for d,t in zip(e['Date'],e['Ticker']))
    tp=len(got & FROZEN_SET); extra=sorted(got-FROZEN_SET); missing=sorted(FROZEN_SET-got)
    return {'n_got':len(got),'n_frozen':len(FROZEN_SET),'tp':tp,'extra_n':len(extra),'missing_n':len(missing),
            'exact':got==FROZEN_SET,'extra':extra,'missing':missing}


def add_outcomes(events, base):
    if events.empty:return events
    rows=[]
    lookup={t:d.sort_values('Date').reset_index(drop=True) for t,d in base.groupby('Ticker',sort=False)}
    for _,r in events.iterrows():
        t=str(r['Ticker']); d=lookup[t]; hits=d.index[d['Date'].eq(r['Date'])].tolist()
        x=r.to_dict()
        if not hits: rows.append(x); continue
        i=hits[0]
        if i+1<len(d): x['entry_date']=d.loc[i+1,'Date']; x['entry_open']=d.loc[i+1,'Open']
        else: x['entry_date']=pd.NaT; x['entry_open']=math.nan
        for h in (5,10,20,40,60):
            j=i+h
            if j<len(d) and pd.notna(x.get('entry_open')) and x['entry_open']>0:
                exit_close=d.loc[j,'Close']; raw=exit_close/x['entry_open']-1.0
                x[f'ret{h}_net40']=raw-0.004
                w=d.iloc[i+1:j+1]
                if len(w):
                    x[f'mae{h}']=w['Low'].min()/x['entry_open']-1.0
                    x[f'mfe{h}']=w['High'].max()/x['entry_open']-1.0
            else:
                x[f'ret{h}_net40']=math.nan;x[f'mae{h}']=math.nan;x[f'mfe{h}']=math.nan
        rows.append(x)
    return pd.DataFrame(rows)


def compact_event_cols(df):
    cols=['Date','Ticker','Name','Close','inc30max','markup_pct','since_inc97','r_ret20','ret20','dd60',
          'foreign20_ratio','trust20_ratio','total20_ratio','dealer20_ratio','margin_chg20',
          'absorb20_count','bridge20_count','lev_absorb20_count','turnover20_med','entry_date','entry_open',
          'ret5_net40','mae5','mfe5','ret10_net40','mae10','mfe10','ret20_net40','mae20','mfe20',
          'ret40_net40','mae40','mfe40','ret60_net40','mae60','mfe60']
    return df[[c for c in cols if c in df.columns]].copy()


def summarize_oos(e):
    out={'signals':int(len(e))}
    for h in (5,10,20,40,60):
        c=f'ret{h}_net40'; s=e[c].dropna() if c in e else pd.Series(dtype=float)
        out[str(h)]={'n':int(len(s)),'mean':float(s.mean()) if len(s) else None,
                     'median':float(s.median()) if len(s) else None,
                     'win':float((s>0).mean()) if len(s) else None}
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--start',default='2025-06-02')
    ap.add_argument('--validation-end',default='2026-10-05')
    ap.add_argument('--oos-start',default='2025-10-31')
    ap.add_argument('--oos-end',default='2025-12-26')
    ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--out',default='out/monster_v1_2025_oos')
    a=ap.parse_args(); out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    start=datetime.strptime(a.start,'%Y-%m-%d').date(); end=datetime.strptime(a.validation_end,'%Y-%m-%d').date()
    recs=fetch_range(start,end,a.workers)
    base,coverage=merge_records(recs); coverage.to_csv(out/'coverage.csv',index=False)
    print('TRADING_DAYS',int((coverage.status=='COMPLETE').sum()),'FROM',a.start,'TO',a.validation_end,flush=True)
    diagnostics=[]; variant_events={}
    for v in VARIANTS:
        b=prepare_base(base,v.dd_mode); s=score_daily(b,v.rank_scope); ev=emit_events(s,v.episode_mode)
        cmp=compare(ev,a.validation_end); cmp.update(variant=v.name,dd_mode=v.dd_mode,rank_scope=v.rank_scope,episode_mode=v.episode_mode)
        diagnostics.append(cmp); variant_events[v.name]=(s,ev)
        print('RECON',v.name,'TP',cmp['tp'],'GOT',cmp['n_got'],'EXTRA',cmp['extra_n'],'MISSING',cmp['missing_n'],'EXACT',cmp['exact'],flush=True)
    # save clean diagnostics without huge nested lists in csv; detailed JSON keeps lists.
    pd.DataFrame([{k:v for k,v in x.items() if k not in ('extra','missing')} for x in diagnostics]).to_csv(out/'reconstruction_variants.csv',index=False)
    (out/'reconstruction_diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding='utf-8')
    exact=[x for x in diagnostics if x['exact']]
    if not exact:
        best=sorted(diagnostics,key=lambda x:(-x['tp'],x['extra_n']+x['missing_n'],x['extra_n']))[0]
        (out/'summary.json').write_text(json.dumps({'status':'FAIL_CLOSED_RECONSTRUCTION_MISMATCH','best_variant':best},ensure_ascii=False,indent=2),encoding='utf-8')
        raise SystemExit('FAIL_CLOSED: no predeclared reconstruction semantics exactly reproduced the frozen 40-event ledger')
    # deterministic priority follows VARIANTS order if more than one reconstruction is identity-equivalent.
    chosen=next(x for v in VARIANTS for x in exact if x['variant']==v.name)
    scored,ev=variant_events[chosen['variant']]
    ev2=add_outcomes(ev,base)
    compact_event_cols(ev2).to_csv(out/'reconstructed_2026_events.csv',index=False)
    # 6415 numeric diagnostic
    q=ev2[(ev2['Date']==pd.Timestamp(FROZEN_6415['Date']))&(ev2['Ticker'].astype(str)==FROZEN_6415['Ticker'])]
    diag6415={}
    if len(q):
        r=q.iloc[0]
        for k,val in FROZEN_6415.items():
            if k in ('Date','Ticker'):continue
            got=r.get(k,math.nan); diag6415[k]={'got':None if pd.isna(got) else float(got),'frozen':float(val),
                                               'abs_diff':None if pd.isna(got) else abs(float(got)-float(val))}
    # OOS is emitted only after exact 2026 event identity reconstruction.
    o0=pd.Timestamp(a.oos_start);o1=pd.Timestamp(a.oos_end)
    oos=ev2[(ev2['Date']>=o0)&(ev2['Date']<=o1)].copy()
    compact_event_cols(oos).to_csv(out/'monster_v1_2025_oos_events.csv',index=False)
    summary={'status':'PASS_RECONSTRUCTION_AND_OOS','chosen_reconstruction':chosen,
             'frozen_event_identity':'40/40 exact Date x Ticker','diagnostic_6415':diag6415,
             'oos_window':[a.oos_start,a.oos_end],'oos':summarize_oos(oos),
             'authority':'RESEARCH_ONLY_NO_PRODUCTION_AUTHORITY_NO_MODEL_MUTATION',
             'source_semantics':'HENGCE original-vessel official TWSE parsers; missing leg fail closed'}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print('SUMMARY',json.dumps(summary,ensure_ascii=False,default=str),flush=True)

if __name__=='__main__': main()
