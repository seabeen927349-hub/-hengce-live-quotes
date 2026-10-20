#!/usr/bin/env python3
from __future__ import annotations
import csv, importlib.util, json, tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('d', HERE/'hengce_dual_engine_display.py')
d=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(d)
TZ=ZoneInfo('Asia/Taipei')

def dt(s): return datetime.fromisoformat(s).astimezone(TZ)

def run_tests():
    stale={'schema_version':5,'module':'Q017_OLD','trade_date':'2026-10-19','binding_status':'PASS','market_state':'GO','authority':'FORMAL_Q017_DECISION_INPUT_NOT_BROKER_ORDER','formal_buy_count':1,'top3':[{'ticker':'2330'}]}
    x=d.q017_view(stale,dt('2026-10-20T07:53:00+08:00'))
    assert x['status']=='AWAITING_0901_OBSERVATION' and not x['formal_authority'] and x['top3']==[]
    x=d.q017_view(stale,dt('2026-10-20T09:03:00+08:00'))
    assert x['status']=='DATA_PENDING' and x['authority']=='NO_FORMAL_SIGNAL' and x['top3']==[]
    with tempfile.TemporaryDirectory() as td:
        h=Path(td)/'electronics.csv'
        with h.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['date','ticker']);w.writeheader();w.writerow({'date':'2026-10-19','ticker':'2330'})
        old=d.ELECTRONICS_HISTORY; d.ELECTRONICS_HISTORY=h
        try:
            bad={**stale,'trade_date':'2026-10-20','top3':[{'ticker':'1709'}]}
            y=d.q017_view(bad,dt('2026-10-20T09:03:00+08:00'))
            assert not y['formal_authority'] and y['formal_buy_count']==0 and y['top3']==[] and 'OUTSIDE_TWSE_ELECTRONICS' in y['reason']
            good={**stale,'trade_date':'2026-10-20','top3':[{'ticker':'2330'}]}
            y=d.q017_view(good,dt('2026-10-20T09:03:00+08:00'))
            assert y['formal_authority'] and y['top3'][0]['ticker']=='2330'
        finally: d.ELECTRONICS_HISTORY=old
    e={'schema_version':2,'module':'E2_PROFIT_MAX_STATE','engine_status':'ON','binding_status':'PASS','authority':'VALIDATED_RESEARCH_SIGNAL_DISPLAY','signal_asof':'2026-10-19','top1':{'ticker':'3026'},'action':'ENTRY_PENDING'}
    ev=d.e2_view(e); assert ev['top1']['ticker']=='3026' and ev['broker_order_execution'] is False and ev['capital_authority_twd']==0
    weekend=d.q017_view(stale,dt('2026-10-25T10:00:00+08:00')); assert weekend['status']=='NO_TWSE_SESSION_EXPECTED'
    return True

if __name__=='__main__':
    run_tests(); print(json.dumps({'status':'PASS','tests':6,'legacy_v3_display_authority':False,'mixed_ranking_forbidden':True}))
