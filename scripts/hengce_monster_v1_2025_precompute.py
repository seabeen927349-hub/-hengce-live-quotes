#!/usr/bin/env python3
"""Outcome-blind late-2025 Monster V1 event identity precompute.

Uses official HENGCE price/T86 parsers and the already-validated 2025 MI_MARGN
artifact. Produces all predeclared reconstruction variants without selecting one
and without computing forward outcomes. Research transport only.
"""
import argparse, json, math, time
from datetime import datetime
from pathlib import Path
import pandas as pd
import hengce_monster_v1_2025_oos_replay as m

MARGIN_ROOT=Path('input_margin/raw')
_orig_get_json=m.vessel.core.get_json
_last=[0.0]
def throttle(*args,**kwargs):
    err=None
    for k in range(6):
        gap=time.monotonic()-_last[0]
        if gap<1.25:time.sleep(1.25-gap)
        try:
            z=_orig_get_json(*args,**kwargs);_last[0]=time.monotonic();return z
        except Exception as e:
            err=e;_last[0]=time.monotonic();time.sleep(min(30,3*(2**k)))
    raise err
m.vessel.core.get_json=throttle

def parse_margin(ds,iso):
    p=MARGIN_ROOT/f'MI_MARGN_{ds}.json'
    if not p.exists():raise m.vessel.NotReady('LOCAL_VALIDATED_MARGIN_NOT_TRADING_DAY')
    q=json.loads(p.read_text(encoding='utf-8-sig'))
    if str(q.get('stat')).upper()!='OK':raise RuntimeError('MARGIN_LOCAL_STAT_NOT_OK')
    cs=list(q.get('tables') or [])
    if isinstance(q.get('fields'),list) and isinstance(q.get('data'),list):cs.append({'fields':q['fields'],'data':q['data']})
    for k,v in q.items():
        import re
        z=re.fullmatch(r'fields(\d+)',str(k))
        if z and isinstance(v,list) and isinstance(q.get('data'+z.group(1)),list):cs.append({'fields':v,'data':q['data'+z.group(1)]})
    data=None
    for t in cs:
        fs=[m.vessel.core.clean(x).replace(' ','') for x in t.get('fields') or []];d=t.get('data') or t.get('records') or []
        if len(fs)>=15 and len(d)>=500 and any('現金償還' in x for x in fs) and any('現券償還' in x for x in fs):data=d;break
    if data is None:raise RuntimeError('MARGIN_LOCAL_TABLE_NOT_FOUND')
    out=[]; import re
    for r in data:
        if not isinstance(r,(list,tuple)) or len(r)<15:continue
        s=m.vessel.core.clean(r[0]).replace('=','').replace('"','')
        if re.fullmatch(r'[1-9]\d{3}',s):
            vals=[iso,s,m.vessel.core.clean(r[1])]+[m.vessel.core.clean(x) for x in r[2:15]]+[m.vessel.core.clean(r[15]) if len(r)>15 else '',m.vessel.core.TWSE_MARGIN]
            out.append(dict(zip(m.vessel.COLS['margin'],vals)))
    return out
m.vessel._margin=parse_margin

def serial_range(a,b,workers):return m.fetch_range.__wrapped__(a,b,1) if hasattr(m.fetch_range,'__wrapped__') else _serial(a,b)
def _serial(a,b):
    rec=[]
    for i,d in enumerate(m.weekdays(a,b),1):
        r=m.fetch_day(d);rec.append(r)
        if i%20==0:print('PROGRESS',i,d,r.get('status'),flush=True)
    return rec
m.fetch_range=lambda a,b,workers:_serial(a,b)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start',default='2025-06-02');ap.add_argument('--end',default='2025-12-26');ap.add_argument('--oos-start',default='2025-10-31');ap.add_argument('--out',default='out/monster_v1_2025_precompute');a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    rec=m.fetch_range(datetime.strptime(a.start,'%Y-%m-%d').date(),datetime.strptime(a.end,'%Y-%m-%d').date(),1)
    base,cov=m.merge_records(rec);cov.to_csv(out/'coverage.csv',index=False)
    counts={}
    for v in m.VARIANTS:
        b=m.prepare_base(base,v.dd_mode);s=m.score_daily(b,v.rank_scope);ev=m.emit_events(s,v.episode_mode)
        q=ev[(ev['Date']>=pd.Timestamp(a.oos_start))&(ev['Date']<=pd.Timestamp(a.end))].copy()
        cols=['Date','Ticker','Name','Close','inc30max','markup_pct','since_inc97','r_ret20','ret20','dd60','foreign20_ratio','trust20_ratio','total20_ratio','dealer20_ratio','margin_chg20','absorb20_count','bridge20_count','lev_absorb20_count','turnover20_med']
        q[[c for c in cols if c in q]].to_csv(out/f'{v.name}.csv',index=False)
        counts[v.name]=int(len(q));print('VARIANT',v.name,'OOS_EVENTS',len(q),flush=True)
    summary={'status':'PRECOMPUTED_OUTCOME_BLIND','window':[a.oos_start,a.end],'variant_event_counts':counts,'selected_variant':None,'forward_outcomes_computed':False,'authority':'RESEARCH_ONLY_NO_MODEL_AUTHORITY'}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print('SUMMARY',json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
