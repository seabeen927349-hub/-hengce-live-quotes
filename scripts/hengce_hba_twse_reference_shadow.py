"""Unsigned official-reference shadow bridge. It never writes a formal settlement input."""
import argparse
import base64
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from hengce_hba_context_bridge_v1 import CARD_TZ, card_eod_leg, card_time
from hengce_hba_research_ledger import canonical, sha
from hengce_hba_research_reference import DOMAINS, OFFICIAL
from hengce_twse_calendar import is_trading_day, load_manifest

SCHEMA = 'HENGCE_TWSE_REFERENCE_SHADOW_V1'
PARSER = 'TWSE_REFERENCE_SHADOW_PARSER_V1'
MAX_BYTES = 2_000_000
BLOCKED = 'BLOCKED_SOURCE_VERIFICATION'
TAIEX = 'https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST'
HALTS = 'https://openapi.twse.com.tw/v1/exchangeReport/TWTAWU'
DELISTINGS = 'https://openapi.twse.com.tw/v1/company/suspendListingCsvAndHtml'
ACTIONS = 'https://www.twse.com.tw/rwd/zh/exRight/TWT49U'


def source_urls(day):
    value = day.strftime('%Y%m%d')
    return {
        'taiex': TAIEX,
        'halts': HALTS,
        'delistings': DELISTINGS,
        'corporate_actions': ACTIONS+'?'+urlencode({'startDate':value, 'endDate':value, 'response':'json'}),
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(url):
    from urllib.parse import urlsplit

    if urlsplit(url).netloc not in DOMAINS or not url.startswith('https://'):
        raise ValueError('TWSE_ORIGIN_REQUIRED')
    request = Request(url, headers={'Accept':'application/json', 'User-Agent':'HENGCE-TWSE-Research/1'})
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError('TWSE_ORIGIN_OR_STATUS_MISMATCH')
        payload = response.read(MAX_BYTES+1)
        # Timestamp after the complete body has arrived, never from a user-supplied date.
        observed = datetime.now(CARD_TZ)
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError('TWSE_BODY_SIZE')
    return payload, observed


def create_once(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        try:
            os.link(tmp.name, path)
        except FileExistsError:
            pass


def capture(root, kind, day, url):
    if url != source_urls(day).get(kind):
        raise ValueError('UNAPPROVED_SOURCE_OR_RECEIPT_IDENTITY')
    path = root/day.isoformat()/(kind+'.json')
    if not path.exists():
        payload, observed = fetch(url)
        # A malformed HTTP response does not become the first usable capture.
        json.loads(payload)
        receipt = {'schema': SCHEMA, 'dataset': kind, 'requested_session':day.isoformat(),
                   'source_url':url, 'source_raw_sha256':sha(payload),
                   'first_observed_at_taipei':observed.isoformat(),
                   'observation_scope':'FIRST_CAPTURE_IN_THIS_EVIDENCE_STORE',
                   'announced_at_taipei':None, 'raw_base64':base64.b64encode(payload).decode()}
        envelope = {'receipt': receipt, 'receipt_sha256': sha(canonical(receipt))}
        create_once(path, canonical(envelope))
    # A concurrent capture keeps the first committed receipt. A retry never rewrites it.
    return path


def open_capture(root, kind, day, url, cutoff):
    if url != source_urls(day).get(kind):
        raise ValueError('UNAPPROVED_SOURCE_OR_RECEIPT_IDENTITY')
    path = root/day.isoformat()/(kind+'.json')
    env = json.loads(path.read_bytes())
    receipt = env['receipt']
    if sha(canonical(receipt)) != env['receipt_sha256']:
        raise ValueError('RECEIPT_SHA_MISMATCH')
    if (receipt['schema'], receipt['dataset'], receipt['requested_session'], receipt['source_url']) != (
            SCHEMA, kind, day.isoformat(), url):
        raise ValueError('UNAPPROVED_SOURCE_OR_RECEIPT_IDENTITY')
    if receipt['announced_at_taipei'] is not None:
        raise ValueError('UNSUPPORTED_ANNOUNCEMENT_PROOF')
    observed = card_time(receipt['first_observed_at_taipei'])
    if (observed > cutoff or observed > datetime.now(CARD_TZ)
            or observed < datetime.combine(day, time(13, 30), CARD_TZ)):
        raise ValueError('CAPTURE_OUTSIDE_INFORMATION_CUTOFF')
    payload = base64.b64decode(receipt['raw_base64'], validate=True)
    if not payload or len(payload) > MAX_BYTES or sha(payload) != receipt['source_raw_sha256']:
        raise ValueError('SOURCE_RAW_SHA_MISMATCH')
    proof = {key: value for key, value in receipt.items() if key != 'raw_base64'}
    proof.update(parser_version=PARSER, receipt_sha256=env['receipt_sha256'],
                 receipt_path=str(path.relative_to(root)), origin_authentication='OFFICIAL_HTTPS_CAPTURE_UNSIGNED')
    return json.loads(payload), proof


def roc_date(value):
    match = re.fullmatch(r'(\d{3})(?:/|年)?(\d{2})(?:/|月)?(\d{2})日?', value)
    if not match:
        raise ValueError('INVALID_OFFICIAL_DATE')
    y, m, d = map(int, match.groups())
    return date(y+1911, m, d)


def number(value):
    try:
        result = Decimal(value.replace(',', ''))
    except InvalidOperation as exc:
        raise ValueError('INVALID_INDEX') from exc
    if not result.is_finite() or result <= 0:
        raise ValueError('INVALID_INDEX')
    return result


def table(payload, fields):
    if payload['stat'] != 'OK' or payload['fields'][:len(fields)] != fields:
        raise ValueError('UNEXPECTED_TWSE_TABLE')
    return payload['data']


def parse_taiex(payload, day):
    if not isinstance(payload, list):
        raise ValueError('UNEXPECTED_TAIEX_TABLE')
    selected = [row for row in payload if roc_date(row['Date']) == day]
    if len(selected) != 1:
        raise ValueError('TAIEX_SESSION_MISSING_OR_DUPLICATE')
    opening, high, low, close = (number(selected[0][k]) for k in (
        'OpeningIndex','HighestIndex','LowestIndex','ClosingIndex'))
    if not low <= min(opening, close) <= max(opening, close) <= high:
        raise ValueError('TAIEX_OHLC_INCONSISTENT')
    return {'status':'VERIFIED_SHADOW', 'open':str(opening), 'close':str(close)}


def event_time(day, value):
    if not re.fullmatch(r'[0-9]{6}', value):
        raise ValueError('INVALID_EVENT_TIME')
    clock = time(int(value[:2]), int(value[2:4]), int(value[4:]))
    return datetime.combine(roc_date(day), clock, CARD_TZ)


def parse_halts(payload, day):
    if not isinstance(payload, list):
        raise ValueError('UNEXPECTED_HALT_TABLE')
    start, end = (datetime.combine(day, t, CARD_TZ) for t in (time(9), time(13,30)))
    halts = {}
    for row in payload:
        halted = event_time(row['TradingHaltDate'], row['TradingHaltTime'])
        resume_date, resume_time = (row[k] for k in ('TradingResumptionDate', 'TradingResumptionTime'))
        missing = (None, '', '--', 'N/A')
        if (resume_date in missing) != (resume_time in missing):
            raise ValueError('HALT_RESUMPTION_FIELDS_INCOMPLETE')
        resumed = event_time(resume_date, resume_time) if resume_date not in missing else None
        if resumed and resumed <= halted:
            raise ValueError('HALT_INTERVAL_INCONSISTENT')
        if halted <= end and (resumed is None or resumed > start):
            halts.setdefault(row['Code'], []).append({
                'halted_at_taipei':halted.isoformat(),
                'resumed_at_taipei':resumed.isoformat() if resumed else None,
                'spans_session_open':halted <= start,
                'spans_session_close':resumed >= end if resumed else None,
                'resumed_during_session':resumed is not None and start < resumed < end,
            })
    return halts


def parse_delistings(payload, day):
    if not isinstance(payload, list):
        raise ValueError('UNEXPECTED_DELISTING_TABLE')
    result = {}
    for row in payload:
        effective = roc_date(row['DelistingDate'])
        if effective <= day:
            result[row['Code']] = max(result.get(row['Code'], effective), effective)
    return result


def parse_actions(payload, day):
    if payload['strDate'] != day.strftime('%Y%m%d') or payload['endDate'] != payload['strDate']:
        raise ValueError('CORPORATE_ACTION_RANGE_MISMATCH')
    rows = table(payload, ['資料日期','股票代號','股票名稱','除權息前收盤價','除權息參考價','權值+息值','權/息'])
    events = {}
    for row in rows:
        if roc_date(row[0]) != day:
            raise ValueError('CORPORATE_ACTION_ROW_DATE_MISMATCH')
        events.setdefault(row[1], []).append({'effective_date':day.isoformat(),
            'event_type':row[6], 'prior_close':row[3], 'reference_price':row[4], 'adjustment':row[5]})
    return events


PARSERS = {'taiex':parse_taiex,'halts':parse_halts,'delistings':parse_delistings,'corporate_actions':parse_actions}


def trading_status(row, halts, delisted):
    try:
        trades = int(row.get('Trades') or 0)
    except ValueError:
        trades = 0
    if delisted:
        # A post-effective trade can be a relisting, code reuse or evidence conflict.
        return {'status':'UNVERIFIED' if trades > 0 else 'DELISTED',
                'delisting_effective_date':delisted.isoformat(),
                'reason':'POST_DELISTING_TRADE_CONFLICT' if trades > 0 else 'TWSE_EFFECTIVE_DELISTING'}
    if halts:
        opening = 'HALTED_AT_OPEN' if any(h['spans_session_open'] for h in halts) else 'UNVERIFIED'
        evidence = {'opening_status': opening, 'intervals': halts}
        if any(h['spans_session_open'] and h['spans_session_close'] is True for h in halts):
            if trades > 0:
                return {'status':'UNVERIFIED','reason':'FULL_SESSION_HALT_WITH_OBSERVED_TRADES',
                        **evidence, 'opening_status':'UNVERIFIED'}
            return {'status':'FULL_SESSION_HALT', **evidence}
        if any(h['resumed_during_session'] for h in halts):
            return {'status':'HALT_RESUMED_DURING_SESSION', **evidence}
        if any(h['resumed_at_taipei'] is None for h in halts):
            return {'status':'UNVERIFIED','reason':'HALT_END_UNVERIFIED', **evidence}
        return {'status':'PARTIAL_SESSION_HALT', **evidence}
    return {'status':'UNVERIFIED', 'opening_status':'UNVERIFIED',
            'observation': 'TRADE_OBSERVED' if trades > 0 else 'NO_EXECUTION_EVIDENCE',
            'reason':'COMPLETE_OPEN_TIME_TRADEABILITY_NOT_ESTABLISHED'}


def build(root, captures, day, cutoff):
    calendar, _, calendar_sha = load_manifest()
    if not is_trading_day(day, calendar) or day > cutoff.date() or cutoff > datetime.now(CARD_TZ):
        raise ValueError('INVALID_MARKET_DAY_OR_CUTOFF')
    rows, eod = card_eod_leg(root, day.isoformat(), 'price', cutoff)
    if eod['status'] != 'VERIFIED':
        raise ValueError('VERIFIED_EOD_UNIVERSE_REQUIRED:'+eod.get('reason',''))
    sources, data = {}, {}
    for kind, url in source_urls(day).items():
        proof = {'source_url':url}
        try:
            raw, proof = open_capture(captures, kind, day, url, cutoff)
            data[kind] = PARSERS[kind](raw, day)
            sources[kind] = {**proof, 'status':'VERIFIED_SHADOW'}
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            sources[kind] = {**proof, 'status':BLOCKED, 'reason':str(exc)}
    halts, delistings, events = (data.get(kind, {}) for kind in ('halts','delistings','corporate_actions'))
    stocks = {}
    for ticker, row in sorted(rows.items()):
        stocks[ticker] = {
            'trading':trading_status(row, halts.get(ticker), delistings.get(ticker)),
            'corporate_action':{'status':'ACTION','events':events[ticker]} if ticker in events else
                {'status':'UNVERIFIED','reason':'TWT49U_ABSENCE_CANNOT_PROVE_NO_CORPORATE_ACTION'},
        }
    return {
        'schema': SCHEMA, 'formal_schema_not_emitted':OFFICIAL, 'formal_settlement_allowed':False,
        'mode':'HISTORICAL_REPLAY' if day < cutoff.date() else 'SHADOW_ONLY',
        'market_date':day.isoformat(), 'evidence_cutoff_taipei':cutoff.isoformat(),
        'sources':sources, 'parser_version':PARSER, 'calendar_sha256':calendar_sha, 'eod_universe':eod,
        'taiex':data.get('taiex', {'status':BLOCKED}), 'stocks':stocks,
        'dataset_status': {
            'taiex': 'VERIFIED_SHADOW' if 'taiex' in data else BLOCKED,
            **{kind: BLOCKED if not stocks or any(stock[kind]['status']=='UNVERIFIED' for stock in stocks.values())
               else 'VERIFIED_SHADOW' for kind in ('trading','corporate_action')},
        },
        'coverage':{'universe':len(stocks), 'taiex':int('taiex' in data),
                    'trade_observed':sum(stock['trading'].get('observation')=='TRADE_OBSERVED'
                                         for stock in stocks.values()),
                    **{kind:dict(Counter(stock[kind]['status'] for stock in stocks.values()))
                       for kind in ('trading','corporate_action')}},
        'official_examples':{
            'halts_during_session':dict(list(sorted(halts.items()))[:5]),
            'most_recent_delisting':[(ticker, d.isoformat()) for ticker, d in sorted(
                delistings.items(), key=lambda item:(item[1], item[0]), reverse=True)[:1]],
            'corporate_action_rows':dict(list(sorted(events.items()))[:3]),
            'corporate_action_rows_total':sum(map(len, events.values())),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--market-date', type=date.fromisoformat, required=True)
    parser.add_argument('--capture', action='store_true', help='at most one request per missing official source')
    parser.add_argument('--asof', help='offline evaluation cutoff only; cannot set capture time')
    args = parser.parse_args()
    if args.capture and args.asof:
        parser.error('capture time is recorded by the receiver; use --asof only for offline verification')
    if args.capture:
        market_day = args.market_date
        now = datetime.now(CARD_TZ)
        calendar, _, _ = load_manifest()
        if not is_trading_day(market_day, calendar) or now < datetime.combine(market_day,time(13,30),CARD_TZ):
            parser.error('capture requires a completed official trading session')
        _, proof = card_eod_leg(args.root, market_day.isoformat(), 'price', now)
        if proof['status'] != 'VERIFIED':
            parser.error('capture requires verified original EOD')
        for kind, url in source_urls(market_day).items():
            try:
                capture(args.evidence_dir, kind, market_day, url)
            except (OSError, URLError, ValueError) as exc:
                print(f'{kind}: {BLOCKED}: {exc}', file=sys.stderr)
    cutoff = card_time(args.asof) if args.asof else datetime.now(CARD_TZ)
    print(canonical(build(args.root, args.evidence_dir, args.market_date, cutoff)).decode())


if __name__ == '__main__':
    main()
