#!/usr/bin/env python3
import csv, hashlib, io, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
MAX_WORKERS = 6


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def decode_twse(content):
    for enc in ('utf-8-sig', 'utf-8', 'cp950', 'big5'):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            pass
    return content.decode('utf-8', errors='replace')


def parse_twse_csv(text):
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
        row = row + [''] * max(0, len(hdr) - len(row))
        rec = {hdr[i]: row[i].strip() for i in range(min(len(hdr), len(row)))}
        ticker = rec.get('證券代號', '').strip().replace('=', '').replace('"', '')
        name = rec.get('證券名稱', '').strip()
        if ticker and name and re.match(r'^[0-9A-Za-z]{4,8}$', ticker):
            rec['_ticker'] = ticker
            rec['_name'] = name
            data.append(rec)
    return data, hdr


def fetch_twse_day(d):
    ds = d.strftime('%Y%m%d')
    params = {'date': ds, 'type': '13', 'response': 'csv'}
    last = None
    for attempt in range(3):
        try:
            r = requests.get(TWSE_URL, params=params, headers=UA, timeout=(5, 12))
            if r.status_code == 200 and r.content:
                rows, hdr = parse_twse_csv(decode_twse(r.content))
                tickers = [x['_ticker'] for x in rows]
                uniq = set(tickers)
                if not rows:
                    status = 'NO_DATA'
                elif len(rows) != len(uniq) or len(rows) < 150:
                    status = 'REVIEW'
                else:
                    status = 'PASS'
                return d, status, rows, bool(hdr), None
            last = f'HTTP {r.status_code}'
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:
            last = repr(e)
        time.sleep(0.6 * (2 ** attempt))
    return d, 'ERROR', [], False, last


def weekday_dates():
    out = []
    d = START
    while d <= END:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def acquire_twse():
    membership_path = OUT / 'twse_electronics_membership_2024_2025.csv'
    qa_path = OUT / 'twse_electronics_daily_qa_2024_2025.csv'
    checkpoint_path = OUT / 'twse_acquisition_checkpoint.jsonl'
    dates = weekday_dates()
    members = []
    qa = []
    completed = 0

    with checkpoint_path.open('w', encoding='utf-8') as cp, ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_twse_day, d): d for d in dates}
        for fut in as_completed(futs):
            d, status, rows, header_found, err = fut.result()
            uniq = len(set(x['_ticker'] for x in rows))
            qa_rec = {
                'date': d.isoformat(), 'status': status, 'rows': len(rows),
                'unique_tickers': uniq, 'header_found': header_found, 'error': err or ''
            }
            qa.append(qa_rec)
            cp.write(json.dumps(qa_rec, ensure_ascii=False) + '\n')
            cp.flush()
            for rec in rows:
                members.append({
                    'date': d.isoformat(), 'ticker': rec['_ticker'], 'name': rec['_name'],
                    'open': rec.get('開盤價',''), 'high': rec.get('最高價',''),
                    'low': rec.get('最低價',''), 'close': rec.get('收盤價',''),
                    'volume_shares': rec.get('成交股數',''), 'turnover_ntd': rec.get('成交金額','')
                })
            completed += 1
            if completed % 25 == 0:
                print(f'TWSE checkpoint {completed}/{len(dates)}', flush=True)

    qa.sort(key=lambda x: x['date'])
    members.sort(key=lambda x: (x['date'], x['ticker']))
    with membership_path.open('w', newline='', encoding='utf-8') as f:
        fields = ['date','ticker','name','open','high','low','close','volume_shares','turnover_ntd']
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(members)
    with qa_path.open('w', newline='', encoding='utf-8') as f:
        fields = ['date','status','rows','unique_tickers','header_found','error']
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(qa)

    pass_days = [x for x in qa if x['status'] == 'PASS']
    errors = [x for x in qa if x['status'] == 'ERROR']
    review = [x for x in qa if x['status'] == 'REVIEW']
    no_data = [x for x in qa if x['status'] == 'NO_DATA']
    return {
        'collector_version': 'v2_parallel_checkpointed',
        'weekday_candidates': len(dates),
        'trading_days_pass': len(pass_days),
        'no_data_weekdays': len(no_data),
        'errors': len(errors),
        'review_days': len(review),
        'membership_rows': len(members),
        'first_pass_date': pass_days[0]['date'] if pass_days else None,
        'last_pass_date': pass_days[-1]['date'] if pass_days else None,
        'membership_path': str(membership_path), 'qa_path': str(qa_path),
        'membership_sha256': sha256(membership_path), 'qa_sha256': sha256(qa_path)
    }


def acquire_nasdaq(symbol):
    params = {'startDate':'2024-01-01T00:00:00.000','endDate':'2025-12-31T00:00:00.000','timeOfDay':'EOD'}
    last = None
    for attempt in range(3):
        try:
            r = requests.get(NASDAQ_EXPORT.format(symbol=symbol), params=params, headers=UA, timeout=(5, 20))
            if r.status_code == 200 and r.content:
                path = OUT / f'nasdaq_{symbol.lower()}_2024_2025.csv'
                path.write_bytes(r.content)
                text = r.content.decode('utf-8-sig', errors='replace')
                parsed = [x for x in csv.reader(io.StringIO(text)) if any(c.strip() for c in x)]
                return {'symbol':symbol,'path':str(path),'bytes':len(r.content),
                        'rows_total_nonempty':len(parsed),'sha256':sha256(path),'url':r.url}
            last = f'HTTP {r.status_code}'
        except Exception as e:
            last = repr(e)
        time.sleep(0.8 * (2 ** attempt))
    raise RuntimeError(last)


def main():
    receipt = {
        'system':'HENGCE',
        'study':'SOX x Taiwan Electronics Cross-Market Response',
        'stage':'OFFICIAL_PIT_ARCHIVE_ACQUISITION',
        'historical_window':['2024-01-01','2025-12-31'],
        'production_core_effect':'NONE','capital_authority':False,
        'sources':{
            'TWSE_membership':'TWSE MI_INDEX type=13 historical daily CSV',
            'SOX':'Nasdaq Index ExportHistory/SOX','COMP':'Nasdaq Index ExportHistory/COMP'
        }
    }
    receipt['twse'] = acquire_twse()
    nasdaq = {}
    with ThreadPoolExecutor(max_workers=2) as ex:
        fs = {ex.submit(acquire_nasdaq, s): s for s in ('SOX','COMP')}
        for fut in as_completed(fs):
            s = fs[fut]
            try:
                nasdaq[s] = fut.result()
            except Exception as e:
                nasdaq[s] = {'status':'ERROR','error':str(e)[:500]}
    receipt['nasdaq'] = nasdaq

    twse_ok = receipt['twse']['trading_days_pass'] >= 470 and receipt['twse']['errors'] == 0 and receipt['twse']['review_days'] == 0
    sox_ok = 'sha256' in nasdaq.get('SOX', {})
    comp_ok = 'sha256' in nasdaq.get('COMP', {})
    receipt['hard_gate'] = 'PASS' if twse_ok and sox_ok and comp_ok else 'FAIL_REVIEW'
    receipt['next_only_action'] = 'BUILD_US_TO_TWSE_ALIGNMENT_PANEL' if receipt['hard_gate'] == 'PASS' else 'REPAIR_SOURCE_ARCHIVE_QA_ONLY'
    rp = OUT / 'acquisition_receipt.json'
    rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)
    if receipt['hard_gate'] != 'PASS':
        sys.exit(2)

if __name__ == '__main__':
    main()
