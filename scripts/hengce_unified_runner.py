#!/usr/bin/env python3
"""Local single-HENGCE transaction. Receipt is the commit marker, never a fallback.

This publishes local UI artifacts only. Repository writers continue using the
existing exact-lease hengce_publish.py; observation capture lanes are untouched.
"""
from __future__ import annotations
import fcntl
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo
from hengce_unified_contracts import atomic, digest, strict_loads, session_metadata, ZERO_AUTHORITY

NAMES = {'base': 'HENGCE_UNIFIED_CANDIDATE_BASE.json',
         'action': 'HENGCE_INTRADAY_ACTION_BOARD.json',
         'receipt': 'HENGCE_INTRADAY_BINDING_RECEIPT.json'}
TZ = ZoneInfo('Asia/Taipei')


def locations():
    root = Path(os.environ.get('HENGCE_ROOT', Path(__file__).resolve().parents[1])).resolve()
    out = Path(os.environ.get('HENGCE_INTRADAY_OUT_DIR', root / 'work_output/intraday_action_board')).resolve()
    return root, out


def select(root, variable, relative, reason, optional=False):
    explicit = os.environ.get(variable)
    if explicit is not None:
        if not explicit or not Path(explicit).is_file():
            raise ValueError(variable + '_OVERRIDE_NOT_FOUND')
        return Path(explicit)
    paths = [root / p for p in relative if (root / p).is_file()]
    if len(paths) > 1:
        raise ValueError('AMBIGUOUS_' + variable)
    if not paths and not optional:
        raise ValueError(reason)
    return paths[0] if paths else None


def read(path):
    data = path.read_bytes()
    return strict_loads(data), hashlib.sha256(data).hexdigest()


