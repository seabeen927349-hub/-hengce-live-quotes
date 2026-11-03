#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DATASET = 'TaiwanStockTradingDailyReportSecIdAgg'
EXPECTED_COLS = ['date','stock_id','securities_trader_id','buy_volume','sell_volume','buy_price','sell_price']
SOURCE_CLASS = 'EVENT_DAY_FACT_RECONSTRUCTION'
SOURCE_PLAN = 'SponsorPro'
MOTHER_SHA256 = '2879ebb756c524dbefa4c47258d58fd6fa138aefcced3c7abb3d46634070651b'
PREREG_COMMIT = '303b2e60501ecc93af6d3b67215f74d17795fa53'
PIT_CONTRACT_BLOB = '144da48d29ad6db18d6f8fcec6aac9e26c0e4f7d'
EXPECTED_DATES = 1274
EXPECTED_U100 = 100


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _canonical_digest_scalar(v):
    if v is None:
        return None
    if isinstance(v, np.generic):
        return _canonical_digest_scalar(v.item())
    if isinstance(v, float):
        if math.isnan(v):
            return {'__nonfinite__': 'NaN'}
        if math.isinf(v):
            return {'__nonfinite__': '+Inf' if v > 0 else '-Inf'}
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, bytes):
        return {'__bytes_hex__': v.hex()}
    return v


