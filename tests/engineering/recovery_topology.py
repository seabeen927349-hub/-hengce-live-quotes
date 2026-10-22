"""Read-only operational recovery inventory from Issue #20's exact base."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = '6bb5cb46a8477f2d7edf0310980791c2fb140415'
OUT = ROOT / 'docs/engineering/recovery-topology.json'
ROWS = [
 ('q017-primary','hengce-q017-primary-observer.yml', ['hengce_q017_observation_lock_v5.py','hengce_q017_observer_supervisor_v2.py'],
  'observations, observation_latest, history, attempts, supervisor; then decision, decision_latest, latest, ledger, display',
  '09:01:00–09:01:59.999999 capture only; persisted evidence may be computed later on current date',
  'validate_observation / validate_decision / authority guard', 'canonical=observation_latest, capture history; decision=decision_latest, hash-bound latest, decision history and exactly one ledger event',
  'write_once hash conflict STOP; canonical may survive missing later projections; independent lane', 'self-test default; explicit observe; no historical date input'),
 ('q017-backup','hengce-q017-backup-observer.yml',['hengce_q017_backup_observer_v5.py','hengce_q017_observation_lock_v5.py'],
  'backup_observations, backup_latest, backup_history, backup_status, attempts, supervisor', 'same strict independent 09:01 window',
  'validate_observation', 'backup canonical=backup_latest, backup history and status binding', 'write_once; separate namespace, no direct decision authority', 'self-test default; explicit observe'),
 ('q017-recovery','hengce-q017-recovery.yml',['hengce_q017_recovery_compute_v5.py','hengce_q017_observation_lock_v5.py'],
  'canonical observation only if absent; observation_latest, decision, decision_latest, latest, history, signal_ledger, recovery_receipt',
  'current date; existing valid immutable 09:01 evidence only, never late capture', 'existing_decision / validate_decision / promote_if_needed / authority guard',
  'canonical-first; never blend; complete observation/decision projections and evidence before publication', 'valid decision wins without recompute, but early return does not prove ledger/history closure; mutable daily receipt overwrites', 'optional trade_date currently permits historical dates; new guard must BLOCK'),
 ('daily','hengce-daily-command-center.yml',['hengce_daily_command_center.py','hengce_eod_incremental_ingest.py','hengce_e2_live.py','hengce_q017_10d_review.py','hengce_q017_10d_review_extension.py'],
  'q017_radar/**, q017_review_10d/**, e2_live/**, eod/**; two publication exits',
  'current operational date; mode-specific premarket/morning/closed-observation/monitor/postclose', 'public router / mode resolver / original-vessel readiness / authority guard',
  'mode-specific full closure; continue-on-error/always paths cannot make partial outputs complete', 'per-file atomic writes, date-dedup review; not a multi-file transaction', 'self-test default; mode/date inputs; historical date currently syntactically accepted'),
 ('e2-morning','hengce-e2-morning-backup.yml',['hengce_e2_live.py','hengce_dual_engine_display.py'],
  'e2_live/**, dual_engine/**', 'current date morning/current-day late recovery; generation remains late when late',
  'freshness/module/zero-capital/broker checks, no-fill/morning regressions', 'state/morning position and source-date binding; display source lineage',
  'date/status skip; state can be written before morning/display, generated timestamps differ on retry', 'manual current-day route, no date input'),
 ('e2-postclose','hengce-e2-profit-max-live.yml',['hengce_e2_live.py','hengce_dual_engine_display.py'],
  'e2_live/**, dual_engine/**, current causal history/macro data', 'current date postclose',
  'frozen E2/no-fill and display checks', 'state=current dated postclose history; display same state/position/source',
  'position/override consulted each run; E2 history mutable per existing contract, not write-once', 'optional trade_date currently unbounded; historical requests must BLOCK'),
 ('macro','hengce-q017-macro-cache.yml',['hengce_q017_macro_cache_v1.py'],
  'sox/dxy CSV/status, macro_cache dated/latest/history', 'current date premarket refresh; completed macro sessions strictly before trade date',
  'validate_cache(verify_files=True)', 'dated=latest/history with cache hash and exact CSV hashes', 'mutable refresh, per-file atomic, no atomic bundle guarantee', 'self-test default; refresh/validate explicit'),
 ('display','hengce-dual-engine-display-refresh.yml',['hengce_dual_engine_display.py'],
  'dual_engine/latest.json', 'current observation, no source-time laundering', 'display hard-lock test and contract checks',
  'display source dates/status/position agree; source canonical state valid or explicitly pending', 'regeneration overwrites latest with new timestamp; workflow_run includes failed completions', 'manual refresh, workflow_run or selected push'),
 ('eod','hengce-daily-command-center.yml',['hengce_eod_incremental_ingest.py'],
  'eod/current-date leg shards, per-leg receipts, status; external existing mother receipt consumed', 'current date postclose, legitimate PENDING permitted',
  '_read / _write / _mother_receipt / ingest', 'expected shard file set/count/hash/date/keys + receipt; mother promoted-leg bindings; downstream cannot infer readiness from shards alone',
  '_read reuses complete-looking CSV without requiring receipt; interrupted multi-shard writes can pass minimum rows; mother authority remains existing receipt contract', 'daily current route; dated one-off ingest utilities remain inventory-only'),
 ('review','hengce-daily-command-center.yml',['hengce_q017_10d_review.py','hengce_q017_10d_review_extension.py'],
  'review ledger/latest/daily, hypothetical ledger and diagnostics (separate zero-capital lane)', 'current operational review only; no historical signal/seed regeneration',
  'load_ledger / immutable cohort fields / append_session / extension load_hledger', 'ledger hash, daily/latest report binding, unique session dates and immutable cohort identity; reject torn CSV/history',
  'session date deduplicated; per-file JSON/markdown writes; new/changed historical cohort creation is not authorized recovery', 'daily postclose consumer; no new standalone recovery route'),
 ('health','hengce-system-health.yml',['hengce_system_health.py','hengce_health_collect_runs.py'],
  'observability output only; never producer outputs', 'weekday milestones; manual self-test/current-health',
  'strict health policy and four-axis evaluator', 'zero-authority diagnostics, no recovery dispatch', 'health-only exact lease; stale producer inputs reject health snapshot', 'self-test default; current-health restricted main'),
]


def show(path):
    return subprocess.check_output(['git','-C',str(ROOT),'show',BASE+':'+path])


def build():
    publisher = show('scripts/hengce_publish.py')
    inventory = json.loads(show('docs/engineering/writer-topology.json'))
    lanes = []
    for lane, workflow, modules, writes, window, validators, closure, retry, manual in ROWS:
        path = '.github/workflows/'+workflow
        raw = show(path); w = yaml.load(raw, Loader=yaml.BaseLoader)
        publications = []
        for job, spec in w['jobs'].items():
            for step in spec['steps']:
                run = step.get('run','')
                if 'hengce_publish.py' in run:
                    profile = re.search(r'--profile ([\w-]+)',run).group(1)
                    publications.append(dict(job=job,step=step.get('name'),profile=profile,
                        staging=[s.strip() for s in run.splitlines() if 'git add' in s]))
        old = [p for writer in inventory['writers'] if writer['workflow']==path for p in writer['publications']]
        lanes.append(dict(lane=lane,workflow=path,workflow_sha256=hashlib.sha256(raw).hexdigest(),
            source_sha256={'scripts/'+m:hashlib.sha256(show('scripts/'+m)).hexdigest() for m in modules},
            schedules_utc=w['on'].get('schedule',[]),triggers=w['on'],write_set=writes,
            immutable_subset=inventory['immutable_prefixes'],
            authoritative_read_dependencies=[p['authoritative_read_dependency_set'] for p in old] or 'health-only: all producer inputs; own observability output excluded',
            legal_date_window=window,existing_validators=validators,required_closure=closure,
            retry_idempotence=retry,manual_semantics=manual,publication_exits=publications))
    return dict(source_commit=BASE,scope='OPERATIONAL_SOURCE_INVENTORY_ONLY',
        signal_authority=False,ranking_authority=False,capital_authority_twd=0,broker_order_execution=False,
        publisher_sha256=hashlib.sha256(publisher).hexdigest(),lanes=lanes,
        excluded='Historical/research retry utilities are inventory-only; no dispatch, optimizer, backtest, holdout or historical signal regeneration.')


if __name__=='__main__':
    OUT.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
    print('Recorded exact-base operational inventory:',OUT)
