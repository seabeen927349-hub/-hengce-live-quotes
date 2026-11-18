"""Read existing market observations, bind them to HBA cards, and reconcile in shadow."""
import argparse
import json
from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from hengce_hba_context_bridge_v1 import CARD_TZ, card_eod_leg, card_time
from hengce_hba_decision_report import read_research_cards
from hengce_hba_research_ledger import canonical, sha
from hengce_hba_twse_reference_shadow import build as official_reference

FINMIND_FILES = (
    'escape_live/finmind_twse_common_context.json',
    'escape_live/finmind_twse_common_status.json',
    'escape_live/intraday_monitor.json',
)
METRIC_SHA = '1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281'
FUGLE_SCHEMA = 'HENGCE_FUGLE_VERIFIED_QUOTE_OBSERVATION_V1'
PRICE_FIELDS = {'Open':'open_twd', 'High':'high_twd', 'Low':'low_twd', 'Close':'close_price_twd'}


def price(value):
    try:
        parsed = Decimal(str(value).replace(',', ''))
        return parsed if parsed.is_finite() and parsed > 0 else None
    except InvalidOperation:
        return None


def payload_sha(obj):
    return sha(canonical({k:v for k,v in obj.items() if k!='payload_sha256'}))


def finmind_context(root, day, cutoff, *, read_clock=None):
    hashes = {}
    try:
        documents = []
        for name in FINMIND_FILES:
            raw = (root/name).read_bytes()
            hashes[name] = sha(raw)
            documents.append(json.loads(raw))
        # Producer generated_at is initialized before the vendor request.
        # This run's completed read is the first availability we can assert here.
        read_at = (read_clock or (lambda: datetime.now(CARD_TZ)))()
        ctx, status, monitor = documents
        if (ctx['schema'] != 'HENGCE_ESCAPE_FINMIND_TWSE_COMMON_AGGREGATE_SHADOW_V3'
                or status['source'] != 'FinMind'
                or status['state'] != 'SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY'
                or monitor['source'] != 'FinMind taiwan_stock_tick_snapshot'
                or ctx['payload_sha256'] != payload_sha(ctx)
                or monitor['payload_sha256'] != payload_sha(monitor)
                or status['context_payload_sha256'] != ctx['payload_sha256']
                or any(d['metric_contract_sha256'] != METRIC_SHA for d in documents)
                or any(d['trading_authority'] is not False for d in documents)
                or status['active_universe_transport_full_coverage'] is not True
                or status['healthy_transport'] is not True
                or status['source_binding_promotion_authority'] is not False
                or status['formal_eod_authority'] is not False
                or monitor['canonical_eod_legs_replaced'] is not False
                or ctx['per_security_rows_persisted'] is not False
                or ctx['raw_finmind_rows_persisted'] is not False):
            raise ValueError('FINMIND_PROVENANCE_OR_AUTHORITY')
        fields = ('generated_at_taipei','latest_source_timestamp','finmind_metric_observation_count',
                  'metric_unknown_count','active_required_count')
        if any(len({d[key] for d in documents}) != 1 for key in fields):
            raise ValueError('FINMIND_SOURCE_BINDING_MISMATCH')
        available = card_time(ctx['generated_at_taipei'])
        observed = datetime.fromisoformat(ctx['latest_source_timestamp'])
        observed = observed.replace(tzinfo=CARD_TZ) if observed.tzinfo is None else observed.astimezone(CARD_TZ)
        if not (ctx['market_date'] == monitor['market_date'] == day.isoformat()
                and observed.date() == available.date() == day and max(observed, available) <= read_at
                and (cutoff is None or read_at <= cutoff)):
            raise ValueError('FINMIND_WRONG_SESSION_OR_CUTOFF')
        valid, unknown, total = (ctx[k] for k in fields[2:])
        market = ctx['market']
        if (any(type(n) is not int or n < 0 for n in (valid, unknown, total))
                or valid+unknown != total or market['return_observed_count'] != valid
                or sum(market[k] for k in ('advance_count','decline_count','flat_count')) != valid):
            raise ValueError('FINMIND_COVERAGE_MISMATCH')
        return {'status':'VERIFIED_AGGREGATE_SHADOW','contract_sha256':METRIC_SHA,
                'input_sha256':hashes, 'source_schema':ctx['schema'],
                'latest_market_observation_taipei':observed.isoformat(),
                'existing_run_started_at_taipei':available.isoformat(), 'read_at_taipei':read_at.isoformat(),
                'first_vendor_receipt_taipei':None,
                'source_scope_valid':valid,'source_scope_unknown':unknown,'source_scope_total':total,
                'matched_per_ticker_rows':0, 'per_ticker_reason':'AGGREGATE_ONLY_NO_RETAINED_VENDOR_ROWS'}
    except FileNotFoundError:
        return {'status':'MISSING','input_sha256':hashes}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {'status':'UNVERIFIED','input_sha256':hashes,'reason':str(exc)}


