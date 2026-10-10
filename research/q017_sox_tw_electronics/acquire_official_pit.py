#!/usr/bin/env python3
import csv, hashlib, io, json, os, re, sys, time
from datetime import date, timedelta
from pathlib import Path

import requests

START = date(2024, 1, 1)
END = date(2025, 12, 31)
OUT = Path('research/q017_sox_tw_electronics/archive')
OUT.mkdir(parents=True, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (HENGCE research; official-source archival)'}

TWSE_URL = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
NASDAQ_EXPORT = 'https://indexes.nasdaq.com/Index/ExportHistory/{symbol}'


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def get(url, params=None, retries=5, timeout=30):
    last = None
    for k in range(retries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 200 and r.content:
                return r
            last = RuntimeError(f'HTTP {r.status_code} {r.url}')
        except Exception as e:
            last = e
        time.sleep(min(2 ** k, 8))
    raise last


def decode_twse(content: bytes):
    for enc in ('utf-8-sig', 'utf-8', 'cp950', 'big5'):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            pass
    return content.decode('utf-8', errors='replace')


def parse_twse_csv(text: str):
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = None
    for i, row in enumerate(rows):
        joined = '|'.join(row)
        if '證券代號' in joined and '證券名稱' in joined and '收盤價' in joined:
            header_idx = i
            break
    if header_idx is None:
        return [], None
    hdr = [x.strip().replace('\ufeff', '') for x in rows[header_idx]]
    data = []
    for row in rows[header_idx + 1:]:
        if not row or len(row) < 2:
            continue
        row = row + [''] * (len(hdr) - len(row))
        rec = {hdr[i]: row[i].strip() for i in range(min(len(hdr), len(row)))}
        ticker = rec.get('證券代號', '').strip().replace('=', '').replace('"', '')
        name = rec.get('證券名稱', '').strip()
        if not ticker or not name:
            continue
        if not re.match(r'^[0-9A-Za-z]{4,8}$', ticker):
            continue
        rec['_ticker'] = ticker
        rec['_name'] = name
        data.append(rec)
    return data, hdr


def acquire_twse():
    membership_path = OUT / 'twse_electronics_membership_2024_2025.csv'
    qa_path = OUT / 'twse_electronics_daily_qa_2024_2025.csv'
    members = []
    qa = []
    d = START
    request_count = 0
    while d <= END:
        if d.weekday() < 5:
            ds = d.strftime('%Y%m%d')
            try:
                r = get(TWSE_URL, {'date': ds, 'type': '13', 'response': 'csv'})
                request_count += 1
                text = decode_twse(r.content)
                rows, hdr = parse_twse_csv(text)
                tickers = [x['_ticker'] for x in rows]
                uniq = sorted(set(tickers))
                status = 'PASS' if len(rows) == len(uniq) and len(rows) >= 150 else ('NO_DATA' if len(rows) == 0 else 'REVIEW')
                qa.append({'date': d.isoformat(), 'status': status, 'rows': len(rows), 'unique_tickers': len(uniq), 'header_found': bool(hdr)})
                for rec in rows:
                    members.append({
                        'date': d.isoformat(),
                        'ticker': rec['_ticker'],
                        'name': rec['_name'],
                        'open': rec.get('開盤價',''),
                        'high': rec.get('最高價',''),
                        'low': rec.get('最低價',''),
                        'close': rec.get('收盤價',''),
                        'volume_shares': rec.get('成交股數',''),
                        'turnover_ntd': rec.get('成交金額',''),
                    })
            except Exception as e:
                qa.append({'date': d.isoformat(), 'status': 'ERROR', 'rows': 0, 'unique_tickers': 0, 'header_found': False, 'error': str(e)[:300]})
            time.sleep(0.35)
        d += timedelta(days=1)

    with membership_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['date','ticker','name','open','high','low','close','volume_shares','turnover_ntd'])
        w.writeheader(); w.writerows(members)
    with qa_path.open('w', newline='', encoding='utf-8') as f:
        fields = ['date','status','rows','unique_tickers','header_found','error']
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(qa)

    pass_days = [x for x in qa if x['status'] == 'PASS']
    errors = [x for x in qa if x['status'] == 'ERROR']
    review = [x for x in qa if x['status'] == 'REVIEW']
    return {
        'membership_path': str(membership_path),
        'qa_path': str(qa_path),
        'requests': request_count,
        'trading_days_pass': len(pass_days),
        'errors': len(errors),
        'review_days': len(review),
        'membership_rows': len(members),
        'first_pass_date': pass_days[0]['date'] if pass_days else None,
        'last_pass_date': pass_days[-1]['date'] if pass_days else None,
        'membership_sha256': sha256(membership_path),
        'qa_sha256': sha256(qa_path),
    }


def acquire_nasdaq(symbol):
    params = {
        'startDate': '2024-01-01T00:00:00.000',
        'endDate': '2025-12-31T00:00:00.000',
        'timeOfDay': 'EOD',
    }
    r = get(NASDAQ_EXPORT.format(symbol=symbol), params=params)
    path = OUT / f'nasdaq_{symbol.lower()}_2024_2025.csv'
    path.write_bytes(r.content)
    text = r.content.decode('utf-8-sig', errors='replace')
    parsed = list(csv.reader(io.StringIO(text)))
    nonempty = [x for x in parsed if any(c.strip() for c in x)]
    return {
        'symbol': symbol,
        'path': str(path),
        'bytes': len(r.content),
        'rows_total_nonempty': len(nonempty),
        'sha256': sha256(path),
        'url': r.url,
    }


def main():
    receipt = {
        'system': 'HENGCE',
        'study': 'SOX x Taiwan Electronics Cross-Market Response',
        'stage': 'OFFICIAL_PIT_ARCHIVE_ACQUISITION',
        'historical_window': ['2024-01-01','2025-12-31'],
        'production_core_effect': 'NONE',
        'capital_authority': False,
        'sources': {
            'TWSE_membership': 'TWSE MI_INDEX type=13 historical daily CSV',
            'SOX': 'Nasdaq Index ExportHistory/SOX',
            'COMP': 'Nasdaq Index ExportHistory/COMP',
        },
    }
    receipt['twse'] = acquire_twse()
    nasdaq = {}
    for symbol in ('SOX','COMP'):
        try:
            nasdaq[symbol] = acquire_nasdaq(symbol)
        except Exception as e:
            nasdaq[symbol] = {'status':'ERROR','error':str(e)[:500]}
    receipt['nasdaq'] = nasdaq

    twse_ok = receipt['twse']['trading_days_pass'] >= 470 and receipt['twse']['errors'] == 0 and receipt['twse']['review_days'] == 0
    sox_ok = 'sha256' in nasdaq.get('SOX', {})
    comp_ok = 'sha256' in nasdaq.get('COMP', {})
    receipt['hard_gate'] = 'PASS' if twse_ok and sox_ok and comp_ok else 'FAIL_REVIEW'
    receipt['next_only_action'] = 'BUILD_US_TO_TWSE_ALIGNMENT_PANEL' if receipt['hard_gate'] == 'PASS' else 'REPAIR_SOURCE_ARCHIVE_QA_ONLY'

    receipt_path = OUT / 'acquisition_receipt.json'
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt['hard_gate'] != 'PASS':
        sys.exit(2)

if __name__ == '__main__':
    main()
