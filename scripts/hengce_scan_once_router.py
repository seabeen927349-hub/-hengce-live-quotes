#!/usr/bin/env python3
"""Authoritative router for `衡策掃一次` with Q017 as the sole active HENGCE strategy.

Q017 is preserved in full. E2, X12, V43 and W1 remain retired/deleted. Legacy HENGCE
may be referenced only as existing legal geometry/formal-trigger infrastructure for a
Q017-selected ticker; it is not an active candidate source.
"""
from __future__ import annotations
import argparse,json,subprocess,sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from hengce_unified_runner import locations
from hengce_unified_contracts import ZERO_AUTHORITY, strict_loads
from hengce_q017_formal_output import Q017_ONLY_POLICY, current_decision, require_q017_publication

TZ=ZoneInfo('Asia/Taipei'); ROOT,OUTPUT_DIR=locations(); SCRIPTS=Path(__file__).resolve().parent
ACTION=OUTPUT_DIR/'HENGCE_INTRADAY_ACTION_BOARD.json'; BASE=OUTPUT_DIR/'HENGCE_UNIFIED_CANDIDATE_BASE.json'; RECEIPT=OUTPUT_DIR/'HENGCE_INTRADAY_BINDING_RECEIPT.json'

def parse_now(v):
    if not v:return datetime.now(TZ)
    d=datetime.fromisoformat(v);return (d if d.tzinfo else d.replace(tzinfo=TZ)).astimezone(TZ)

def load(path):
    try:return strict_loads(Path(path).read_bytes())
    except Exception:return None

def run_step(name,argv,timeout=180):
    try:
        p=subprocess.run(argv,cwd=ROOT,text=True,capture_output=True,timeout=timeout)
        return {'name':name,'return_code':p.returncode,'ok':p.returncode==0,'stdout_tail':p.stdout[-2000:],'stderr_tail':p.stderr[-2000:]}
    except subprocess.TimeoutExpired as e:return {'name':name,'return_code':124,'ok':False,'error':f'TIMEOUT:{e}'}
    except Exception as e:return {'name':name,'return_code':125,'ok':False,'error':f'{type(e).__name__}:{e}'}

def _trading_day(now):
    try:
        import hengce_twse_calendar as cal
        manifest,_,_=cal.load_manifest();return cal.is_trading_day(now.date(),manifest)
    except Exception:return None

def refresh(now):
    """Only the Q017-only formal bridge may run. No retired strategy producer is invoked."""
    td=_trading_day(now)
    if td is not True:return []
    try:current_decision(now,ROOT)
    except (OSError,ValueError,TypeError,KeyError,OverflowError):
        return [{'name':'q017_only_action_board','return_code':2,'ok':False,'reason':'CURRENT_SCHEMA5_OBSERVATION_BOUND_DECISION_REQUIRED'}]
    qpath=ROOT/'hengce/q017_canonical/latest.json'
    q=load(qpath)
    if not isinstance(q,dict) or q.get('trade_date')!=now.date().isoformat() or q.get('binding_status')!='PASS':
        return [{'name':'q017_only_action_board','return_code':2,'ok':False,'reason':'CURRENT_CANONICAL_Q017_ARTIFACT_REQUIRED'}]
    return [run_step('q017_only_action_board',[sys.executable,str(SCRIPTS/'hengce_q017_only_runner.py')],timeout=240)]

def _retired_lane(label,artifact=None,reason=None):
    x={'status':'RETIRED_FROM_ACTIVE_HENGCE','lane':label,'attention_score_contribution':0,'trade_authority':0,'capital_authority_twd':0,'broker_order_execution':False}
    if reason:x['reason']=reason
    if isinstance(artifact,dict):x['historical_last_artifact']={k:artifact.get(k) for k in ('system','module','trade_date','signal_asof','engine_status','action','market_state','binding_status','status') if k in artifact}
    return x