def run(now=None):
    now = now or datetime.now(TZ)
    now = now.astimezone(TZ)
    root, outdir = locations()
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {k: outdir / v for k, v in NAMES.items()}
    # Lock only local publication/computation, never the independent Q017 capture.
    with (outdir / '.publication.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('FAIL_CLOSED: PUBLICATION_BUSY', file=sys.stderr)
            return 2
        envelope = {'schema_version': 3, 'system': 'HENGCE', **ZERO_AUTHORITY,
                    'generated_at': now.isoformat(), 'trade_date': now.date().isoformat(),
                    'ActionLayer': 'INTRADAY_ACTION_BOARD', 'score_fusion': False}
        atomic(paths['receipt'], {**envelope, 'binding_status': 'RUNNING', 'rows': []})
        try:
            import hengce_unified_candidate_adapter as adapter
            import hengce_unified_action_board as board
            for variable, module in [('HENGCE_UNIFIED_ADAPTER', adapter), ('HENGCE_INTRADAY_BRIDGE', board)]:
                if variable in os.environ and Path(os.environ[variable]).resolve() != Path(module.__file__).resolve():
                    raise ValueError('UNSUPPORTED_RUNTIME_OVERRIDE:' + variable)
            formal = select(root, 'HENGCE_FORMAL_BASE_JSON', [
                'work_output/formal/production/v2_scan.json', 'work_output/formal/production/v3_scan.json',
                'work_output/formal/v2_scan.json', 'work_output/formal/v3_scan.json'], 'FORMAL_BASE_NOT_FOUND')
            legacy, legacy_sha = read(formal)
            if not isinstance(legacy, dict) or legacy.get('formal_scan_allowed') is not True:
                raise ValueError('FORMAL_BASE_DISALLOWED')
            session_metadata(legacy, now)
            if not legacy.get('run_id'):
                raise ValueError('FORMAL_RUN_ID_MISSING')
            ctxpath = select(root, 'HENGCE_MARKET_CONTEXT_JSON',
                             ['work_output/context/HENGCE_MARKET_CONTEXT.json'], 'MARKET_CONTEXT_NOT_FOUND')
            context, context_sha = read(ctxpath)
            session_metadata(context, now)
            qpath = select(root, 'HENGCE_Q017_CANONICAL_JSON', ['hengce/q017_canonical/latest.json'], '', optional=True)
            q017, qsha = None, None
            if qpath:
                qsha = hashlib.sha256(qpath.read_bytes()).hexdigest()
                try:
                    q017, qsha = read(qpath)
                    session_metadata(q017, now)
                    if q017.get('schema_version') != 1 or q017.get('module') != 'HENGCE_CANONICAL_Q017_CANDIDATES':
                        raise ValueError('UNSUPPORTED_Q017_SCHEMA_OR_PRODUCER')
                    producer = q017.get('producer')
                    if not isinstance(producer, dict) or not producer.get('code_commit') or not producer.get('input_hashes'):
                        raise ValueError('Q017_LINEAGE_UNAVAILABLE')
                except (OSError, ValueError, TypeError) as exc:
                    q017 = {'input_error': str(exc)}  # isolate unavailable optional source; never translate v5
            if os.environ.get('HENGCE_LIVE_JSON') is not None:
                livepath = select(root, 'HENGCE_LIVE_JSON', [], 'LIVE_OVERRIDE_NOT_FOUND')
                live, live_sha = read(livepath)
            else:
                url = os.environ.get('HENGCE_LIVE_RAW_URL',
                    'https://raw.githubusercontent.com/seabeen927349-hub/-hengce-live-quotes/main/live/active.json')
                if not url.startswith('https://'):
                    raise ValueError('LIVE_TRANSPORT_REQUIRES_HTTPS')
                with urlopen(url, timeout=20) as response:
                    raw = response.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise ValueError('LIVE_TOO_LARGE')
                live, live_sha = strict_loads(raw), hashlib.sha256(raw).hexdigest()
            if os.environ.get('HENGCE_LIVE_JSON') is None:
                livepath = None
            max_age = int(os.environ.get('HENGCE_LIVE_MAX_AGE_SECONDS', '480'))
            if not 0 < max_age <= 480:
                raise ValueError('LIVE_MAX_AGE_CANNOT_WEAKEN_CONTRACT')
            unified = adapter.build(legacy, q017)
            action = board.build(unified, live, context, trade_date=now.date().isoformat(),
                                 max_age_seconds=max_age, now=now)
            if action['binding_status'] != 'PASS':
                raise ValueError('INTRADAY_BRIDGE_FAIL_CLOSED:' + action['binding_reason'])
            source_sha = {'legacy_base': legacy_sha, 'q017_source': qsha,
                          'context': context_sha, 'live': live_sha}
            transaction = digest({'sources': source_sha, 'time': now.isoformat()})
            unified.update(transaction_id=transaction)
            action.update(transaction_id=transaction, generated_at=now.isoformat(),
                          trade_date=now.date().isoformat(), base_hash=digest(unified))
            receipt = {**envelope, 'binding_status': 'PASS', 'transaction_id': transaction,
                       'source_paths': {'legacy_base': str(formal), 'q017_source': str(qpath) if qpath else None, 'context': str(ctxpath)},
                       'source_sha256': source_sha, 'base_hash': digest(unified), 'action_hash': digest(action),
                       'q017_contract_status': unified['q017_contract_status'],
                       'source_provenance_counts': unified['source_provenance_counts']}
            # Snapshot hashes bind what was actually computed. Revalidate local
            # authoritative dependencies immediately before publication as well.
            for source_path, expected in [(formal, legacy_sha), (ctxpath, context_sha),
                                          (qpath, qsha), (livepath, live_sha)]:
                if source_path and hashlib.sha256(source_path.read_bytes()).hexdigest() != expected:
                    raise ValueError('AUTHORITATIVE_SOURCE_CHANGED_DURING_COMPUTATION')
            # No PASS receipt until every member has been atomically replaced.
            atomic(outdir / 'live_active.json', live)
            atomic(paths['base'], unified)
            atomic(paths['action'], action)
            atomic(paths['receipt'], receipt)
            print('HENGCE_UNIFIED_INTRADAY_ACTION_BOARD_PASS', file=sys.stderr)
            return 0
        except Exception as exc:
            reason = str(exc) or type(exc).__name__
            failure = {**envelope, 'binding_status': 'FAIL_CLOSED', 'reason': reason, 'rows': []}
            # Invalidate receipt first: a crash during cleanup cannot expose old PASS.
            atomic(paths['receipt'], failure)
            atomic(paths['action'], {**failure, 'module': 'HENGCE_UNIFIED_INTRADAY_ACTION_BOARD'})
            atomic(paths['base'], {**failure, 'module': 'HENGCE_UNIFIED_CANDIDATE_ADAPTER'})
            print('FAIL_CLOSED: ' + reason, file=sys.stderr)
            return 2


if __name__ == '__main__':
    raise SystemExit(run())