def fugle_context(raw, expected_sha, day, read_at, cutoff):
    if raw is None:
        return {}, {'status':'MISSING','reason':'PRIVATE_OBSERVATION_NOT_SUPPLIED'}
    meta = {'input_sha256':sha(raw), 'read_at_taipei':read_at.isoformat(),
            'first_vendor_receipt_taipei':None, 'role':'HISTORICAL_SHADOW_ONLY'}
    try:
        if meta['input_sha256'] != expected_sha:
            raise ValueError('FUGLE_SHA_MISMATCH')
        packet = json.loads(raw)
        if (packet['schema'] != FUGLE_SCHEMA or packet['source'] != 'Fugle Stock'
                or packet['authority'] != 'RESEARCH_QUOTE_ONLY_NO_RANKING_OR_TRADING'
                or packet['quote_market_date'] != day.isoformat()
                or packet['quotation_status'] != 'VERIFIED_CLOSED_SESSION_QUOTE_NOT_FORMAL_MOTHER_EOD'):
            raise ValueError('FUGLE_SCHEMA_SCOPE_OR_DAY')
        stamped = card_time(packet['generated_at_taipei'])
        if stamped.date() != day or not stamped <= read_at <= cutoff:
            raise ValueError('FUGLE_AVAILABILITY_UNPROVEN_AT_CUTOFF')
        rows = {}
        for row in packet['quotes']:
            ticker = row['ticker']
            if ticker in rows:
                raise ValueError('DUPLICATE_FUGLE_TICKER')
            rows[ticker] = row
        return rows, {**meta,'status':'VERIFIED_RECEIPT_SHADOW','source_schema':packet['schema'],
                      'receipt_market_timestamp_taipei':stamped.isoformat(),'source_rows':len(rows)}
    except (ValueError, TypeError, KeyError) as exc:
        return {}, {**meta,'status':'UNVERIFIED','reason':str(exc)}


def reconcile_quote(eod, row, day, cutoff):
    if row is None:
        return {'status':'MISSING'}
    try:
        stamp = card_time(row['last_trade_at_taipei'])
        close = card_time(row['close_time_taipei'])
        updated = card_time(row['vendor_updated_at_taipei'])
        when = stamp.time()
        if (row['source_exchange'] != 'TWSE' or row['quote_market_date'] != day.isoformat()
                or row['source'] != 'Fugle Stock' or row['vendor_is_close'] is not True
                or row['trade_semantics'] != 'SESSION_CLOSING_AUCTION_CONFIRMED'
                or stamp.date() != day or close != stamp or not time(13,30) <= when <= time(13,32)
                or updated.date() != day or not stamp <= updated <= cutoff
                or price(row['last_price_twd']) != price(row['close_price_twd'])):
            raise ValueError('NOT_COMPARABLE_CLOSING_OBSERVATION')
        pairs = {key:(price(eod.get(key)), price(row.get(v))) for key,v in PRICE_FIELDS.items()}
        if any(None in pair for pair in pairs.values()):
            raise ValueError('OHLC_MISSING_OR_INVALID')
        differences = [k for k,(official,vendor) in pairs.items() if official != vendor]
        # Do not republish vendor prices or volumes. Report comparison field names only.
        return {'status':'CONFLICT' if differences else 'VERIFIED_SHADOW',
                'different_fields':differences, 'market_observation_taipei':stamp.isoformat()}
    except (ValueError, TypeError, KeyError) as exc:
        return {'status':'UNVERIFIED','reason':str(exc)}