def _active_q017(radar,canonical):
    return {'status':'ACTIVE_SOLE_HENGCE_STRATEGY','family':'Q017','fully_preserved':True,
            'native_rules':(radar or {}).get('rules') or {'status':'DATA_PENDING_SCHEMA5_DECISION_REQUIRED'},
            'schema5_0901_evidence':radar if isinstance(radar,dict) else {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'},
            'canonical_daily_artifact':{'research_only':True,'formal_authority':False,'artifact':canonical if isinstance(canonical,dict) else {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'}},
            'selection_authority':'Q017_SCHEMA5_0901_ONLY','legacy_hengce_role':'GEOMETRY_AND_FORMAL_TRIGGER_INFRASTRUCTURE_ONLY_NOT_SELECTION_SOURCE'}

def _user_positions():
    out=[];d=ROOT/'hengce/user_actual_trades'
    if d.is_dir():
        for p in sorted(d.glob('*.json'))[-20:]:
            x=load(p)
            if isinstance(x,dict):out.append({'file':p.name,'data':x})
    return out

def _current_q017_action(now):
    action,base,receipt=load(ACTION),load(BASE),load(RECEIPT)
    if not all(isinstance(x,dict) for x in (action,base,receipt)):return None
    try:
        from hengce_unified_scan_display import build
        shown=build(now,action,base,receipt)
        require_q017_publication(shown,base,now,ROOT)
        return action
    except (OSError,ValueError,TypeError,KeyError,OverflowError):return None

def build_reporting(now):
    try:import hengce_total_scoreboard as scoreboard
    except Exception as exc:return {'status':'DATA_PENDING_REPORTING_MODULE','reason':f'{type(exc).__name__}:{exc}',**ZERO_AUTHORITY}
    paths={'contract':ROOT/'hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json','preserve':ROOT/'hengce/HENGCE_Q017_PRESERVATION_DECISION_20261026.json',
           'retire':ROOT/'hengce/HENGCE_MAINLINE_RETIREMENT_DECISION_20261026.json','qc':ROOT/'hengce/q017_canonical/latest.json',
           'e':ROOT/'hengce/e2_live/state_latest.json','v':ROOT/'hengce/v43_daily/latest.json','w':ROOT/'hengce/w1_nextday/latest.json',
           'review':ROOT/'hengce/q017_review_10d/review_latest.json','prices':ROOT/'hengce/q017_radar/data/twse_electronics_history_2026.csv'}
    qc,e,v,w=(load(paths[k]) for k in ('qc','e','v','w'))
    try:q=current_decision(now,ROOT)
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as exc:
        q={'schema_version':5,'module':'Q017_AUTHORITY_GUARD_FAIL_CLOSED','trade_date':now.date().isoformat(),
           'authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'top3':[],'market_state':'DATA_PENDING','reason':str(exc)}
    try:
        prices,pdate=scoreboard.latest_prices(paths['prices']);sb=scoreboard.build(q,e,v,w,prices,pdate)
    except Exception as exc:sb={'status':'FAIL_CLOSED','reason':f'{type(exc).__name__}:{exc}',**ZERO_AUTHORITY}
    lanes={'q017':_active_q017(q,qc),'e2_profit_max':_retired_lane('E2_PROFIT_MAX',e,'DELETED_OR_RETIRED_PER_USER'),
           'v43':_retired_lane('V43',v,'PRIOR_SIX_MONTH_RETIREMENT'),'x12':_retired_lane('X12',None,'PRIOR_SIX_MONTH_RETIREMENT'),
           'w1_nextday':_retired_lane('W1_WIDE_TAIL',w,'PRIOR_SIX_MONTH_RETIREMENT')}
    return {'schema_version':4,'status':'PASS_Q017_SOLE_ACTIVE',**ZERO_AUTHORITY,'active_strategy_count':1,'active_strategy':'Q017',
            'runtime_expected':'Q017_ONLY_HARD_LOCK_20261026_SCHEMA5','contract':{'formal_authority':False,'historical_metadata':load(paths['contract'])},
            'q017_preservation_decision':load(paths['preserve']),'superseded_q017_retirement_audit':load(paths['retire']),'lanes':lanes,
            'three_line_resonance':{'status':'RETIRED_NOT_APPLICABLE_SINGLE_ACTIVE_STRATEGY','trade_authority':0,'attention_score_contribution':0},
            'total_scoreboard':sb,'q017_10d_review':load(paths['review']) or {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'},
            'live_data_health':{'status':'OBSERVABILITY_ONLY_NOT_FORMAL_INPUT'},
            'position_and_action_state':{'strategy_action':'Q017_ONLY_FAIL_CLOSED_UNLESS_CURRENT_FORMAL_BINDING_PASS','user_actual_trades':_user_positions()},
            'guards':['Q017 is the sole active HENGCE strategy.','E2, X12, V43 and W1 remain retired/deleted.','Legacy HENGCE cannot supply candidates; it may only supply existing legal geometry/formal-trigger infrastructure for the Q017-selected ticker.','Attention score cannot upgrade formal action.','Missing/stale Q017 evidence fails closed.']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--now');ap.add_argument('--display-only',action='store_true');a=ap.parse_args();now=parse_now(a.now)
    attempts=[] if a.display_only else refresh(now)
    action=_current_q017_action(now)
    market_open=_trading_day(now)
    rows=action.get('rows',[]) if isinstance(action,dict) and isinstance(action.get('rows'),list) else []
    formal_entry=any(isinstance(r,dict) and r.get('FinalAction') in {'REVIEW_ENTRY','ENTER','BUY'} and not str(r.get('ExecutionEligibility','')).startswith('ABSTAIN') for r in rows)
    status='ACTIVE_Q017_FORMAL_ACTION_BOUND' if action else ('ACTIVE_Q017_MARKET_CLOSED' if market_open is False else 'ACTIVE_Q017_FAIL_CLOSED_NO_CURRENT_FORMAL_ACTION')
    out={'schema_version':2,**ZERO_AUTHORITY,'system':'HENGCE','module':'HENGCE_SCAN_ONCE_ROUTER','architecture':'SINGLE_HENGCE',
         'status':status,'binding_status':'PASS' if action else 'FAIL_CLOSED','authority':'Q017_ONLY_FORMAL_ACTION_WHEN_CURRENTLY_BOUND',
         'formal_hengce_stock_output_engine':'Q017',
         'can_create_new_entry':formal_entry,'rows':rows,'reason':None if action else ('TWSE_NOT_TRADING_DAY' if market_open is False else 'CURRENT_Q017_FORMAL_BINDING_UNAVAILABLE'),
         'scan_once_router':{'status':status,'command':'衡策掃一次','refresh_attempts':attempts,'retired_producers_invoked':False,'active_strategy_count':1,
                             'active_strategy':'Q017','q017_only_candidate_source':True,'single_hengce_output':True,'score_fusion':False,'reporting_sidecar_version':'Q017_SCHEMA5_ONLY'},
         'reporting':build_reporting(now)}
    print(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False));return 0

if __name__=='__main__':raise SystemExit(main())
