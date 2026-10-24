#!/usr/bin/env python3
import csv, hashlib, io, json, re, time
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
import requests

START = date(2026, 1, 1)
END = date(2026, 10, 22)
OUT = Path('research/rr_v1_pit_2026_evidence_20261024/output')
RAW = OUT / 'raw'
OUT.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)
TWSE_URL = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
UA = {'User-Agent': 'Mozilla/5.0 (HENGCE research evidence acquisition)'}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
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
    out = []
    for row in rows[header_idx + 1:]:
        if not row or len(row) < 2:
            continue
        row = row + [''] * max(0, len(hdr) - len(row))
        rec = {hdr[i]: row[i].strip() for i in range(min(len(hdr), len(row)))}
        ticker = rec.get('證券代號', '').strip().replace('=', '').replace('"', '')
        name = rec.get('證券名稱', '').strip()
        if re.fullmatch(r'[0-9]{4}', ticker) and name:
            out.append({
                'date': '', 'ticker': ticker, 'name': name,
                'open': rec.get('開盤價',''), 'high': rec.get('最高價',''),
                'low': rec.get('最低價',''), 'close': rec.get('收盤價',''),
                'volume_shares': rec.get('成交股數',''),
                'turnover_ntd': rec.get('成交金額','')
            })
    return out, hdr


def dates():
    d = START
    while d <= END:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def fetch_day(d):
    ds = d.strftime('%Y%m%d')
    params = {'date': ds, 'type': '13', 'response': 'csv'}
    last = None
    for attempt in range(3):
        ts = datetime.now(timezone.utc).isoformat()
        try:
            r = requests.get(TWSE_URL, params=params, headers=UA, timeout=(5, 20))
            raw = r.content or b''
            raw_sha = sha256_bytes(raw)
            raw_path = RAW / f'{ds}.csv'
            if raw:
                raw_path.write_bytes(raw)
            if r.status_code == 200 and raw:
                parsed, hdr = parse_twse_csv(decode_twse(raw))
                for x in parsed:
                    x['date'] = d.isoformat()
                n = len(parsed)
                u = len({x['ticker'] for x in parsed})
                if not parsed:
                    status = 'NO_DATA'
                elif n != u or n < 150:
                    status = 'REVIEW'
                else:
                    status = 'PASS'
                return parsed, {
                    'date': d.isoformat(), 'status': status,
                    'http_status': r.status_code, 'retrieved_at_utc': ts,
                    'request_date': ds, 'request_type': '13', 'request_response': 'csv',
                    'rows': n, 'unique_four_digit_tickers': u,
                    'header_found': bool(hdr), 'raw_sha256': raw_sha,
                    'raw_path': str(raw_path), 'error': ''
                }
            last = f'HTTP {r.status_code}'
        except Exception as e:
            last = repr(e)
        time.sleep(0.8 * (2 ** attempt))
    return [], {
        'date': d.isoformat(), 'status': 'ERROR', 'http_status': '',
        'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
        'request_date': ds, 'request_type': '13', 'request_response': 'csv',
        'rows': 0, 'unique_four_digit_tickers': 0, 'header_found': False,
        'raw_sha256': '', 'raw_path': '', 'error': last or 'unknown'
    }


def main():
    members, qa = [], []
    for d in dates():
        day_rows, rec = fetch_day(d)
        members.extend(day_rows)
        qa.append(rec)
        print(json.dumps(rec, ensure_ascii=False), flush=True)

    members.sort(key=lambda x: (x['date'], x['ticker']))
    qa.sort(key=lambda x: x['date'])
    membership_path = OUT / 'twse_electronics_membership_2026_to_20261022.csv'
    qa_path = OUT / 'twse_electronics_daily_qa_2026_to_20261022.csv'

    with membership_path.open('w', newline='', encoding='utf-8') as f:
        fields = ['date','ticker','name','open','high','low','close','volume_shares','turnover_ntd']
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(members)
    with qa_path.open('w', newline='', encoding='utf-8') as f:
        fields = ['date','status','http_status','retrieved_at_utc','request_date','request_type','request_response','rows','unique_four_digit_tickers','header_found','raw_sha256','raw_path','error']
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(qa)

    receipt = {
        'system': 'HENGCE',
        'task_id': 'HENGCE-RR-V1-PIT-2026-EVIDENCE-20261024',
        'source': 'TWSE MI_INDEX type=13 historical daily CSV',
        'date_start': START.isoformat(), 'date_end': END.isoformat(),
        'ticker_scope': 'FOUR_ASCII_DIGITS',
        'weekday_candidates': len(qa),
        'pass_days': sum(x['status']=='PASS' for x in qa),
        'no_data_days': sum(x['status']=='NO_DATA' for x in qa),
        'review_days': sum(x['status']=='REVIEW' for x in qa),
        'error_days': sum(x['status']=='ERROR' for x in qa),
        'membership_rows': len(members),
        'membership_sha256': sha256_file(membership_path),
        'qa_sha256': sha256_file(qa_path),
        'new_model_evaluations': 0,
        'rr_v1_total_model_evaluations': 8529,
        'stage_b_ran': False,
        'hard_gate': 'PASS' if all(x['status'] in ('PASS','NO_DATA') for x in qa) else 'BLOCKED_REVIEW'
    }
    rp = OUT / 'PIT_2026_EVIDENCE_RECEIPT.json'
    rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)

if __name__ == '__main__':
    main()
