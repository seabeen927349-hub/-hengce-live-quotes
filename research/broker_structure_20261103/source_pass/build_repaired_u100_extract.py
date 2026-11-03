#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from pathlib import Path

EXPECTED_DATES = 1274
EXPECTED_U100 = 100
EXPECTED_REPAIRED_KEYSET_SHA256 = 'b0d010ba525f5ae9f93871c316da3ef6dedbd5ca4d64bafab3dac3281743b3d1'


def read_dates(path: Path) -> list[int]:
    vals = [int(x) for x in path.read_text(encoding='utf-8').strip().split(',') if x.strip()]
    if len(vals) != EXPECTED_DATES or len(set(vals)) != EXPECTED_DATES or vals != sorted(vals):
        raise RuntimeError(f'INVALID_SIGNAL_DATE_ORDINALS:{len(vals)}')
    return vals


def load_segments(paths: list[Path], n_dates: int) -> list[set[str]]:
    memberships = [set() for _ in range(n_dates)]
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
                ticker = str(ticker).zfill(4)
                for i in range(a, b + 1):
                    memberships[i].add(ticker)
    return memberships


def keyset_sha256(dates: list[int], memberships: list[set[str]]) -> str:
    lines = []
    from datetime import datetime
    for idx, tickers in enumerate(memberships):
        d = datetime.fromordinal(dates[idx]).date().isoformat()
        for t in tickers:
            lines.append(f'{d},{t}')
    lines.sort()
    raw = ('\n'.join(lines) + '\n').encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def compress_segments(memberships: list[set[str]]) -> list[tuple[str,int,int]]:
    by_ticker: dict[str,list[int]] = {}
    for idx, tickers in enumerate(memberships):
        for t in tickers:
            by_ticker.setdefault(t, []).append(idx)
    rows = []
    for ticker in sorted(by_ticker):
        vals = sorted(by_ticker[ticker])
        start = prev = vals[0]
        for x in vals[1:]:
            if x == prev + 1:
                prev = x
                continue
            rows.append((ticker, start, prev))
            start = prev = x
        rows.append((ticker, start, prev))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-root', required=True)
    ap.add_argument('--output-root', required=True)
    args = ap.parse_args()

    src = Path(args.source_root)
    out = Path(args.output_root)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    dates = read_dates(src / 'h20_dates_ord.txt')
    u100 = load_segments(sorted(src.glob('u100.part*')), len(dates))
    mother = load_segments(sorted(src.glob('mother.part*')), len(dates))

    overlay = src / 'u100_authority_key_repair.csv'
    if not overlay.is_file():
        raise RuntimeError('U100_AUTHORITY_REPAIR_OVERLAY_MISSING')
    seen_actions = set()
    with overlay.open('r', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            idx = int(r['date_idx'])
            if idx < 0 or idx >= len(dates):
                raise RuntimeError(f'REPAIR_DATE_IDX_INVALID:{idx}')
            expected_date = __import__('datetime').datetime.fromordinal(dates[idx]).date().isoformat()
            if r['date'] != expected_date:
                raise RuntimeError(f'REPAIR_DATE_MISMATCH:{idx}:{r["date"]}:{expected_date}')
            ticker = str(r['ticker']).zfill(4)
            action = r['action']
            key = (idx, action, ticker)
            if key in seen_actions:
                raise RuntimeError(f'DUPLICATE_REPAIR_ACTION:{key}')
            seen_actions.add(key)
            if action == 'REMOVE_STALE_EXPORT':
                if ticker not in u100[idx]:
                    raise RuntimeError(f'REPAIR_REMOVE_KEY_ABSENT:{idx}:{ticker}')
                u100[idx].remove(ticker)
            elif action == 'ADD_SEALED_AUTHORITY':
                if ticker in u100[idx]:
                    raise RuntimeError(f'REPAIR_ADD_KEY_ALREADY_PRESENT:{idx}:{ticker}')
                u100[idx].add(ticker)
            else:
                raise RuntimeError(f'REPAIR_ACTION_INVALID:{action}')

    if len(seen_actions) != 24:
        raise RuntimeError(f'REPAIR_ACTION_COUNT_NOT_24:{len(seen_actions)}')
    for idx, (u, m) in enumerate(zip(u100, mother)):
        if len(u) != EXPECTED_U100:
            raise RuntimeError(f'REPAIRED_U100_SIZE_NOT_100:{idx}:{len(u)}')
        if not u.issubset(m):
            raise RuntimeError(f'REPAIRED_U100_NOT_SUBSET_MOTHER:{idx}:{sorted(u-m)[:5]}')

    repaired_sha = keyset_sha256(dates, u100)
    if repaired_sha != EXPECTED_REPAIRED_KEYSET_SHA256:
        raise RuntimeError(f'REPAIRED_KEYSET_SHA_MISMATCH:{repaired_sha}')

    shutil.copy2(src / 'h20_dates_ord.txt', out / 'h20_dates_ord.txt')
    for p in sorted(src.glob('mother.part*')):
        shutil.copy2(p, out / p.name)
    shutil.copy2(overlay, out / overlay.name)
    audit = src / 'U100_AUTHORITY_KEY_REPAIR_AUDIT.json'
    if audit.is_file():
        shutil.copy2(audit, out / audit.name)

    rows = compress_segments(u100)
    chunk = 500
    for i in range(0, len(rows), chunk):
        p = out / f'u100.part{i//chunk:02d}'
        with p.open('w', encoding='utf-8', newline='') as f:
            f.write('ticker,start_idx,end_idx\n')
            for ticker, a, b in rows[i:i+chunk]:
                f.write(f'{ticker},{a},{b}\n')

    print(f'REPAIRED_U100_OK dates={len(dates)} rows={sum(len(x) for x in u100)} segments={len(rows)} keyset_sha256={repaired_sha}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
