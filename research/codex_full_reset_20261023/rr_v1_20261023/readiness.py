"""Issue #32: offline data-route inspection only. Does not execute a model.

All repository observations bind to immutable commits. No downloader, feature
builder, simulator, fill inference, signal regeneration or evaluation entrypoint.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'results'
TASK = '868cf34fae807472506df5a4d008ab0d9af12536'
PREREG = '2da94b21025a71dc74de78a041e4e6280ce792bb'
MAIN = '0b7781bfacc261128fb3720dda8a81225c8996e7'
SEED = '09e59c5a0142a73be9d7ad0d50388444232d0a8e'
RESET = 'research/codex_full_reset_20261023/'
SEED_DIR = 'research/q017_sox_tw_electronics/archive_2026/'
HISTORY = 'hengce/q017_radar/data/twse_electronics_history_2026.csv'
CONFIG = {'family': 'RESIDUAL_REVERSAL', 'score': 'NEG_RESID1',
          'turnover_min': 50000000.0, 'top_n': 1, 'horizon': 20,
          'regime': 'PRIOR_SOX5_LE_-0.03'}
AUTH = {'research_only': True, 'signal_authority': False,
        'ranking_authority': False, 'capital_authority_twd': 0,
        'broker_order_execution': False, 'production_promotion': False,
        'merge_authorized': False, 'main_write_authorized': False}
NUMERIC = ('open', 'high', 'low', 'close', 'volume_shares', 'turnover_ntd')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def blob(ref, path):
    return git('show', ref + ':' + path)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode()


def rows(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError('MISSING_OR_DUPLICATE_HEADERS')
    result = list(reader)
    if not result:
        raise ValueError('EMPTY_SOURCE')
    if any(None in r or any(v is None for v in r.values()) for r in result):
        raise ValueError('RAGGED_SOURCE')
    return reader.fieldnames, result


def csv_summary(raw, date_column='date', ticker_column=None):
    fields, rr = rows(raw)
    if date_column not in fields or (ticker_column and ticker_column not in fields):
        raise ValueError('MISSING_KEY_COLUMN')
    ds = []; keys = set(); nonordinary = Counter(); missing = Counter()
    for r in rr:
        d = r[date_column]
        if date.fromisoformat(d).isoformat() != d:
            raise ValueError('NONCANONICAL_DATE')
        key = (d, r[ticker_column]) if ticker_column else d
        if key in keys:
            raise ValueError('DUPLICATE_SOURCE_KEY')
        keys.add(key); ds.append(d)
        if ticker_column and not re.fullmatch(r'[0-9]{4}', r[ticker_column]):
            nonordinary[r[ticker_column]] += 1
        for c in NUMERIC:
            if c in fields and r[c] in ('', '--', '---'):
                missing[c] += 1
    return {'rows': len(rr), 'date_min': min(ds), 'date_max': max(ds),
            'distinct_dates': len(set(ds)), 'columns': fields,
            'non_four_digit_ticker_rows': dict(sorted(nonordinary.items())),
            'explicit_missing_numeric_fields': dict(sorted(missing.items()))}


def source(ref, path, kind='json'):
    raw = blob(ref, path)
    record = {'commit': ref, 'path': path, 'sha256': sha(raw), 'bytes': len(raw)}
    if kind == 'csv':
        record['coverage'] = csv_summary(raw, ticker_column='ticker' if b'ticker' in raw.splitlines()[0] else None)
    if kind == 'csv.gz':
        record['coverage'] = csv_summary(gzip.decompress(raw), ticker_column='ticker')
    return record


def compare_seed(seed_raw, current_raw):
    """Compare evidence only. Never fill missing rows or create a new mother."""
    sf, sr = rows(seed_raw); cf, cr = rows(current_raw)
    if sf != cf:
        raise ValueError('SEED_SCHEMA_MISMATCH')
    csv_summary(seed_raw, ticker_column='ticker')
    csv_summary(current_raw, ticker_column='ticker')
    end = max(r['date'] for r in sr)
    a = {(r['date'], r['ticker']): r for r in sr}
    b = {(r['date'], r['ticker']): r for r in cr if r['date'] <= end}
    def normalized(r):
        return {k: v.replace(',', '') if k in NUMERIC else v for k, v in r.items()}
    mismatches = [list(k) for k in sorted(a.keys() & b.keys()) if normalized(a[k]) != normalized(b[k])]
    return {'seed_cutoff': end, 'seed_rows': len(a), 'current_prefix_rows': len(b),
            'missing_keys': [list(k) for k in sorted(a.keys() - b.keys())],
            'extra_keys': [list(k) for k in sorted(b.keys() - a.keys())],
            'different_values_after_thousands_separator_normalization': mismatches,
            'normalization_is_comparison_only': True}


def inventory():
    specs = [
        (TASK, RESET+'RR_V1_PREREG_20261023.json', 'json'),
        (TASK, RESET+'CODEX_RR_V1_TASK.md', 'text'),
        (TASK, RESET+'stage_c_rule_search.py', 'text'),
        (TASK, HISTORY, 'csv'),
        (TASK, 'hengce/q017_radar/data/sox_2026.csv', 'csv'),
        (TASK, 'hengce/q017_radar/data/sox_status.json', 'json'),
        (TASK, 'research/e2_profit_max/macro/sox_daily_202212_202610.csv', 'csv'),
        (TASK, RESET+'results/stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz', 'csv.gz'),
        (TASK, RESET+'results/stage_b/TWSE_MOTHER_RECEIPT.json', 'json'),
        (TASK, 'research/e2_profit_max/membership/membership_receipt.json', 'json'),
        (TASK, 'scripts/hengce_daily_command_center_core_legacy.py', 'text'),
        (TASK, 'eod/20261021/receipts/mother.json', 'json'),
        (TASK, 'eod/20261022/status.json', 'json'),
        (TASK, RESET+'data_foundation_v2_20261023/results/READINESS_V2.json', 'json'),
        (SEED, SEED_DIR+'acquisition_receipt_2026.json', 'json'),
        (SEED, SEED_DIR+'twse_electronics_membership_2026.csv', 'csv'),
        (SEED, SEED_DIR+'twse_electronics_daily_qa_2026.csv', 'text'),
        (SEED, 'research/q017_sox_tw_electronics/acquire_2026_sox_dxy_pit.py', 'text'),
        (MAIN, 'eod/20261022/status.json', 'json')]
    records = [source(*s) for s in specs]
    receipt = json.loads(blob(SEED, SEED_DIR+'acquisition_receipt_2026.json'))
    for key, filename in [('sha256', 'twse_electronics_membership_2026.csv'),
                          ('qa_sha256', 'twse_electronics_daily_qa_2026.csv')]:
        if sha(blob(SEED, SEED_DIR+filename)) != receipt['twse'][key]:
            raise ValueError('SEED_RECEIPT_HASH_MISMATCH')
    trees = {}
    for ref in (TASK, MAIN):
        raw = git('ls-tree', '-r', '--name-only', ref)
        paths = raw.decode().splitlines()
        trees[ref] = {'tree_listing_sha256': sha(raw),
                      'eod_dates': sorted({p.split('/')[1] for p in paths if p.startswith('eod/')}),
                      'named_canonical_mother_files': [p for p in paths if Path(p).name == 'HENGCE_2026_HIST_MOTHER.csv']}
    return {'authority': AUTH, 'sources': records, 'repository_trees': trees,
            'seed_receipt_hashes_verified': True,
            'seed_comparison': compare_seed(blob(SEED, SEED_DIR+'twse_electronics_membership_2026.csv'), blob(TASK, HISTORY)),
            'canonical_receipt': json.loads(blob(TASK, 'eod/20261021/receipts/mother.json')),
            'external_store_access': 'ChatGPT Library is not mounted; /workspace/library-files empty at inspection; no Library file-access tool available',
            'attachment_inspection': 'All three uploaded handoff ZIPs contain task/governance text only, no historical mother',
            'source_policy': 'Existing retained Git objects only; no market download; no new or parallel mother; no in-memory model dataset assembled',
            'pit_assessment': 'Historical branch receipt identifies TWSE type=13 for 190 dates; seed hashes verify. Not a complete independent 2026 daily raw-response/membership reconciliation. Do not claim that no 2026 PIT evidence exists.',
            'macro_assessment': 'Frozen Stage C reads ret1/ret5 from research SOX CSV ending 2026-10-16. Live SOX closes extend to 2026-10-21 but have no ret1/ret5 columns. No silent splice or feature rewrite performed.',
            'warmup_assessment': 'Existing 2023-2025 mother contains possible warmup. No approved/verified canonical cross-source date/ticker/identity bridge to 2026 was available; no concatenation performed.'}


BLOCKERS = [
    'CANONICAL_ACCUMULATED_MOTHER_REFERENCED_BUT_NOT_ACCESSIBLE',
    'CANONICAL_20261022_PROMOTION_NOT_COMPLETE',
    'FULL_2026_PIT_AND_WARMUP_LINEAGE_NOT_RECONCILED',
    'FROZEN_MACRO_INPUT_NOT_CURRENT_FOR_REQUESTED_END_DATE',
    'V2_ENTITLEMENT_IDENTITY_EXECUTION_EVIDENCE_NOT_PROVEN_FOR_2026',
]


def generate():
    prereg = json.loads(blob(TASK, RESET+'RR_V1_PREREG_20261023.json'))
    if prereg['frozen_config'] != CONFIG or prereg['authority'] != AUTH:
        raise ValueError('PREREGISTRATION_CONTRACT_MISMATCH')
    if blob(TASK, RESET+'RR_V1_PREREG_20261023.json') != blob(PREREG, RESET+'RR_V1_PREREG_20261023.json'):
        raise ValueError('PREREGISTRATION_CHANGED')
    lineage = inventory()
    readiness = {'status': 'BLOCKED_DATA_READINESS', 'authority': AUTH,
                 'requested_interval': ['2026-01-01', '2026-10-22'],
                 'block_reasons': BLOCKERS, 'new_model_evaluations': 0,
                 'prior_model_evaluations': 8529, 'total_model_evaluations': 8529,
                 'data_status_is_not_model_failure': True,
                 'next_action': 'STOP. Supply/reconcile the existing canonical mother and receipts, PIT/warmup and frozen macro lineage plus applicable V2 evidence, then separately review readiness. Do not substitute, tune or automatically spend the one-evaluation budget.'}
    result = {'status': readiness['status'], 'authority': AUTH, 'config': CONFIG,
              'new_model_evaluations': 0, 'prior_model_evaluations': 8529,
              'intended_baskets': None, 'complete_baskets': None, 'censored_baskets': None,
              'regime_occurrences': None, 'censor_reasons': None,
              'trade_concentration': None, 'ticker_concentration': None,
              'metric_status': 'NOT_EVALUATED_DATA_READINESS_BLOCKED',
              'cost_cases': [{'aggregate_roundtrip_cost': c, 'compounded_return': None,
                              'win_rate': None, 'max_drawdown': None,
                              'remove_best_trade_return': None}
                             for c in (.008, .012, .016)],
              'pristine_holdout': False, 'prospective_claim': False,
              'complete_case_is_not_executable_strategy': True}
    report = '''# RR V1 — BLOCKED_DATA_READINESS

Issue #32, one frozen configuration: RESIDUAL_REVERSAL|NEG_RESID1|TO50000000|N1|H20|PRIOR_SOX5_LE_-0.03.
**Zero new model evaluations. Prior/cumulative evaluations remain 8,529.**
This is a data-readiness result, not a failed or passed model validation.

## Existing data route inspected

- Task/preregistration pinned to 868cf34 / 2da94b2; main independently inspected at 0b7781b, never merged/rebased into this branch.
- Both trees retain seven EOD directories, 2026-10-14–22. Latest price is COMPLETE (1,088 rows); mother promotion is PENDING and downstream_ready=false. Margin PENDING alone is not asserted to be a price-model requirement.
- Canonical receipt for 2026-10-21 references ChatGPT Library:/HENGCE_CANONICAL/HENGCE_2026_HIST_MOTHER.csv, 207,218 rows, SHA256 60fb82570d48ef2620a8390d612457fc79e795b9e1fe485f61739103bfa8db47. These are receipt assertions, not locally verified mother bytes. The CSV is absent from both repository trees, mounted Library directory and uploaded handoffs. No direct Library-access connector is available. Receipt existence does not prove dataset availability or 10/22 completion.
- Existing Q017 electronics CSV: 88,442 rows / 194 dates, 2026-01-02–10-22. It is not empty or restricted to October. Its producer references an existing historical seed branch; that branch was fetched read-only and pinned to 09e59c5.
- Historical seed: 86,615 rows / 190 dates, 2026-01-02–10-16, official TWSE type=13 according to acquisition receipt. Seed and QA SHA256 checks PASS. Current overlapping CSV has 86,614 rows, one fewer key (2026-10-16 / 8112A, preferred share). The 457 text differences on 10/16 are thousands separators only; no different common-key values remain after comparison-only normalization. Do not silently replace the accumulated source with this seed.
- The seed admits 4–8 character symbols; frozen Stage-B mother explicitly retains four-digit symbols. This must be reconciled consistently, including market-median membership, before claiming identical frozen feature semantics. No symbols were filtered, repaired or ranked here.
- Existing Stage-B official PIT mother: 313,749 rows / 724 dates, 2023-01-03–2025-12-31. Potential warmup exists; it is not a 2026 source. No cross-source concatenation or second mother was created.
- Frozen research SOX input: 972 rows, 2022-12-01–2026-10-16, date/close/ret1/ret5. Live SOX input: 202 dates, 2026-01-02–10-21, date/close only. No silent splice, recomputed ret5 or reuse of the last old macro value for newer sessions. A general macro PASS receipt cannot override actual file coverage/schema.
- Full 2026 PIT/raw-response and warmup lineage, corporate-action entitlement/identity and execution evidence have not been established. Prior V2 evidence covers 2023–25 and remains unchanged; it cannot clear 2026 orders or manufacture fills.

## Requested metrics

Requested validation: 2026-01-01–10-22 with pre-2026 warmup. No features, rankings, signals, regimes, baskets, model returns or cost-stress returns were computed. Intended/complete/censored baskets, regime occurrences, censor reasons, compounded return, win rate, drawdown, remove-best-trade return and trade/ticker concentration are all **NOT_EVALUATED (null)**, not zero. Aggregate cost cases remain frozen at 0.8%, 1.2%, 1.6%; no diagnostic or cost case was counted as a trial. RR_V1_EVENTS.jsonl is intentionally empty, not evidence of zero trades.

All 2023–2026 historical material remains exposed. No pristine holdout or prospective/OOS performance claim is made. Complete-case returns, if later authorized and produced, cannot establish an executable whole-strategy return.

## Disposition and limits

Stop under the explicit data-route gate in CODEX_RR_V1_TASK.md. Provide/access the existing canonical mother with its matching source/schema/coverage receipt and reconcile PIT membership, pre-2026 warmup, current frozen macro inputs and applicable V2 evidence before revisiting the single evaluation. No alternate market download, new EOD tree, second mother, tuning, family substitution or historical signal regeneration occurred.

All outputs are research-only; signal/ranking authority=false; capital=0; broker=false; promotion/merge/main-write authorization=false. Production Q017/E2/M1, schedules and model computation are unchanged. Old outcomes and ledgers remain byte-exact. Offline audit reproduces these files from pinned Git objects, without running any model. CI/replay verification and immutable evidence commit are recorded in PR #30 after final-head completion.

MODEL CHANGES: NONE IMPLEMENTED

PR #30 must remain OPEN / DRAFT / NOT MERGED.
'''
    return {'RR_V1_READINESS.json': encoded(readiness),
            'RR_V1_DATA_LINEAGE.json': encoded(lineage),
            'RR_V1_EVENTS.jsonl': b'', 'RR_V1_RESULT.json': encoded(result),
            'RR_V1_REPORT.md': report.encode()}


def check_scope():
    allowed = (RESET+'rr_v1_20261023/', '.github/workflows/hengce-codex-full-reset-contracts.yml')
    changed = git('diff', '--name-only', TASK, '--').decode().splitlines()
    if any(not p.startswith(allowed) for p in changed):
        raise ValueError('OUT_OF_SCOPE_CHANGE')


def audit():
    check_scope()
    for name, raw in generate().items():
        if (OUT/name).read_bytes() != raw:
            raise ValueError('REPRODUCTION_MISMATCH:'+name)
    checkpoint = json.loads((OUT/'RR_V1_AUDIT.json').read_bytes())
    if checkpoint != audit_payload():
        raise ValueError('AUDIT_CHECKPOINT_MISMATCH')
    print('RR_V1_OFFLINE_AUDIT PASS; BLOCKED_DATA_READINESS; model evaluations=0')


def audit_payload():
    files = {name: sha(raw) for name, raw in generate().items()}
    for p in (HERE/'readiness.py', HERE/'test_readiness.py'):
        files['../'+p.name] = sha(p.read_bytes())
    return {'status': 'PASS_BLOCKED_READINESS_EVIDENCE_ONLY', 'authority': AUTH,
            'task_commit': TASK, 'preregistration_commit': PREREG,
            'preregistration_sha256': sha(blob(PREREG, RESET+'RR_V1_PREREG_20261023.json')),
            'config_sha256': sha(encoded(CONFIG)), 'frozen_implementation_sha256': sha(blob(TASK, RESET+'stage_c_rule_search.py')),
            'configurations_evaluated': 0, 'new_model_evaluations': 0,
            'parameter_tuning': 0, 'family_search': 0, 'market_downloads': 0,
            'second_mother_created': False, 'events_file_is_empty': True,
            'prior_model_evaluations': 8529, 'total_model_evaluations': 8529,
            'files_sha256': files,
            'external_anchor': 'Pushed Git commit containing these evidence bytes; compare checkpoint against commit history, not a self-contained hash alone.',
            'scope_audit': 'git diff against task commit permits only rr_v1_20261023/** and the existing offline-contract CI workflow; all prior evidence and production bytes unchanged',
            'main_operations': 'Fetch/read only. This tool contains no commit, push, merge, rebase, feature or simulation operation.'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', action='store_true')
    args = parser.parse_args()
    if args.audit:
        audit()
    else:
        check_scope()
        for name, raw in generate().items():
            path = OUT/name
            if path.exists():
                raise FileExistsError('EVIDENCE_ALREADY_EXISTS:'+name)
            path.write_bytes(raw)
        (OUT/'RR_V1_AUDIT.json').write_bytes(encoded(audit_payload()))
        audit()
