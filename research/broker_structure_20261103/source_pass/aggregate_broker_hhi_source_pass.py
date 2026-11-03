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
    shards = []
    parse_errors = []
    for p in files:
        try:
            shards.append(json.loads(Path(p).read_text(encoding='utf-8')))
        except Exception as exc:
            parse_errors.append(f'{Path(p).name}:{type(exc).__name__}:{exc}')

    receipt = {
        'schema_version': 1,
        'system': 'HENGCE',
        'artifact': 'BROKER_HHI_SOURCE_ONLY_PASS_RECEIPT',
        'authority': 'DERIVED_SOURCE_FEATURE_AND_LINEAGE_ONLY_NO_OUTCOME_NO_TRADING_AUTHORITY',
        'prereg_commit': PREREG_COMMIT,
        'source_revision_class': SOURCE_CLASS,
        'expected_signal_dates': EXPECTED_DATES,
        'expected_shards': EXPECTED_SHARDS,
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
            bad = [s for s in shards if s.get('status') != 'PASS_SHARD']
            if bad:
                rc = fail(receipt, 'ONE_OR_MORE_SOURCE_SHARDS_FAILED', [
                    {'shard': s.get('shard'), 'status': s.get('status'), 'errors': s.get('errors', [])[:5]}
                    for s in bad
                ])
            else:
                daily = []
                for s in shards:
                    daily.extend(s.get('daily', []))
                indices = [x.get('date_index') for x in daily]
                dates = [x.get('date') for x in daily]
                if len(daily) != EXPECTED_DATES:
                    rc = fail(receipt, f'DAILY_COUNT_MISMATCH:{len(daily)}')
                elif sorted(indices) != list(range(EXPECTED_DATES)) or len(set(dates)) != EXPECTED_DATES:
                    rc = fail(receipt, 'DATE_COVERAGE_NOT_EXACTLY_ONCE')
                else:
                    panel_rows = []
                    lineage_rows = []
                    validation_errors = []
                    for x in sorted(daily, key=lambda r: r['date_index']):
                        if x.get('status') != 'PASS_SOURCE_DATE':
                            validation_errors.append(f"{x.get('date')}:STATUS:{x.get('status')}")
                            continue
                        if x.get('observed_missing_among_mother_traded_symbols') != 0:
                            validation_errors.append(f"{x.get('date')}:MOTHER_MISSING")
                        h = x.get('hhi_by_stock', {})
                        if len(h) != EXPECTED_U100:
                            validation_errors.append(f"{x.get('date')}:HHI_COUNT:{len(h)}")
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

                    if validation_errors:
                        rc = fail(receipt, 'SOURCE_DAILY_VALIDATION_FAILED', validation_errors[:100])
                    elif len(panel_rows) != EXPECTED_DATES * EXPECTED_U100:
                        rc = fail(receipt, f'PANEL_ROW_COUNT_MISMATCH:{len(panel_rows)}')
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
                        receipt.update({
                            'status': 'PASS_SOURCE_ONLY_HHI_AND_LINEAGE',
                            'signal_date_count': EXPECTED_DATES,
                            'panel_row_count': len(panel_rows),
                            'lineage_row_count': len(lineage_rows),
                            'panel_sha256': sha256_file(panel_path),
                            'lineage_sha256': sha256_file(lineage_path),
                            'next_legal_step': 'JOIN_DERIVED_HHI_TO_FROZEN_UPSTREAM_AND_RUN_EXACT_FROZEN_H20_JUDGE_WITHOUT_RETUNING',
                        })

    receipt_path = Path(a.receipt_output)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
