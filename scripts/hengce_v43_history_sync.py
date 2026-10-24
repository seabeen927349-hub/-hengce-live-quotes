#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo('Asia/Taipei')
TWSE = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
UA = {'User-Agent': 'Mozilla/5.0 HENGCE-V43-DAILY/1.0', 'Accept': 'application/json', 'Referer': 'https://www.twse.com.tw/'}
FIELDS = ['date','ticker','name','open','high','low','close','volume_shares','turnover_ntd']
MIN_MEMBERS = 150


def clean(x) -> str:
    return '' if x is None else str(x).replace(',', '').strip()


def atomic_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def latest_date(path: Path) -> date:
    latest = None
    seen = set()
    with path.open(encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames or not set(FIELDS).issubset(rd.fieldnames):
            raise RuntimeError('V43_HISTORY_COLUMNS_MISSING')
        for r in rd:
            ds = str(r.get('date') or '').strip()
            t = str(r.get('ticker') or '').strip()
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', ds) or not re.fullmatch(r'[1-9]\d{3}', t):
                continue
            key = (ds, t)
            if key in seen:
                raise RuntimeError(f'V43_HISTORY_DUPLICATE:{ds}:{t}')
            seen.add(key)
            d = date.fromisoformat(ds)
            latest = d if latest is None or d > latest else latest
    if latest is None:
        raise RuntimeError('V43_HISTORY_EMPTY')
    return latest


def fetch_type13(target: date) -> tuple[str, list[dict]]:
    ds = target.strftime('%Y%m%d')
    r = requests.get(TWSE, params={'date': ds, 'type': '13', 'response': 'json'}, headers=UA, timeout=(8, 45))
    r.raise_for_status()
    payload = r.json()
    if str(payload.get('stat')).upper() != 'OK':
        return f"TWSE_NOT_READY:{payload.get('stat')}", []
    table = None
    for t in payload.get('tables') or []:
        fs = t.get('fields') or []
        if '證券代號' in fs and '收盤價' in fs:
            table = t
            break
    if table is None:
        return 'TWSE_TYPE13_SESSION_UNAVAILABLE:NO_SECURITY_TABLE', []
    fs = table.get('fields') or []
    idx = {x: i for i, x in enumerate(fs)}
    data = table.get('data') or table.get('records') or []

    def v(row, *names):
        for n in names:
            i = idx.get(n)
            if i is not None and i < len(row):
                return clean(row[i])
        return ''

    rows = []
    for row in data:
        ticker = v(row, '證券代號').replace('=', '').replace('"', '')
        if not re.fullmatch(r'[1-9]\d{3}', ticker):
            continue
        rows.append({
            'date': target.isoformat(),
            'ticker': ticker,
            'name': v(row, '證券名稱'),
            'open': v(row, '開盤價'),
            'high': v(row, '最高價'),
            'low': v(row, '最低價'),
            'close': v(row, '收盤價'),
            'volume_shares': v(row, '成交股數', '成交量'),
            'turnover_ntd': v(row, '成交金額'),
        })
    if len(rows) == 0:
        return 'TWSE_TYPE13_SESSION_UNAVAILABLE:ZERO_SECURITY_ROWS', []
    if len(rows) < MIN_MEMBERS:
        raise RuntimeError(f'V43_TYPE13_PARTIAL_ROWS_FAIL_CLOSED:{target.isoformat()}:{len(rows)}')
    rows.sort(key=lambda x: x['ticker'])
    if len({x['ticker'] for x in rows}) != len(rows):
        raise RuntimeError(f'V43_TYPE13_DUPLICATE_TICKER:{target.isoformat()}')
    return 'OK', rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--history', type=Path, default=Path('hengce/v43_daily/data/twse_electronics_history_2026.csv'))
    ap.add_argument('--through-date')
    ap.add_argument('--status', type=Path, default=Path('hengce/v43_daily/data_sync_latest.json'))
    a = ap.parse_args()

    now = datetime.now(TZ)
    through = date.fromisoformat(a.through_date) if a.through_date else now.date()
    if not a.history.exists() or a.history.stat().st_size < 100000:
        raise RuntimeError('V43_OWNED_HISTORY_MISSING_OR_TOO_SMALL')

    before = latest_date(a.history)
    if through < before:
        raise RuntimeError(f'V43_THROUGH_DATE_BEFORE_HISTORY:{through}:{before}')

    added = []
    skipped = []
    d = before + timedelta(days=1)
    while d <= through:
        if d.weekday() >= 5:
            skipped.append({'date': d.isoformat(), 'reason': 'WEEKEND'})
            d += timedelta(days=1)
            continue
        status, rows = fetch_type13(d)
        if status != 'OK':
            skipped.append({'date': d.isoformat(), 'reason': status})
            d += timedelta(days=1)
            continue
        with a.history.open('a', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writerows(rows)
        added.append({'date': d.isoformat(), 'rows': len(rows), 'source': 'TWSE_MI_INDEX_TYPE_13'})
        d += timedelta(days=1)

    after = latest_date(a.history)
    out = {
        'schema_version': 1,
        'system': 'HENGCE',
        'engine': 'HENGCE_V43_DAILY',
        'module': 'V43_INDEPENDENT_HISTORY_SYNC',
        'status': 'PASS_UPDATED' if added else 'PASS_NO_NEW_SESSION',
        'generated_at_taipei': now.isoformat(),
        'history_path': str(a.history),
        'history_latest_before': before.isoformat(),
        'history_latest_after': after.isoformat(),
        'through_date': through.isoformat(),
        'added_sessions': added,
        'skipped_dates': skipped,
        'history_ownership': 'HENGCE_V43_DAILY_OWNED',
        'runtime_source': 'TWSE_MI_INDEX_TYPE_13',
        'q017_runtime_read': False,
        'q017_runtime_dependency': False,
        'q017_write': False,
        'capital_authority_twd': 0,
        'broker_order_execution': False,
    }
    atomic_json(a.status, out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