def report(root, cards_dir, evidence_dir, cutoff, fugle_raw=None, fugle_sha=None, fugle_read_at=None):
    manifest, cards = read_research_cards(cards_dir)
    day = date.fromisoformat(manifest['market_date'])
    finmind = finmind_context(root, day, cutoff)
    cutoff = cutoff or datetime.now(CARD_TZ)
    if card_time(manifest['evidence_cutoff_taipei']) > cutoff:
        raise ValueError('RESEARCH_CARDS_AFTER_CUTOFF')
    eod, proof = card_eod_leg(root, day.isoformat(), 'price', cutoff)
    if proof['status'] != 'VERIFIED' or set(eod) != set(cards):
        raise ValueError('HBA_AND_ORIGINAL_EOD_UNIVERSE_MISMATCH')
    original = manifest['provenance']['eod'][day.isoformat()]['price']
    if any(original[k]!=proof[k] for k in ('sha256','mother_sha256','available_at')):
        raise ValueError('HBA_AND_ORIGINAL_EOD_PROVENANCE_MISMATCH')
    twse = official_reference(root, evidence_dir, day, cutoff)
    quotes, fugle = fugle_context(fugle_raw, fugle_sha, day, fugle_read_at, cutoff)
    stocks = {}
    for ticker, card in sorted(cards.items()):
        ref = twse['stocks'][ticker]
        quote = reconcile_quote(eod[ticker], quotes.get(ticker), day, cutoff)
        if not quotes and fugle['status']=='UNVERIFIED':
            quote = {'status':'UNVERIFIED','reason':'SOURCE_RECEIPT_REJECTED'}
        stocks[ticker] = {'research_card_sha256':sha(canonical(card)),
                          'twse_close':'VERIFIED' if price(eod[ticker].get('Close')) else 'MISSING',
                          'fugle_close_comparison':quote,
                          'finmind_per_ticker':'UNVERIFIED',
                          'trading':ref['trading'], 'corporate_action':ref['corporate_action']}
    return {'schema':'HENGCE_MARKET_SOURCE_RECONCILIATION_SHADOW_V1','market_date':day.isoformat(),
            'evidence_cutoff_taipei':cutoff.isoformat(),'mode':'HISTORICAL_REPLAY' if day<cutoff.date() else 'SHADOW_ONLY',
            'formal_settlement_allowed':False,'trading_authority':False,
            'hba_manifest_sha256':sha((cards_dir/'manifest.json').read_bytes()),
            'twse_price_proof':proof,'twse_reference_proofs':twse['sources'],'finmind':finmind,'fugle':fugle,
            'coverage':{'universe':len(stocks),'fugle_outside_universe':len(set(quotes)-stocks.keys()),
                        **{name:dict(Counter(extract(x) for x in stocks.values()))
                           for name,extract in (
                               ('twse_close',lambda x:x['twse_close']),
                               ('fugle_close_comparison',lambda x:x['fugle_close_comparison']['status']),
                               ('finmind_per_ticker',lambda x:x['finmind_per_ticker']),
                               ('trading',lambda x:x['trading']['status']),
                               ('corporate_action',lambda x:x['corporate_action']['status']))}},
            'stocks':stocks}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--cards', required=True, type=Path)
    p.add_argument('--twse-evidence', required=True, type=Path)
    p.add_argument('--fugle', type=Path, help='private existing closing observation JSON')
    p.add_argument('--fugle-sha', help='SHA-256 verified separately from the pinned private file')
    p.add_argument('--asof', help='optional earlier evidence cutoff')
    args = p.parse_args()
    if bool(args.fugle) != bool(args.fugle_sha):
        p.error('--fugle and --fugle-sha must be provided together')
    raw = args.fugle.read_bytes() if args.fugle else None
    read_at = datetime.now(CARD_TZ)
    cutoff = card_time(args.asof) if args.asof else None
    print(canonical(report(args.root,args.cards,args.twse_evidence,cutoff,raw,args.fugle_sha,read_at)).decode())


if __name__=='__main__':
    main()
