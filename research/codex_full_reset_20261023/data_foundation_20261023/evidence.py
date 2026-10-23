"""Research-only, bounded official-source collector and offline data contracts.

Neither reference prices nor repaired-looking OHLC grant decision/PnL authority.
Tests pass synthetic bytes; no networking occurs at import or during audit.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from reset_ledger import AUTHORITY
from stage_b_build_twse_year import load_expected


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, obj):
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        f.write('\n')


def iso(value):
    m = re.fullmatch(r'(\d{3})年(\d{2})月(\d{2})日', value)
    if not m:
        raise ValueError('INVALID_ROC_EFFECTIVE_DATE')
    return date(int(m[1])+1911, int(m[2]), int(m[3])).isoformat()


def number(value):
    # Explicit missing numeric values stay missing; never replace with zero.
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+)?', value.replace(',', '')):
        raise ValueError('INVALID_SOURCE_NUMBER')
    x = float(value.replace(',', ''))
    if not math.isfinite(x) or x <= 0:
        raise ValueError('NONPOSITIVE_SOURCE_PRICE')
    return x


def annual_projection(raw, kind, year, membership):
    """Allowlist historical event fields; current fundamentals never propagate."""
    obj = json.loads(raw)
    if obj.get('stat') != 'OK' or obj.get('strDate') != f'{year}0101' or obj.get('endDate') != f'{year}1231':
        raise ValueError('SOURCE_STATUS_OR_RANGE_MISMATCH')
    fields = obj.get('fields')
    if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields) or len(fields) != len(set(fields)):
        raise ValueError('INVALID_OR_DUPLICATE_HEADERS')
    if kind == 'TWT49U':
        required = ('資料日期', '股票代號', '股票名稱', '除權息前收盤價', '除權息參考價', '權/息')
    elif kind == 'TWTAUU':
        required = ('恢復買賣日期', '股票代號', '名稱', '停止買賣前收盤價格', '恢復買賣參考價', '減資原因')
    else:
        raise ValueError('UNSUPPORTED_REPORT')
    if not set(required).issubset(fields) or not isinstance(obj.get('data'), list):
        raise ValueError('SOURCE_SCHEMA_MISMATCH')
    title = str(obj.get('title', ''))
    if str(year-1911)+'年' not in title:
        raise ValueError('SOURCE_TITLE_DATE_MISMATCH')
    events, seen, quarantined = [], set(), sorted(set(fields)-set(required))
    for values in obj['data']:
        if not isinstance(values, list) or len(values) != len(fields):
            raise ValueError('SOURCE_ROW_LENGTH_MISMATCH')
        row = dict(zip(fields, values))
        day, ticker = iso(row[required[0]]), row['股票代號']
        if not day.startswith(str(year)) or not isinstance(ticker, str):
            raise ValueError('SOURCE_EFFECTIVE_DATE_OR_ID_MISMATCH')
        key = (day, ticker)
        if key in seen:
            raise ValueError('DUPLICATE_SOURCE_EVENT')
        seen.add(key)
        # Parse prices even out of scope: malformed source isn't silently hidden.
        old, ref = number(row[required[3]]), number(row[required[4]])
        if ticker not in membership.get(day, set()):
            continue
        if not re.fullmatch('[0-9]{4}', ticker):
            raise ValueError('UNEXPECTED_PIT_TICKER')
        events.append({'effective_date': day, 'ticker': ticker, 'name': row[required[2]],
                       'source_report': kind, 'prior_close_reported': old,
                       'reference_price_reported': ref, 'event_type_reported': row[required[5]],
                       'original_first_seen_at': None, 'revision_history': 'UNKNOWN',
                       'share_adjustment_factor': None, 'total_return_factor': None,
                       'adjusted_pnl_ready': False, 'authority': AUTHORITY})
    return {'events': sorted(events, key=lambda r: (r['effective_date'], r['ticker'])),
            'source_event_rows': len(seen), 'projected_electronics_events': len(events),
            'quarantined_fields': quarantined, 'authority': AUTHORITY}


def readiness():
    return {'status': 'BLOCKED_DATA_READINESS', 'new_model_evaluations': 0,
            'cumulative_prior_model_evaluations': 8529, 'authority': AUTHORITY,
            'reasons': ['CORPORATE_ACTION_TERMS_AND_DELIVERY_NOT_COMPLETE',
                        'SECURITY_IDENTITY_CONTINUITY_NOT_COMPLETE',
                        'ORIGINAL_PUBLICATION_AND_REVISION_HISTORY_UNPROVEN',
                        'AUCTION_ALLOCATION_AND_FILL_EVIDENCE_UNAVAILABLE'],
            'old_experiments_reclassified': False, 'hypothetical_adjusted_prices_generated': False}


def require_adjusted_pnl_ready():
    raise ValueError('BLOCKED_DATA_READINESS: reference tables alone cannot authorize adjusted PnL')


def requests():
    base = 'https://www.twse.com.tw/exchangeReport/'
    tasks = []
    for kind in ('TWT49U', 'TWTAUU'):
        for year in (2023, 2024, 2025):
            tasks.append({'id': f'{kind}_{year}', 'url': base+kind+f'?response=json&startDate={year}0101&endDate={year}1231',
                          'kind': kind, 'year': year})
    for ticker, day in (('6189', '20250725'), ('2364', '20250828')):
        tasks.append({'id': f'DETAIL_{ticker}_{day}',
                      'url': 'https://www.twse.com.tw/rwd/zh/exRight/TWT49UDetail?'+urllib.parse.urlencode({'response':'json','STK_NO':ticker,'T1':day}),
                      'kind': 'DETAIL', 'ticker': ticker, 'day': day})
    for ticker, month in (('2327', '20250801'), ('3090', '20250701')):
        tasks.append({'id': f'STOCK_DAY_{ticker}_{month}', 'kind': 'MONTHLY', 'ticker': ticker, 'month': month,
                      'url': base+'STOCK_DAY?'+urllib.parse.urlencode({'response':'json','stockNo':ticker,'date':month})})
    tasks += [
        {'id':'OPEN_REFERENCE_20250407', 'kind':'LIMIT', 'url':base+'TWT84U?response=json&date=20250407'},
        {'id':'SUSPENSION_3090_20250714', 'kind':'PDF', 'url':'https://www.twse.com.tw/staticFiles/news/news/tsecnews/8a8216d697fc438f019808c0ad380026.pdf'},
        {'id':'SPLIT_2327_20250825', 'kind':'PDF', 'url':'https://www.taifex.com.tw/file/taifex/CHINESE/11/attach/2327_20250825.pdf'},
    ]
    return tasks


def acquire(task, directory, opener=urllib.request.urlopen):
    """Exactly one attempt. Retain error bodies as well as successful bytes."""
    record = {**task, 'fetch_started_at_utc': datetime.now(timezone.utc).isoformat(),
              'original_first_seen_at': None, 'authority': AUTHORITY}
    raw = b''
    try:
        with opener(task['url'], timeout=25) as response:
            raw = response.read()
            record['http_status'] = response.status
            record['content_type'] = response.headers.get('Content-Type', '')
        record['transport'] = 'HTTP_RESPONSE_RETAINED'
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        record.update(http_status=exc.code, transport='HTTP_ERROR_RETAINED', error=str(exc))
    except Exception as exc:
        record.update(transport='TRANSPORT_FAILURE_RETAINED', error=type(exc).__name__+':'+str(exc))
    record['fetch_completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    record['raw_path'] = task['id']+'.bin.gz'
    compressed = gzip.compress(raw, mtime=0)
    with (directory/record['raw_path']).open('xb') as stream:
        stream.write(compressed)
    record.update(response_sha256=sha(raw), archive_sha256=sha(compressed), bytes=len(raw))
    return record, raw


def collect(output):
    output.mkdir(exist_ok=False)
    membership = {}
    for year in (2023, 2024, 2025):
        daily, _, _ = load_expected(year)
        membership.update(daily)
    manifest = {'authority': AUTHORITY, 'plan_sha256': sha((HERE/'PLAN.json').read_bytes()),
                'collector_sha256': sha(Path(__file__).read_bytes()), 'records': [],
                'readiness': readiness()}
    projected = []
    for task in requests():
        record, raw = acquire(task, output)
        try:
            if record.get('http_status') != 200:
                raise ValueError('HTTP_NOT_OK')
            if task['kind'] in ('TWT49U', 'TWTAUU'):
                projection = annual_projection(raw, task['kind'], task['year'], membership)
                write_json(output/(task['id']+'_projection.json'), projection)
                projected.extend(projection['events'])
                record['validation'] = 'VALIDATED_EVENT_TABLE_NOT_ADJUSTED_PRICES'
                record['source_event_rows'] = projection['source_event_rows']
                record['projected_electronics_events'] = projection['projected_electronics_events']
            elif task['kind'] == 'PDF':
                if not raw.startswith(b'%PDF-'):
                    raise ValueError('NOT_PDF')
                record['validation'] = 'PDF_BYTES_ONLY_CONTENT_REQUIRES_REVIEW'
            else:
                obj = json.loads(raw)
                if obj.get('stat') != 'OK' or not obj.get('data'):
                    raise ValueError('NONPASS_OR_EMPTY_REPORT')
                record['validation'] = 'UNVALIDATED_SCHEMA_EVIDENCE_ONLY'
                # These raw responses are not silently promoted to model inputs.
        except Exception as exc:
            record['validation'] = 'REJECTED'
            record['validation_reason'] = type(exc).__name__+':'+str(exc)
        manifest['records'].append(record)
        # Persist each attempt before the next request; crashes retain receipts.
        write_json(output/(task['id']+'_receipt.json'), record)
        print(json.dumps({k:record[k] for k in ('id','transport','validation')}, ensure_ascii=False), flush=True)
        time.sleep(1.5)
    write_json(output/'MANIFEST.json', manifest)
    write_json(output/'ELECTRONICS_EVENTS.json', {'events':projected, 'authority':AUTHORITY,
               'ready_for_adjusted_pnl':False, 'source':'validated projections only; not complete action coverage'})
    write_json(output/'READINESS.json', readiness())
    return manifest


def audit(output):
    manifest = json.loads((output/'MANIFEST.json').read_text())
    if manifest['authority'] != AUTHORITY or manifest['readiness'] != readiness():
        raise ValueError('AUTHORITY_OR_READINESS_DRIFT')
    if manifest['plan_sha256'] != sha((HERE/'PLAN.json').read_bytes()) or manifest['collector_sha256'] != sha(Path(__file__).read_bytes()):
        raise ValueError('PLAN_OR_COLLECTOR_DRIFT')
    expected = {r['id']:r for r in requests()}
    if {r['id'] for r in manifest['records']} != set(expected) or len(manifest['records']) != len(expected):
        raise ValueError('REQUEST_INVENTORY_MISMATCH')
    membership = {}
    for year in (2023, 2024, 2025):
        membership.update(load_expected(year)[0])
    projected = []
    for record in manifest['records']:
        task = expected[record['id']]
        if any(record[k] != value for k, value in task.items()):
            raise ValueError('REQUEST_PROVENANCE_DRIFT')
        archived = (output/record['raw_path']).read_bytes()
        raw = gzip.decompress(archived)
        if sha(archived) != record['archive_sha256'] or sha(raw) != record['response_sha256']:
            raise ValueError('RAW_HASH_MISMATCH')
        if json.loads((output/(record['id']+'_receipt.json')).read_text()) != record:
            raise ValueError('RECEIPT_MISMATCH')
        if record['validation'] == 'VALIDATED_EVENT_TABLE_NOT_ADJUSTED_PRICES':
            actual = annual_projection(raw, task['kind'], task['year'], membership)
            if actual != json.loads((output/(record['id']+'_projection.json')).read_text()):
                raise ValueError('PROJECTION_MISMATCH')
            projected.extend(actual['events'])
    all_events = json.loads((output/'ELECTRONICS_EVENTS.json').read_text())
    if all_events['events'] != projected or all_events['authority'] != AUTHORITY or all_events['ready_for_adjusted_pnl'] is not False:
        raise ValueError('PROJECTED_EVENT_OR_AUTHORITY_MISMATCH')
    if json.loads((output/'READINESS.json').read_text()) != readiness():
        raise ValueError('UNSUPPORTED_READINESS_PROMOTION')
    print(json.dumps({'audit':'PASS', 'requests':len(expected), 'electronics_events':len(projected),
                      'new_model_evaluations':0, 'readiness':'BLOCKED_DATA_READINESS'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--output', type=Path, default=HERE/'results')
    args = parser.parse_args()
    if args.collect == args.audit:
        parser.error('Choose exactly one of --collect or --audit')
    if args.collect:
        collect(args.output)
    else:
        audit(args.output)
