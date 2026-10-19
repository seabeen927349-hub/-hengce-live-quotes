#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def replace_once(path,old,new):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    if new in s:
        print('ALREADY_PATCHED',path);return
    if old not in s: raise RuntimeError(f'PATCH_ANCHOR_MISSING:{path}')
    p.write_text(s.replace(old,new,1),encoding='utf-8')
    print('PATCHED',path)

core_old="""def premarket(today=None):
    today=today or now_tw().date();sox=refresh_sox(today);seed=ensure_tw_history();ed,es=latest_eod_status();sf=sox_features(today)
    eod_ok=bool(es and es.get('price_status')=='COMPLETE' and es.get('institutional_status')=='COMPLETE' and es.get('margin_status')=='COMPLETE')
    hist=load_tw_history();latest_hist=max(r['date'] for r in hist)
    status={'system':'HENGCE','module':'DAILY_DATA_GATE','generated_at_taipei':now_tw().isoformat(),'trade_date':today.isoformat(),'status':'PASS' if eod_ok else 'DATA_PENDING','required':{'sox':sox,'latest_eod_date':ed,'latest_eod_complete':eod_ok,'electronics_history':seed,'electronics_history_latest':latest_hist},'sox':sf,'policy':'NO_REQUIRED_DATA_NO_FORMAL_SIGNAL'}
    atomic_json(DATA_STATUS,status);return status
"""
core_new="""def premarket(today=None):
    today=today or now_tw().date();sox=refresh_sox(today);seed=ensure_tw_history();ed,es=latest_eod_status();sf=sox_features(today)
    eod_ok=bool(es and es.get('price_status')=='COMPLETE' and es.get('institutional_status')=='COMPLETE' and es.get('margin_status')=='COMPLETE')
    hist=load_tw_history();latest_hist=max(r['date'] for r in hist)
    try: hist_date=datetime.strptime(latest_hist,'%Y-%m-%d').date()
    except Exception: hist_date=None
    q017_ok=bool(hist_date and hist_date<today and sox.get('status')=='PASS')
    eod_iso=None
    if ed:
        try:eod_iso=datetime.strptime(ed,'%Y%m%d').date().isoformat()
        except Exception:eod_iso=str(ed)
    e2_archive_status='PASS' if (eod_ok and eod_iso==latest_hist) else ('ARCHIVE_GAP' if eod_ok else 'DATA_PENDING')
    status={'system':'HENGCE','module':'DAILY_DATA_GATE','generated_at_taipei':now_tw().isoformat(),'trade_date':today.isoformat(),'status':'PASS' if q017_ok else 'DATA_PENDING','lane_status':{'q017_inputs':'PASS' if q017_ok else 'DATA_PENDING','e2_eod_archive':e2_archive_status},'required':{'sox':sox,'latest_eod_date':ed,'latest_eod_complete':eod_ok,'electronics_history':seed,'electronics_history_latest':latest_hist},'sox':sf,'policy':'Q017_AND_E2_DATA_LANES_INDEPENDENT;E2_ARCHIVE_GAP_DOES_NOT_INVALIDATE_CAUSAL_Q017_INPUTS'}
    atomic_json(DATA_STATUS,status);return status
"""
replace_once(Path('scripts/hengce_daily_command_center_core_legacy.py'),core_old,core_new)

