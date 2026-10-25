#!/usr/bin/env python3
"""Authoritative router for `衡策掃一次`.

Backward compatibility: top-level JSON remains the single unified HENGCE formal
action display. v2.4 keeps the reporting-only sidecar but retires X12/V43/W1
from active research scoring after the 2026-10-26 six-month practicality review.
The sidecar never upgrades formal action/order/capital authority.
"""
from __future__ import annotations
import argparse,json,subprocess,sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from hengce_unified_runner import locations
from hengce_unified_contracts import ZERO_AUTHORITY, strict_loads

TZ=ZoneInfo('Asia/Taipei'); ROOT,OUTPUT_DIR=locations(); SCRIPTS=Path(__file__).resolve().parent
RUNNER=ROOT/'RUN_INTRADAY_ACTION_BOARD.sh'
if not RUNNER.is_file(): RUNNER=SCRIPTS/'RUN_INTRADAY_ACTION_BOARD.sh'
ACTION=OUTPUT_DIR/'HENGCE_INTRADAY_ACTION_BOARD.json'; BASE=OUTPUT_DIR/'HENGCE_UNIFIED_CANDIDATE_BASE.json'

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

def refresh(now):
    """Never invoke producer recovery or legacy decision writers from a scan."""
    return []

def _lane_summary_q(q):
    if not isinstance(q,dict):return {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'}
    return {'status':'PASS' if q.get('binding_status')=='PASS' else 'FAIL_CLOSED','trade_date':q.get('trade_date'),'binding_status':q.get('binding_status'),'market_state':q.get('market_state'),'top3':q.get('top3') or [],'authority':q.get('authority'),'role':'SCHEMA5_0901_LEGACY_REQUIRED_REPORTING_EVIDENCE_NOT_SECOND_FORMAL_ACTION_BOARD'}
def _lane_summary_e(e):
    if not isinstance(e,dict):return {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'}
    return {'status':'PASS' if e.get('binding_status')=='PASS' else 'FAIL_CLOSED','signal_asof':e.get('signal_asof'),'engine_status':e.get('engine_status'),'action':e.get('action'),'top1':e.get('top1'),'position_state':e.get('position_state'),'rules':e.get('rules'),'authority':e.get('authority')}
def _lane_summary_v(v):
    if not isinstance(v,dict):return {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'}
    s=v.get('screen') or {}; sch=v.get('schedule') or {}
    return {'status':v.get('status'),'signal_date':s.get('signal_date'),'top3':s.get('top3') or [],'regime':s.get('regime'),'frozen_schedule_state':sch.get('state'),'today_is_frozen_schedule_signal':sch.get('today_is_frozen_schedule_signal'),'validation':v.get('validation'),'authority':v.get('authority')}
def _lane_summary_w(w):
    if not isinstance(w,dict):return {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'}
    return {'status':w.get('status'),'signal_date':w.get('signal_date'),'top20':w.get('top20') or [],'timing':w.get('timing'),'economic_gate_40bp':w.get('economic_gate_40bp'),'full_rank_available':w.get('full_rank_available'),'authority':w.get('authority'),'provenance':w.get('provenance')}

def _user_positions():
    out=[]; d=ROOT/'hengce/user_actual_trades'
    if d.is_dir():
        for p in sorted(d.glob('*.json'))[-20:]:
            x=load(p)
            if isinstance(x,dict):out.append({'file':p.name,'data':x})
    return out

def build_reporting(now):
    """Best-effort reporting sidecar; retired research never alters formal rows."""
    try:
        import hengce_total_scoreboard as scoreboard
        import hengce_three_line_resonance as resonance
    except Exception as exc:
        return {'status':'DATA_PENDING_REPORTING_MODULES','reason':f'{type(exc).__name__}:{exc}',**ZERO_AUTHORITY}
    paths={
      'contract':ROOT/'hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json','q':ROOT/'hengce/q017_radar/latest.json','e':ROOT/'hengce/e2_live/state_latest.json',
      'v':ROOT/'hengce/v43_daily/latest.json','w':ROOT/'hengce/w1_nextday/latest.json','review':ROOT/'hengce/q017_review_10d/review_latest.json',
      'health':ROOT/'hengce/health/latest.json','prices':ROOT/'hengce/q017_radar/data/twse_electronics_history_2026.csv'}
    q,e,v,w=(load(paths[k]) for k in ('q','e','v','w')); contract=load(paths['contract'])
    try:
        prices,pdate=scoreboard.latest_prices(paths['prices']); sb=scoreboard.build(q,e,v,w,prices,pdate) if all(isinstance(x,dict) for x in (q,e,v,w)) else {'status':'DATA_PENDING_REQUIRED_LANE'}
    except Exception as exc: sb={'status':'FAIL_CLOSED','reason':f'{type(exc).__name__}:{exc}'}
    res={'status':'RETIRED_RESEARCH_COMBINATION','reason':'V43_AND_W1_RETIRED_FROM_ACTIVE_RESEARCH_FRONTIER_20261026',**ZERO_AUTHORITY}
    v_last=_lane_summary_v(v); w_last=_lane_summary_w(w)
    lanes={'q017_schema5':_lane_summary_q(q),'e2_profit_max':_lane_summary_e(e),
           'v43':{'status':'RETIRED_FROM_ACTIVE_RESEARCH_FRONTIER','attention_score_contribution':0,'trade_authority':0,'historical_last_artifact':v_last},
           'x12_frontier':{'status':'RETIRED_FROM_ACTIVE_RESEARCH_FRONTIER','attention_score_contribution':0,'trade_authority':0,'reason':'ONLY_3_EXECUTED_OPERATIONS_IN_6_MONTHS_UNDER_USER_PRACTICALITY_REQUIREMENT'},
           'w1_nextday':{'status':'RETIRED_FROM_ACTIVE_RESEARCH_FRONTIER','attention_score_contribution':0,'trade_authority':0,'historical_last_artifact':w_last},
           'q1':{'status':'DATA_PENDING_NO_VERIFIABLE_CURRENT_ARTIFACT','role':'UNVALIDATED_NEXTDAY_CHALLENGER','action':'DO_NOT_GUESS_OR_RERUN_ELIMINATED_MODELS'}}
    essential=all(lanes[k].get('status')!='DATA_PENDING_NO_CURRENT_ARTIFACT' for k in ('q017_schema5','e2_profit_max')) and sb.get('module')=='HENGCE_TOTAL_SCOREBOARD'
    return {'schema_version':2,'status':'PASS_REPORTING' if essential else 'PARTIAL_REPORTING',**ZERO_AUTHORITY,
            'contract':contract,'runtime_expected':'HENGCE_SCAN_ONCE_CONTRACT_v2_4_20261026','lanes':lanes,'three_line_resonance':res,'total_scoreboard':sb,
            'q017_10d_review':load(paths['review']) or {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'},'live_data_health':load(paths['health']) or {'status':'DATA_PENDING_NO_CURRENT_ARTIFACT'},
            'position_and_action_state':{'e2':(e or {}).get('position_state') if isinstance(e,dict) else None,'user_actual_trades':_user_positions()},
            'guards':['Reporting sidecar has zero formal action/order/capital authority.','Schema-v5 Q017 remains separately visible for old-contract compliance but is not a second formal action board.','X12, V43 and W1 are retired from active research and contribute zero attention/trade authority.','Retired research may be shown only as historical audit evidence.','Attention score cannot upgrade formal action.']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--now');ap.add_argument('--display-only',action='store_true');a=ap.parse_args();now=parse_now(a.now)
    attempts=[] if a.display_only else refresh(now)
    if not a.display_only: attempts.append(run_step('unified_hengce_action_board',['bash',str(RUNNER)],timeout=240))
    cmd=[sys.executable,str(SCRIPTS/'hengce_unified_scan_display.py'),'--now',now.isoformat(),'--no-write']
    if ACTION.exists():cmd+=['--action',str(ACTION)]
    if BASE.exists():cmd+=['--base',str(BASE)]
    try:
        p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=30);display=strict_loads(p.stdout) if p.stdout.strip() else {}
        if p.returncode!=0 and isinstance(display,dict) and display.get('binding_status')=='PASS':display={}
    except Exception:display={}
    if any(not x.get('ok',False) for x in attempts):display={}
    if not isinstance(display,dict) or display.get('system')!='HENGCE':
        display={'schema_version':1,**ZERO_AUTHORITY,'system':'HENGCE','module':'HENGCE_SCAN_ONCE_ROUTER','architecture':'SINGLE_HENGCE','status':'DATA_PENDING','binding_status':'FAIL_CLOSED','authority':'NO_FORMAL_HENGCE_OUTPUT','rows':[],'reason':'UNIFIED_SCAN_DISPLAY_FAILED'}
    display['scan_once_router']={'status':'PASS' if display.get('binding_status')=='PASS' else 'FAIL_CLOSED','command':'衡策掃一次','refresh_attempts':attempts,'single_hengce_output':True,'q017_separate_ranking_displayed':False,'e2_separate_engine_displayed':False,'legacy_v3_separate_ranking_displayed':False,'score_fusion':False,'reporting_sidecar_version':'v2.4'}
    display['reporting']=build_reporting(now)
    print(json.dumps(display,ensure_ascii=False,indent=2,allow_nan=False))
    return 0 if display.get('binding_status')=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
