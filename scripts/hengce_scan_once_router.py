#!/usr/bin/env python3
"""Authoritative router for `衡策掃一次` after mainline retirement.

v2.5 has no active HENGCE strategy. Historical Q017/Unified, E2, X12, V43 and
W1 artifacts remain readable for audit only. The router never invokes a retired
producer and can never create a new entry/order/capital authority.
"""
from __future__ import annotations
import argparse,json,subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from hengce_unified_runner import locations
from hengce_unified_contracts import ZERO_AUTHORITY, strict_loads

TZ=ZoneInfo('Asia/Taipei'); ROOT,OUTPUT_DIR=locations()
ACTION=OUTPUT_DIR/'HENGCE_INTRADAY_ACTION_BOARD.json'


def parse_now(v):
    if not v:return datetime.now(TZ)
    d=datetime.fromisoformat(v);return (d if d.tzinfo else d.replace(tzinfo=TZ)).astimezone(TZ)


def load(path):
    try:return strict_loads(Path(path).read_bytes())
    except Exception:return None


def run_step(name,argv,timeout=180):
    """Compatibility API only. v2.5 never calls this for retired producers."""
    try:
        p=subprocess.run(argv,cwd=ROOT,text=True,capture_output=True,timeout=timeout)
        return {'name':name,'return_code':p.returncode,'ok':p.returncode==0,'stdout_tail':p.stdout[-2000:],'stderr_tail':p.stderr[-2000:]}
    except Exception as e:return {'name':name,'return_code':125,'ok':False,'error':f'{type(e).__name__}:{e}'}


def refresh(now):
    """Retired-strategy scan never invokes any producer."""
    return []


def _retired_lane(label,artifact=None,reason=None):
    x={'status':'RETIRED_FROM_ACTIVE_HENGCE','lane':label,'attention_score_contribution':0,'trade_authority':0,'capital_authority_twd':0,'broker_order_execution':False}
    if reason:x['reason']=reason
    if isinstance(artifact,dict):
        x['historical_last_artifact']={
            k:artifact.get(k) for k in ('system','module','trade_date','signal_asof','engine_status','action','market_state','binding_status','status') if k in artifact
        }
    return x


def _user_positions():
    out=[]; d=ROOT/'hengce/user_actual_trades'
    if d.is_dir():
        for p in sorted(d.glob('*.json'))[-20:]:
            x=load(p)
            if isinstance(x,dict):out.append({'file':p.name,'data':x})
    return out


def _last_formal_audit():
    a=load(ACTION)
    if not isinstance(a,dict):return {'status':'NO_HISTORICAL_ACTION_ARTIFACT'}
    rows=a.get('rows') if isinstance(a.get('rows'),list) else []
    return {'status':'HISTORICAL_AUDIT_ONLY','module':a.get('module'),'generated_at':a.get('generated_at'),'binding_status':a.get('binding_status'),'row_count':len(rows),'rows_exposed':False,'authority':'ZERO'}


def build_reporting(now):
    try: import hengce_total_scoreboard as scoreboard
    except Exception as exc:
        return {'status':'DATA_PENDING_REPORTING_MODULE','reason':f'{type(exc).__name__}:{exc}',**ZERO_AUTHORITY}
    paths={
      'contract':ROOT/'hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json',
      'decision':ROOT/'hengce/HENGCE_MAINLINE_RETIREMENT_DECISION_20261026.json',
      'q':ROOT/'hengce/q017_radar/latest.json','e':ROOT/'hengce/e2_live/state_latest.json',
      'v':ROOT/'hengce/v43_daily/latest.json','w':ROOT/'hengce/w1_nextday/latest.json',
      'review':ROOT/'hengce/q017_review_10d/review_latest.json','health':ROOT/'hengce/health/latest.json',
      'prices':ROOT/'hengce/q017_radar/data/twse_electronics_history_2026.csv'}
    q,e,v,w=(load(paths[k]) for k in ('q','e','v','w'))
    try:
        prices,pdate=scoreboard.latest_prices(paths['prices'])
        sb=scoreboard.build(q,e,v,w,prices,pdate)
    except Exception as exc: sb={'status':'FAIL_CLOSED','reason':f'{type(exc).__name__}:{exc}',**ZERO_AUTHORITY}
    lanes={
      'q017_unified':_retired_lane('Q017_UNIFIED',q,'FOUR_EXECUTED_H20_NO_OVERLAP_OPERATIONS_IN_SIX_MONTHS_FAILS_PRACTICALITY_RULE'),
      'e2_profit_max':_retired_lane('E2_PROFIT_MAX',e,'ALREADY_DELETED_OR_RETIRED_PER_USER_NOT_REVALIDATED'),
      'v43':_retired_lane('V43',v,'PRIOR_SIX_MONTH_RETIREMENT'),
      'x12':_retired_lane('X12',None,'ONLY_THREE_EXECUTED_OPERATIONS_IN_SIX_MONTHS'),
      'w1_nextday':_retired_lane('W1_WIDE_TAIL',w,'FAILED_65_PERCENT_40BP_GATE_AND_RECENT_WINDOW'),
      'q1':{'status':'NOT_ACTIVE_UNVALIDATED_CHALLENGER','trade_authority':0,'attention_score_contribution':0,'action':'DO_NOT_GUESS_OR_REVIVE_OLD_MODELS'}
    }
    return {
      'schema_version':3,'status':'PASS_AUDIT_ONLY_NO_ACTIVE_STRATEGY',**ZERO_AUTHORITY,
      'active_strategy_count':0,'runtime_expected':'HENGCE_SCAN_ONCE_CONTRACT_v2_5_20261026',
      'contract':load(paths['contract']),'mainline_retirement_decision':load(paths['decision']),
      'lanes':lanes,
      'three_line_resonance':{'status':'RETIRED','trade_authority':0,'attention_score_contribution':0},
      'total_scoreboard':sb,
      'q017_10d_review':{'status':'HISTORICAL_AUDIT_ONLY','artifact_present':isinstance(load(paths['review']),dict)},
      'live_data_health':load(paths['health']) or {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'},
      'position_and_action_state':{'strategy_action':'NO_ACTIVE_STRATEGY_NO_NEW_ENTRY','user_actual_trades':_user_positions()},
      'guards':['No retired producer is invoked by 衡策掃一次.','All retired families contribute zero attention and zero trade authority.','Historical artifacts are audit-only and cannot create a buy/sell instruction.','A future active strategy requires a newly preregistered model/version.']
    }


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--now');ap.add_argument('--display-only',action='store_true');a=ap.parse_args();now=parse_now(a.now)
    out={
      'schema_version':1,**ZERO_AUTHORITY,'system':'HENGCE','module':'HENGCE_SCAN_ONCE_ROUTER',
      'architecture':'SINGLE_HENGCE','status':'RETIRED_NO_ACTIVE_STRATEGY','binding_status':'FAIL_CLOSED',
      'authority':'NO_ACTIVE_HENGCE_STRATEGY','can_create_new_entry':False,'rows':[],
      'reason':'Q017_UNIFIED_X12_V43_W1_RETIRED_AND_E2_ALREADY_DELETED_OR_RETIRED',
      'scan_once_router':{'status':'RETIRED_NO_ACTIVE_STRATEGY','command':'衡策掃一次','refresh_attempts':refresh(now),
                          'retired_producers_invoked':False,'active_strategy_count':0,'single_hengce_output':True,'score_fusion':False,'reporting_sidecar_version':'v2.5'},
      'historical_formal_output':_last_formal_audit(),
      'reporting':build_reporting(now)
    }
    print(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
