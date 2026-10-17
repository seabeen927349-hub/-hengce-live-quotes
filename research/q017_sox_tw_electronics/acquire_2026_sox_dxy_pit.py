#!/usr/bin/env python3
import csv, hashlib, io, json, math, random, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

START = date(2026, 1, 1)
END = date(2026, 10, 17)
OUT = Path('research/q017_sox_tw_electronics/archive_2026')
OUT.mkdir(parents=True, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (HENGCE Q017 research; PIT archival)'}
TWSE_URL = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
NASDAQ_EXPORT = 'https://indexes.nasdaq.com/Index/ExportHistory/SOX'
MAX_WORKERS = 2


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def decode_twse(content):
    for enc in ('utf-8-sig', 'utf-8', 'cp950', 'big5'):
        try: return content.decode(enc)
        except UnicodeDecodeError: pass
    return content.decode('utf-8', errors='replace')


def parse_twse_csv(text):
    rows = list(csv.reader(io.StringIO(text, newline='')))
    header_idx = None
    for i, row in enumerate(rows):
        joined = '|'.join(row)
        if '證券代號' in joined and '證券名稱' in joined and '收盤價' in joined:
            header_idx = i; break
    if header_idx is None: return [], None
    hdr = [x.strip().replace('\ufeff', '') for x in rows[header_idx]]
    data = []
    for row in rows[header_idx + 1:]:
        if not row or len(row) < 2: continue
        row = row + [''] * max(0, len(hdr) - len(row))
        rec = {hdr[i]: row[i].strip() for i in range(min(len(hdr), len(row)))}
        ticker = rec.get('證券代號', '').strip().replace('=', '').replace('"', '')
        name = rec.get('證券名稱', '').strip()
        if ticker and name and re.match(r'^[0-9A-Za-z]{4,8}$', ticker):
            rec['_ticker'] = ticker; rec['_name'] = name; data.append(rec)
    return data, hdr


def fetch_twse_day(d):
    params = {'date': d.strftime('%Y%m%d'), 'type': '13', 'response': 'csv'}
    last = None
    for attempt in range(6):
        try:
            time.sleep(0.18 + random.random() * 0.18)
            r = requests.get(TWSE_URL, params=params, headers=UA, timeout=(8, 25))
            if r.status_code == 200 and r.content:
                rows, hdr = parse_twse_csv(decode_twse(r.content))
                tickers = [x['_ticker'] for x in rows]
                status = 'NO_DATA' if not rows else ('PASS' if len(rows) == len(set(tickers)) and len(rows) >= 150 else 'REVIEW')
                return d, status, rows, bool(hdr), None
            last = f'HTTP {r.status_code}'
        except Exception as e:
            last = repr(e)
        time.sleep(min(12.0, 1.5 * (2 ** attempt)) + random.random())
    return d, 'ERROR', [], False, last


def weekday_dates():
    out, d = [], START
    while d <= END:
        if d.weekday() < 5: out.append(d)
        d += timedelta(days=1)
    return out


def acquire_twse():
    members, qa = [], []
    dates = weekday_dates()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_twse_day, d): d for d in dates}
        for n, fut in enumerate(as_completed(futs), 1):
            d, status, rows, header_found, err = fut.result()
            qa.append({'date': d.isoformat(), 'status': status, 'rows': len(rows), 'unique_tickers': len(set(x['_ticker'] for x in rows)), 'header_found': header_found, 'error': err or ''})
            for rec in rows:
                members.append({'date': d.isoformat(), 'ticker': rec['_ticker'], 'name': rec['_name'], 'open': rec.get('開盤價',''), 'high': rec.get('最高價',''), 'low': rec.get('最低價',''), 'close': rec.get('收盤價',''), 'volume_shares': rec.get('成交股數',''), 'turnover_ntd': rec.get('成交金額','')})
            if n % 20 == 0: print(f'TWSE {n}/{len(dates)}', flush=True)
    qa.sort(key=lambda x: x['date']); members.sort(key=lambda x: (x['date'], x['ticker']))
    mp = OUT / 'twse_electronics_membership_2026.csv'; qp = OUT / 'twse_electronics_daily_qa_2026.csv'
    with mp.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['date','ticker','name','open','high','low','close','volume_shares','turnover_ntd']); w.writeheader(); w.writerows(members)
    with qp.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['date','status','rows','unique_tickers','header_found','error']); w.writeheader(); w.writerows(qa)
    return {'weekday_candidates':len(dates),'pass_days':sum(x['status']=='PASS' for x in qa),'review_days':sum(x['status']=='REVIEW' for x in qa),'errors':sum(x['status']=='ERROR' for x in qa),'no_data_weekdays':sum(x['status']=='NO_DATA' for x in qa),'rows':len(members),'path':str(mp),'sha256':sha256(mp),'qa_path':str(qp),'qa_sha256':sha256(qp)}