def logical_content_sha256(table) -> str:
    selected = table.select(EXPECTED_COLS)
    sorted_table = selected.sort_by([(c, 'ascending') for c in EXPECTED_COLS])
    h = hashlib.sha256()
    h.update(('HENGCE_LOGICAL_ROW_HASH_V2_NONFINITE_CANONICAL\n' + '\x1f'.join(EXPECTED_COLS) + '\n').encode())
    for batch in sorted_table.to_batches(max_chunksize=65536):
        pycols = [batch.column(i).to_pylist() for i in range(batch.num_columns)]
        for vals in zip(*pycols):
            canonical = [_canonical_digest_scalar(v) for v in vals]
            h.update(json.dumps(canonical, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode())
            h.update(b'\n')
    return h.hexdigest()


def read_dates(path: Path) -> list[int]:
    vals = [int(x) for x in path.read_text(encoding='utf-8').strip().split(',') if x.strip()]
    if len(vals) != EXPECTED_DATES or len(set(vals)) != EXPECTED_DATES or vals != sorted(vals):
        raise RuntimeError(f'INVALID_SIGNAL_DATE_ORDINALS:{len(vals)}')
    return vals


def load_segments(paths: list[Path], n_dates: int) -> list[set[str]]:
    rows = []
    for p in paths:
        with p.open('r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('ticker,'):
                    continue
                ticker, a, b = s.split(',')
                a = int(a); b = int(b)
                if a < 0 or b < a or b >= n_dates:
                    raise RuntimeError(f'INVALID_SEGMENT:{p.name}:{s}')
                rows.append((str(ticker).zfill(4), a, b))
    memberships = [set() for _ in range(n_dates)]
    for ticker, a, b in rows:
        for i in range(a, b + 1):
            memberships[i].add(ticker)
    return memberships


def normalize_stock_id(x) -> str:
    s = str(x).strip()
    if re.fullmatch(r'\d+(?:\.0+)?', s):
        s = s.split('.')[0]
        if len(s) <= 4:
            return s.zfill(4)
    return s


def validate_memberships(dates: list[int], u100: list[set[str]], mother: list[set[str]]) -> None:
    if len(u100) != len(dates) or len(mother) != len(dates):
        raise RuntimeError('MEMBERSHIP_LENGTH_MISMATCH')
    for i, (u, m) in enumerate(zip(u100, mother)):
        if len(u) != EXPECTED_U100:
            raise RuntimeError(f'U100_SIZE_NOT_100:index={i}:n={len(u)}')
        if not u.issubset(m):
            raise RuntimeError(f'U100_NOT_SUBSET_MOTHER:index={i}:missing={sorted(u-m)[:5]}')


def audit_stock_level_integrity(pdf: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, set[str]]]:
    p = pdf.copy()
    p['stock_norm'] = p['stock_id'].map(normalize_stock_id)
    p['trader_norm'] = p['securities_trader_id'].astype('string').str.strip()
    p['buy_num'] = pd.to_numeric(p['buy_volume'], errors='coerce')
    p['sell_num'] = pd.to_numeric(p['sell_volume'], errors='coerce')

    duplicate_mask = p.duplicated(['date','stock_id','securities_trader_id'], keep=False)
    bad_volume_mask = (
        ~np.isfinite(p['buy_num'].to_numpy(float)) |
        ~np.isfinite(p['sell_num'].to_numpy(float)) |
        (p['buy_num'].to_numpy(float) < 0) |
        (p['sell_num'].to_numpy(float) < 0)
    )
    bad_identity_mask = p['securities_trader_id'].isna() | p['trader_norm'].isna() | (p['trader_norm'] == '')

    bad = {
        'duplicate_key': set(p.loc[duplicate_mask, 'stock_norm'].astype(str)),
        'invalid_volume': set(p.loc[bad_volume_mask, 'stock_norm'].astype(str)),
        'invalid_identity': set(p.loc[bad_identity_mask, 'stock_norm'].astype(str)),
    }
    return p, bad


def compute_u100_hhi(
    audited: pd.DataFrame,
    target: set[str],
    missing_source: set[str],
    bad: dict[str, set[str]],
) -> tuple[dict[str, float], dict[str, str]]:
    invalid: dict[str, str] = {}
    for t in sorted(target):
        reasons = []
        if t in missing_source:
            reasons.append('MISSING_SOURCE_DATA')
        if t in bad['duplicate_key']:
            reasons.append('DUPLICATE_KEY')
        if t in bad['invalid_volume']:
            reasons.append('INVALID_VOLUME')
        if t in bad['invalid_identity']:
            reasons.append('INVALID_IDENTITY')
        if reasons:
            invalid[t] = '+'.join(reasons)

    out: dict[str, float] = {}
    for t in sorted(target - set(invalid)):
        s = audited[audited['stock_norm'] == t].copy()
        if s.empty:
            invalid[t] = 'MISSING_SOURCE_DATA'
            continue
        s['gross'] = s['buy_num'] + s['sell_num']
        s = s[s['gross'] > 0].copy()
        total = float(s['gross'].sum())
        if not np.isfinite(total) or total <= 0:
            invalid[t] = 'ZERO_TOTAL_GROSS_VOLUME'
            continue
        v = float(((s['gross'] / total) ** 2).sum())
        if not np.isfinite(v) or not (0.0 < v <= 1.0 + 1e-12):
            invalid[t] = 'HHI_RANGE_INVALID'
            continue
        out[t] = v
    return out, invalid


async def process(args) -> dict:
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    from finmind_mcp.client import FinMindClient

    root = Path(args.extract_root)
    dates = read_dates(root / 'h20_dates_ord.txt')
    u100 = load_segments(sorted(root.glob('u100.part*')), len(dates))
    mother = load_segments(sorted(root.glob('mother.part*')), len(dates))
    validate_memberships(dates, u100, mother)

    if args.total_shards <= 0 or args.shard < 0 or args.shard >= args.total_shards:
        raise RuntimeError('INVALID_SHARD_ARGUMENTS')
    chosen_indices = list(range(args.shard, len(dates), args.total_shards))

    out = {
        'schema_version': 2,
        'system': 'HENGCE',
        'artifact': 'BROKER_HHI_SOURCE_ONLY_SHARD',
        'authority': 'DERIVED_SOURCE_FEATURE_AND_LINEAGE_ONLY_NO_OUTCOME_NO_TRADING_AUTHORITY',
        'prereg_commit': PREREG_COMMIT,
        'pit_contract_blob_sha': PIT_CONTRACT_BLOB,
        'dataset': DATASET,
        'source_plan': SOURCE_PLAN,
        'source_revision_class': SOURCE_CLASS,
        'canonical_mother_sha256': MOTHER_SHA256,
        'missingness_semantics': 'STOCK_DATE_FAIL_CLOSED; DATE_AUDIT_CONTINUES; PRIMARY_COMPLETE_CASE_GATE_IS_LATER',
        'shard': args.shard,
        'total_shards': args.total_shards,
        'selected_date_count': len(chosen_indices),
        'status': 'PASS_SHARD',
        'errors': [],
        'daily': [],
        'raw_broker_rows_persisted': False,
        'forward_returns_loaded': False,
    }

    if not os.environ.get('FINMIND_TOKEN'):
        out['status'] = 'DATA_OR_LINEAGE_INVALID'
        out['errors'].append('FINMIND_TOKEN_MISSING')
        return out

    client = FinMindClient()
    with tempfile.TemporaryDirectory(prefix=f'hengce-broker-source-{args.shard}-') as td0:
        td = Path(td0)
        for seq, idx in enumerate(chosen_indices, 1):
            d = datetime.fromordinal(dates[idx]).date().isoformat()
            target = u100[idx]
            expected_mother = mother[idx]
            raw = td / f'{d}.parquet'
            retrieval_utc = datetime.now(timezone.utc).isoformat()
            retrieval_taipei = datetime.now(ZoneInfo('Asia/Taipei')).isoformat()
            last_err = None
            for attempt in range(5):
                try:
                    signed = await client.storage_object_url(DATASET, d)
                    await client.download(signed, raw)
                    last_err = None
                    break
                except Exception as exc:
                    last_err = f'{type(exc).__name__}:{exc}'
                    await asyncio.sleep(min(20.0, 1.5 * (2 ** attempt)))
            if last_err is not None or not raw.is_file():
                out['status'] = 'DATA_OR_LINEAGE_INVALID'
                out['errors'].append(f'{d}:TRANSPORT_OR_OBJECT_UNAVAILABLE:{last_err}')
                break

            try:
                physical_sha = sha256_file(raw)
                physical_bytes = raw.stat().st_size
                pf = pq.ParquetFile(raw)
                cols = pf.schema_arrow.names
                missing_cols = sorted(set(EXPECTED_COLS) - set(cols))
                if missing_cols:
                    raise RuntimeError(f'MISSING_REQUIRED_SCHEMA:{missing_cols}')
                table = pf.read(columns=EXPECTED_COLS)
                if table.num_rows <= 0:
                    raise RuntimeError('PARQUET_EMPTY_SOURCE_OBJECT')
                observed_dates = {str(x) for x in pc.unique(table['date']).to_pylist() if x is not None}
                if observed_dates != {d}:
                    raise RuntimeError(f'SOURCE_DATE_MISMATCH:{sorted(observed_dates)}')

                logical_sha = logical_content_sha256(table)
                pdf = table.to_pandas()
                audited, bad = audit_stock_level_integrity(pdf)
                observed_stocks = set(audited['stock_norm'].dropna().astype(str))
                missing_mother = expected_mother - observed_stocks
                hhi, u100_invalid = compute_u100_hhi(audited, target, missing_mother, bad)

                broker_ids = {str(x) for x in pdf['securities_trader_id'].dropna().astype(str)}
                daily = {
                    'date_index': idx,
                    'date': d,
                    'status': 'PASS_SOURCE_DATE_AUDIT',
                    'retrieval_timestamp_utc': retrieval_utc,
                    'retrieval_timestamp_taipei': retrieval_taipei,
                    'query_or_download_mode': 'FinMindClient.storage_object_url whole-day parquet',
                    'row_count': int(table.num_rows),
                    'unique_stock_id_count': len(observed_stocks),
                    'unique_securities_trader_id_count': len(broker_ids),
                    'physical_object_sha256': physical_sha,
                    'physical_object_bytes': physical_bytes,
                    'logical_content_sha256': logical_sha,
                    'logical_digest_spec': 'HENGCE_LOGICAL_ROW_HASH_V2_NONFINITE_CANONICAL_SORT_ALL_REQUIRED_FIELDS_JSON_LINES',
                    'schema_field_list': cols,
                    'canonical_mother_sha256': MOTHER_SHA256,
                    'date_specific_mother_traded_symbol_count': len(expected_mother),
                    'observed_missing_among_mother_traded_symbols': len(missing_mother),
                    'missing_mother_traded_symbols': sorted(missing_mother),
                    'duplicate_key_stock_count': len(bad['duplicate_key']),
                    'invalid_volume_stock_count': len(bad['invalid_volume']),
                    'invalid_identity_stock_count': len(bad['invalid_identity']),
                    'u100_count': len(target),
                    'u100_valid_hhi_count': len(hhi),
                    'u100_missing_feature_count': len(u100_invalid),
                    'u100_missing_feature_by_stock': u100_invalid,
                    'hhi_by_stock': hhi,
                    'source_revision_class': SOURCE_CLASS,
                }
                out['daily'].append(daily)
            except Exception as exc:
                out['status'] = 'DATA_OR_LINEAGE_INVALID'
                out['errors'].append(f'{d}:DATE_OBJECT_INTEGRITY:{type(exc).__name__}:{exc}')
                break
            finally:
                try:
                    raw.unlink(missing_ok=True)
                except Exception:
                    pass
            if seq % 10 == 0:
                print(f'SOURCE_PASS_PROGRESS shard={args.shard} {seq}/{len(chosen_indices)} dates')

    if out['status'] == 'PASS_SHARD':
        if len(out['daily']) != len(chosen_indices):
            out['status'] = 'DATA_OR_LINEAGE_INVALID'
            out['errors'].append('PROCESSED_DATE_COUNT_MISMATCH')
        else:
            out['summary'] = {
                'processed_dates': len(out['daily']),
                'expected_selected_dates': len(chosen_indices),
                'dates_with_any_mother_missing': sum(x['observed_missing_among_mother_traded_symbols'] > 0 for x in out['daily']),
                'dates_with_any_u100_feature_missing': sum(x['u100_missing_feature_count'] > 0 for x in out['daily']),
                'minimum_u100_valid_hhi_count': min(x['u100_valid_hhi_count'] for x in out['daily']),
            }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--extract-root', required=True)
    ap.add_argument('--shard', required=True, type=int)
    ap.add_argument('--total-shards', required=True, type=int)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    try:
        out = asyncio.run(process(a))
    except Exception as exc:
        out = {
            'schema_version': 2,
            'system': 'HENGCE',
            'artifact': 'BROKER_HHI_SOURCE_ONLY_SHARD',
            'authority': 'DERIVED_SOURCE_FEATURE_AND_LINEAGE_ONLY_NO_OUTCOME_NO_TRADING_AUTHORITY',
            'prereg_commit': PREREG_COMMIT,
            'shard': a.shard,
            'total_shards': a.total_shards,
            'status': 'DATA_OR_LINEAGE_INVALID',
            'errors': [f'TOPLEVEL:{type(exc).__name__}:{exc}'],
            'daily': [],
            'raw_broker_rows_persisted': False,
            'forward_returns_loaded': False,
        }
    p = Path(a.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({
        'shard': out.get('shard'), 'status': out.get('status'),
        'selected_date_count': out.get('selected_date_count'),
        'processed_dates': len(out.get('daily', [])),
        'error_count': len(out.get('errors', [])),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
