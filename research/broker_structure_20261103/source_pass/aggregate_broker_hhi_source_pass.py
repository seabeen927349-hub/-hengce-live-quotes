#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
from pathlib import Path

EXPECTED_DATES = 1274
EXPECTED_U100 = 100
EXPECTED_SHARDS = 24
PREREG_COMMIT = '303b2e60501ecc93af6d3b67215f74d17795fa53'
SOURCE_CLASS = 'EVENT_DAY_FACT_RECONSTRUCTION'


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fail(receipt: dict, reason: str, errors: list | None = None) -> int:
    receipt['status'] = 'DATA_OR_LINEAGE_INVALID_STOP'
    receipt['reason'] = reason
    if errors:
        receipt['errors'] = errors
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--panel-output', required=True)
    ap.add_argument('--lineage-output', required=True)
    ap.add_argument('--receipt-output', required=True)
    a = ap.parse_args()

    files = sorted(glob.glob(str(Path(a.input_dir) / '*.json')))
    shards, parse_errors = [], []
    for p in files:
        try:
            shards.append(json.loads(Path(p).read_text(encoding='utf-8')))
        except Exception as exc:
            parse_errors.append(f'{Path(p).name}:{type(exc).__name__}:{exc}')

    receipt = {
        'schema_version': 2,
        'system': 'HENGCE',
        'artifact': 'BROKER_HHI_SOURCE_ONLY_PASS_RECEIPT',
        'authority': 'DERIVED_SOURCE_FEATURE_AND_LINEAGE_ONLY_NO_OUTCOME_NO_TRADING_AUTHORITY',
        'prereg_commit': PREREG_COMMIT,
        'source_revision_class': SOURCE_CLASS,
        'expected_signal_dates': EXPECTED_DATES,
        'expected_shards': EXPECTED_SHARDS,
        'missingness_semantics': 'STOCK_DATE_FAIL_CLOSED; PRIMARY_COMPLETE_CASE_GATE_95_OF_100_IS_APPLIED_LATER_WITH_FROZEN_OUTCOME_AND_CONTROLS',
        'raw_broker_rows_persisted': False,
        'forward_returns_loaded': False,
        'status': 'FAIL_CLOSED',
    }

    rc = 0
    if parse_errors:
        rc = fail(receipt, 'SHARD_JSON_PARSE_ERROR', parse_errors)
    elif len(shards) != EXPECTED_SHARDS:
        rc = fail(receipt, f'SHARD_ARTIFACT_COUNT_MISMATCH:{len(shards)}')
    else:
        shard_ids = [s.get('shard') for s in shards]
        if sorted(shard_ids) != list(range(EXPECTED_SHARDS)):
            rc = fail(receipt, f'SHARD_ID_SET_INVALID:{sorted(shard_ids)}')
        else:
            bad_shards = [s for s in shards if s.get('status') != 'PASS_SHARD']
            if bad_shards:
                rc = fail(receipt, 'ONE_OR_MORE_SOURCE_SHARDS_HAVE_UNREPAIRED_OBJECT_OR_LINEAGE_FAILURE', [
                    {'shard': s.get('shard'), 'status': s.get('status'), 'errors': s.get('errors', [])[:5]}
                    for s in bad_shards
                ])
            else:
                daily = [x for s in shards for x in s.get('daily', [])]
                indices = [x.get('date_index') for x in daily]
                dates = [x.get('date') for x in daily]
                if len(daily) != EXPECTED_DATES:
                    rc = fail(receipt, f'DAILY_AUDIT_COUNT_MISMATCH:{len(daily)}')
                elif sorted(indices) != list(range(EXPECTED_DATES)) or len(set(dates)) != EXPECTED_DATES:
                    rc = fail(receipt, 'DATE_AUDIT_COVERAGE_NOT_EXACTLY_ONCE')
                else:
                    panel_rows, lineage_rows, validation_errors = [], [], []
                    valid_counts, mother_missing_counts = [], []
                    for x in sorted(daily, key=lambda r: r['date_index']):
                        if x.get('status') != 'PASS_SOURCE_DATE_AUDIT':
                            validation_errors.append(f"{x.get('date')}:STATUS:{x.get('status')}")
                            continue
                        h = x.get('hhi_by_stock', {})
                        invalid = x.get('u100_missing_feature_by_stock', {})
                        if len(h) + len(invalid) != EXPECTED_U100 or set(h).intersection(invalid):
                            validation_errors.append(f"{x.get('date')}:U100_FEATURE_PARTITION_INVALID:{len(h)}+{len(invalid)}")
                            continue
                        if x.get('u100_valid_hhi_count') != len(h) or x.get('u100_missing_feature_count') != len(invalid):
                            validation_errors.append(f"{x.get('date')}:U100_FEATURE_COUNTS_INCONSISTENT")
                            continue
                        for ticker, v0 in sorted(h.items()):
                            try:
                                v = float(v0)
                            except Exception:
                                validation_errors.append(f"{x.get('date')}:{ticker}:HHI_NOT_NUMERIC")
                                continue
                            if not math.isfinite(v) or not (0.0 < v <= 1.0 + 1e-12):
                                validation_errors.append(f"{x.get('date')}:{ticker}:HHI_RANGE:{v}")
                            panel_rows.append((x['date'], str(ticker), v))
                        lineage_rows.append({k: v for k, v in x.items() if k != 'hhi_by_stock'})
                        valid_counts.append(len(h))
                        mother_missing_counts.append(int(x.get('observed_missing_among_mother_traded_symbols', -1)))

                    if validation_errors:
                        rc = fail(receipt, 'SOURCE_DAILY_AUDIT_VALIDATION_FAILED', validation_errors[:100])
                    else:
                        panel_path = Path(a.panel_output)
                        panel_path.parent.mkdir(parents=True, exist_ok=True)
                        with panel_path.open('w', encoding='utf-8', newline='') as f:
                            f.write('date,ticker,BROKER_GROSS_HHI_1D\n')
                            for d, t, v in panel_rows:
                                f.write(f'{d},{t},{v:.17g}\n')
                        lineage_path = Path(a.lineage_output)
                        lineage_path.parent.mkdir(parents=True, exist_ok=True)
                        with lineage_path.open('w', encoding='utf-8') as f:
                            for row in lineage_rows:
                                f.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')

                        lt95 = [x['date'] for x in daily if int(x.get('u100_valid_hhi_count', 0)) < 95]
                        receipt.update({
                            'status': 'PASS_SOURCE_AUDIT_DERIVED_HHI_READY',
                            'signal_date_audit_count': EXPECTED_DATES,
                            'derived_hhi_row_count': len(panel_rows),
                            'expected_max_hhi_row_count': EXPECTED_DATES * EXPECTED_U100,
                            'minimum_u100_valid_hhi_count_on_any_date': min(valid_counts),
                            'dates_with_any_u100_feature_missing': sum(c < EXPECTED_U100 for c in valid_counts),
                            'dates_with_u100_valid_hhi_below_95': len(lt95),
                            'sample_dates_u100_valid_hhi_below_95': lt95[:20],
                            'dates_with_any_mother_traded_source_missing': sum(c > 0 for c in mother_missing_counts),
                            'maximum_mother_traded_source_missing_count_on_any_date': max(mother_missing_counts),
                            'panel_sha256': sha256_file(panel_path),
                            'lineage_sha256': sha256_file(lineage_path),
                            'next_legal_step': 'JOIN_VALID_DERIVED_HHI_STOCK_DATES_TO_FROZEN_UPSTREAM; APPLY_FROZEN_COMPLETE_CASE_95_GATE; RUN_EXACT_FROZEN_H20_JUDGE_WITHOUT_RETUNING',
                        })

    receipt_path = Path(a.receipt_output)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