e2_old="""def morning(td):
 if not STATE.exists():raise RuntimeError('E2_STATE_MISSING')
 s=read_json(STATE);validate_locked_state(s);sd=datetime.strptime(s['signal_asof'],'%Y-%m-%d').date()
 if sd>=td:raise RuntimeError('E2_SIGNAL_ASOF_NOT_PRIOR_TO_TRADE_DATE')
 if (td-sd).days>MAX_STATE_STALE_DAYS:raise RuntimeError('E2_STATE_TOO_STALE')
 le=latest_complete_eod_date()
 if le and le>sd:raise RuntimeError(f'E2_STATE_STALE_VS_COMPLETE_EOD:STATE={sd}:EOD={le}')
 ps=s['position_state'];due=ps.get('pending') or []
 out={'schema_version':1,'system':'HENGCE','module':'E2_MORNING_EXECUTION_BRIDGE','trade_date':td.isoformat(),'generated_at_taipei':now_tw().isoformat(),'binding_status':'PASS','source_signal_asof':s['signal_asof'],'latest_complete_eod_date':le.isoformat() if le else None,'engine_status':s['strict']['engine_status'],'strict_cohort_count':s['strict']['cohort_count'],'new_signal_buy_count':s['strict']['buy_count'],'entry_due_count':len(due),'entry_due':due,'held_from_prior_close':ps.get('held') or [],'free_slots_before_today_entries':ps['free_slots_next_session'],'extension_shadow':s['extension_shadow'],'capital_authority':'STRICT_PENDING_ENTRY_ONLY','note':'E2 signals form after close; morning bridge executes only prior locked PENDING_ENTRY state. Shadow has zero capital authority.'};atomic_json(MORNING,out);return out
"""
e2_new="""def latest_market_session_hint(td):
 p=ROOT/'hengce'/'q017_radar'/'data_status.json'
 if not p.exists():return None
 try:o=read_json(p);x=((o.get('required') or {}).get('electronics_history_latest'))
 except Exception:return None
 try:d=datetime.strptime(str(x),'%Y-%m-%d').date()
 except Exception:return None
 return d if d<td else None
def morning(td):
 if not STATE.exists():raise RuntimeError('E2_STATE_MISSING')
 s=read_json(STATE);validate_locked_state(s);sd=datetime.strptime(s['signal_asof'],'%Y-%m-%d').date()
 if sd>=td:raise RuntimeError('E2_SIGNAL_ASOF_NOT_PRIOR_TO_TRADE_DATE')
 if (td-sd).days>MAX_STATE_STALE_DAYS:raise RuntimeError('E2_STATE_TOO_STALE')
 expected=latest_market_session_hint(td)
 if expected and sd!=expected:raise RuntimeError(f'E2_STATE_NOT_LATEST_MARKET_SESSION:STATE={sd}:EXPECTED={expected}')
 le=latest_complete_eod_date()
 if le and le>sd:raise RuntimeError(f'E2_STATE_STALE_VS_COMPLETE_EOD:STATE={sd}:EOD={le}')
 archive_gap=bool(le is None or le<sd)
 ps=s['position_state'];due=ps.get('pending') or []
 out={'schema_version':1,'system':'HENGCE','module':'E2_MORNING_EXECUTION_BRIDGE','trade_date':td.isoformat(),'generated_at_taipei':now_tw().isoformat(),'binding_status':'PASS','source_signal_asof':s['signal_asof'],'expected_prior_market_session':expected.isoformat() if expected else None,'latest_complete_eod_date':le.isoformat() if le else None,'local_eod_archive_gap':archive_gap,'engine_status':s['strict']['engine_status'],'strict_cohort_count':s['strict']['cohort_count'],'new_signal_buy_count':s['strict']['buy_count'],'entry_due_count':len(due),'entry_due':due,'held_from_prior_close':ps.get('held') or [],'free_slots_before_today_entries':ps['free_slots_next_session'],'extension_shadow':s['extension_shadow'],'capital_authority':'STRICT_PENDING_ENTRY_ONLY','note':'E2 state must match latest known prior market session. A lagging local EOD archive is repairable and has no authority over a separately hash-locked E2 state.'};atomic_json(MORNING,out);return out
"""
replace_once(Path('scripts/hengce_e2_live.py'),e2_old,e2_new)

wf=ROOT/'.github/workflows/hengce-daily-command-center.yml'
s=wf.read_text(encoding='utf-8')
if "'30 7 * * 1-5'" not in s:
    s=s.replace("    - cron: '0 7 * * 1-5'\n","    - cron: '0 7 * * 1-5'\n    - cron: '30 7 * * 1-5'\n    - cron: '0 8 * * 1-5'\n    - cron: '0 9 * * 1-5'\n",1)
    s=s.replace("              '0 7 * * 1-5') MODE='postclose' ;;","              '0 7 * * 1-5'|'30 7 * * 1-5'|'0 8 * * 1-5'|'0 9 * * 1-5') MODE='postclose' ;;",1)
    wf.write_text(s,encoding='utf-8')
    print('PATCHED workflow postclose retries')
else: print('ALREADY_PATCHED workflow')
