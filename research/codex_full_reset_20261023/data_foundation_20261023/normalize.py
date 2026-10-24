"""Additional explicit offline schemas. Preserve initial collector refusals.

The acquisition implementation/receipts remain byte-exact. This adapter records
the supported slash-date representation and lower-case detail response status;
it does not grant adjusted-PnL readiness or alter any earlier model evaluation.
"""
import argparse
from decimal import Decimal
import gzip
import json
from pathlib import Path
import re

import evidence as e


def reduction(raw, year, membership):
    obj = json.loads(raw)
    fields = obj.get('fields', [])
    if '恢復買賣日期' not in fields:
        raise ValueError('REDUCTION_DATE_HEADER_MISSING')
    index = fields.index('恢復買賣日期')
    for row in obj.get('data', []):
        m = re.fullmatch(r'(\d{3})/(\d{2})/(\d{2})', row[index])
        if not m:
            raise ValueError('REDUCTION_SLASH_DATE_SCHEMA_MISMATCH')
        row[index] = f'{m[1]}年{m[2]}月{m[3]}日'
    result = e.annual_projection(json.dumps(obj), 'TWTAUU', year, membership)
    return {**result, 'normalization': 'ROC_SLASH_TO_ROC_IDEOGRAPHS_ONLY', 'raw_sha256': e.sha(raw)}


DETAIL_FIELDS = ['股票代號', '股票名稱', '(每股配發現金股利)除息', '(增資配股) 除權',
                 'A. 按普通股股東持股比例每千股無償配股', 'B. 員工紅利轉增資', 'C. (有償) 現金增資',
                 '每股認購金額', 'a. 公開承銷', 'b. 員工認購', ' c. 原股東認購', '按股東持股比例每千股認購']


def unit(value, suffix):
    m = re.fullmatch(r'(\d[\d,]*(?:\.\d+)?) '+re.escape(suffix), value)
    if not m:
        raise ValueError('UNRECOGNIZED_TERM_UNIT')
    return Decimal(m[1].replace(',', ''))


def detail(raw, ticker, day, parent):
    obj = json.loads(raw)
    if (obj.get('stat') not in ('ok', 'OK') or obj.get('fields') != DETAIL_FIELDS
            or not isinstance(obj.get('data'), list) or len(obj['data']) != 1
            or len(obj['data'][0]) != len(DETAIL_FIELDS)):
        raise ValueError('DETAIL_SCHEMA_OR_STATUS_MISMATCH')
    row = obj['data'][0]
    if row[0].strip() != ticker or parent['ticker'] != ticker or parent['effective_date'] != day:
        raise ValueError('DETAIL_IDENTITY_MISMATCH')
    cash = unit(row[2], '元／股')
    free = unit(row[4], '股')
    subscription = unit(row[6], '股')
    subscription_price = unit(row[7], '元／股')
    per1000_subscription = unit(row[11], '股')
    if subscription != 0 or subscription_price != 0 or per1000_subscription != 0:
        raise ValueError('PAID_SUBSCRIPTION_REQUIRES_SEPARATE_TERMS')
    expected_ref = (Decimal(str(parent['prior_close_reported']))-cash)/(1+free/1000)
    if abs(expected_ref-Decimal(str(parent['reference_price_reported']))) > Decimal('.011'):
        raise ValueError('DETAIL_REFERENCE_FORMULA_MISMATCH')
    return {'ticker':ticker, 'effective_date':day, 'cash_per_old_share_reported':str(cash),
            'free_shares_per_1000_old_shares_reported':str(free),
            'paid_subscription_shares_reported':str(subscription),
            'reference_formula_consistent_with_parent':True,
            'effective_date_binding':'REQUEST_AND_PARENT_EVENT_ONLY_DETAIL_HAS_NO_DATE_ECHO',
            'delivery_and_cash_payment_dates':None, 'original_first_seen_at':None,
            'adjusted_pnl_ready':False, 'raw_sha256':e.sha(raw), 'authority':e.AUTHORITY}


LIMIT_FIELDS = ['證券代號', '證券名稱', '漲停價', '開盤競價基準', '跌停價', '開盤競價基準',
                '收盤價', '買進揭示價', '賣出揭示價', '最近成交日', '可否零股交易']


def limits(raw, membership):
    obj = json.loads(raw)
    if obj.get('stat') != 'OK' or obj.get('date') != '20250407' or obj.get('fields') != LIMIT_FIELDS:
        raise ValueError('LIMIT_DATE_OR_POSITIONAL_SCHEMA_MISMATCH')
    result, seen = [], set()
    for row in obj.get('data', []):
        if len(row) != len(LIMIT_FIELDS) or row[0] in seen:
            raise ValueError('LIMIT_DUPLICATE_OR_ROW_WIDTH')
        seen.add(row[0])
        if row[0] not in membership.get('2025-04-07', set()):
            continue
        # Two identically named source columns have distinct time meanings.
        result.append({'ticker':row[0], 'date':'2025-04-07',
                       'upper_limit':e.number(row[2]), 'current_open_reference':e.number(row[3]),
                       'lower_limit':e.number(row[4]), 'previous_open_reference':e.number(row[5]),
                       'auction_fill_proven':False, 'authority':e.AUTHORITY})
    return result


def build(output):
    membership = {}
    for year in (2023, 2024, 2025):
        membership.update(e.load_expected(year)[0])
    manifest = json.loads((output/'MANIFEST.json').read_text())
    records = {r['id']:r for r in manifest['records']}
    def raw(key):
        r = records[key]
        compressed = (output/r['raw_path']).read_bytes()
        data = gzip.decompress(compressed)
        if e.sha(data) != r['response_sha256'] or e.sha(compressed) != r['archive_sha256']:
            raise ValueError('RAW_BYTES_CHANGED')
        return data
    reductions = [reduction(raw(f'TWTAUU_{year}'), year, membership) for year in (2023, 2024, 2025)]
    events = json.loads((output/'ELECTRONICS_EVENTS.json').read_text())['events']
    cases = []
    for ticker, day in (('6189','2025-07-25'), ('2364','2025-08-28')):
        parents = [r for r in events if r['ticker'] == ticker and r['effective_date'] == day]
        if len(parents) != 1:
            raise ValueError('PARENT_ACTION_NOT_UNIQUE')
        cases.append(detail(raw(f'DETAIL_{ticker}_{day.replace("-", "")}'), ticker, day, parents[0]))
    return {'raw_manifest_sha256':e.sha((output/'MANIFEST.json').read_bytes()),
            'normalizer_sha256':e.sha(Path(__file__).read_bytes()), 'authority':e.AUTHORITY,
            'initial_rejections_retained':True, 'new_model_evaluations':0,
            'reduction_projections':reductions, 'specific_action_terms':cases,
            'opening_references_20250407':limits(raw('OPEN_REFERENCE_20250407'), membership),
            'readiness':e.readiness()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', action='store_true')
    args = parser.parse_args()
    output = e.HERE/'results'
    result = build(output)
    target = output/'NORMALIZED_ADDITIONAL_EVIDENCE.json'
    if args.audit:
        if json.loads(target.read_text()) != result:
            raise ValueError('ADDITIONAL_EVIDENCE_MISMATCH')
    else:
        e.write_json(target, result)
    print(json.dumps({'audit':'PASS' if args.audit else 'NORMALIZED',
                      'electronics_reductions':sum(len(r['events']) for r in result['reduction_projections']),
                      'specific_action_terms':len(result['specific_action_terms']),
                      'opening_references':len(result['opening_references_20250407']),
                      'new_model_evaluations':0}))