def parse_sox_bytes(raw):
    records = None
    if raw.startswith(b'PK'):
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
        records = list(ws.iter_rows(values_only=True))
    else:
        text = raw.decode('utf-8-sig', errors='replace')
        records = list(csv.reader(io.StringIO(text, newline='')))
    rows=[]
    for rec in records:
        if len(rec) < 2: continue
        ds = rec[0]
        dt = None
        if isinstance(ds, datetime): dt = ds.date()
        else:
            for fmt in ('%m/%d/%Y','%Y-%m-%d','%m/%d/%Y %H:%M:%S'):
                try: dt=datetime.strptime(str(ds).strip(),fmt).date(); break
                except ValueError: pass
        if not dt or not (START <= dt <= END): continue
        try: close=float(str(rec[1]).replace(',','').strip())
        except (ValueError,TypeError): continue
        if math.isfinite(close) and close > 0: rows.append({'date':dt.isoformat(),'close':close})
    return sorted({x['date']:x for x in rows}.values(), key=lambda x:x['date'])


def acquire_sox():
    params={'startDate':'2026-01-01T00:00:00.000','endDate':'2026-10-17T00:00:00.000','timeOfDay':'EOD'}
    last=None
    for attempt in range(4):
        try:
            r=requests.get(NASDAQ_EXPORT,params=params,headers=UA,timeout=(8,30))
            if r.status_code==200 and r.content:
                raw=OUT/'nasdaq_sox_2026_raw.bin'; raw.write_bytes(r.content)
                rows=parse_sox_bytes(r.content)
                if len(rows) < 180: raise ValueError(f'SOX_ROWS_TOO_FEW:{len(rows)}')
                out=OUT/'sox_2026.csv'
                with out.open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=['date','close']);w.writeheader();w.writerows(rows)
                return {'status':'PASS','rows':len(rows),'path':str(out),'sha256':sha256(out),'raw_sha256':sha256(raw),'source_url':r.url}
            last=f'HTTP {r.status_code}'
        except Exception as e: last=repr(e)
        time.sleep(1.5*(2**attempt))
    return {'status':'ERROR','error':last}


def main():
    receipt={'system':'HENGCE','study':'Q017 2026 SOX x Taiwan Electronics','stage':'RESEARCH_ONLY_PIT_ACQUISITION','historical_window':[START.isoformat(),END.isoformat()],'production_core_effect':'NONE','capital_authority':False,'transport_intent':'GITHUB_ACTIONS_VESSEL','sources':{'TWSE_electronics':'TWSE MI_INDEX type=13','SOX':'Nasdaq ExportHistory/SOX'}}
    with ThreadPoolExecutor(max_workers=2) as ex:
        ft=ex.submit(acquire_twse); fs=ex.submit(acquire_sox)
        receipt['twse']=ft.result(); receipt['sox']=fs.result()
    tw=receipt['twse']
    receipt['hard_gate']='PASS' if tw['pass_days']>=180 and tw['errors']==0 and receipt['sox'].get('status')=='PASS' else 'FAIL_REVIEW'
    rp=OUT/'acquisition_receipt_2026.json'; rp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2), flush=True)
    return 0 if receipt['hard_gate']=='PASS' else 2

if __name__=='__main__': raise SystemExit(main())
