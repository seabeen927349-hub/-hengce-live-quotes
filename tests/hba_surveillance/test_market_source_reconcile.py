import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from hengce_hba_context_bridge_v1 import card_time
from hengce_hba_research_ledger import canonical, sha
from hengce_hba_market_source_reconcile import (FINMIND_FILES, FUGLE_SCHEMA, METRIC_SHA, finmind_context,
                                                fugle_context, reconcile_quote, report)

DAY = date(2026,11,17)
READ = card_time('2026-11-18T17:00:00+08:00')
STAMP = '2026-11-17T13:30:00+08:00'


def quote():
    return {'ticker':'2610','last_trade_at_taipei':STAMP,'close_time_taipei':STAMP,
            'vendor_updated_at_taipei':STAMP,'trade_semantics':'SESSION_CLOSING_AUCTION_CONFIRMED',
            'source':'Fugle Stock','source_exchange':'TWSE','quote_market_date':'2026-11-17',
            'vendor_is_close':True,'last_price_twd':23.1,'close_price_twd':23.1,
            'open_twd':22.8,'high_twd':23.1,'low_twd':22.15,'volume_lots':5}


def eod_quote():
    return {'Open':'22.80','High':'23.10','Low':'22.15','Close':'23.10','VolumeShares':'5001'}


def packet(rows):
    return canonical({'schema':FUGLE_SCHEMA,'source':'Fugle Stock','generated_at_taipei':STAMP,
                      'authority':'RESEARCH_QUOTE_ONLY_NO_RANKING_OR_TRADING','quote_market_date':'2026-11-17',
                      'quotation_status':'VERIFIED_CLOSED_SESSION_QUOTE_NOT_FORMAL_MOTHER_EOD','quotes':rows})


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        fields = {'generated_at_taipei':'2026-11-17T13:05:17+08:00',
                  'latest_source_timestamp':'2026-11-17 13:05:10.785974',
                  'metric_contract_sha256':METRIC_SHA,'finmind_metric_observation_count':1084,
                  'metric_unknown_count':4,'active_required_count':1088,'trading_authority':False}
        ctx = {**fields,'schema':'HENGCE_ESCAPE_FINMIND_TWSE_COMMON_AGGREGATE_SHADOW_V3',
               'market_date':'2026-11-17','per_security_rows_persisted':False,
               'raw_finmind_rows_persisted':False, 'market':{'return_observed_count':1084,
                   'advance_count':198,'decline_count':831,'flat_count':55}}
        ctx['payload_sha256'] = sha(canonical(ctx))
        status = {**fields,'source':'FinMind','state':'SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY',
                  'context_payload_sha256':ctx['payload_sha256'],'active_universe_transport_full_coverage':True,
                  'healthy_transport':True,'source_binding_promotion_authority':False,'formal_eod_authority':False}
        monitor = {**fields,'source':'FinMind taiwan_stock_tick_snapshot',
                   'market_date':'2026-11-17','canonical_eod_legs_replaced':False}
        monitor['payload_sha256'] = sha(canonical(monitor))
        for path, obj in zip(FINMIND_FILES,(ctx,status,monitor)):
            f = self.root/path
            f.parent.mkdir(exist_ok=True)
            f.write_bytes(canonical(obj))

    def test_finmind_triplet_keeps_vendor_denominator(self):
        result = finmind_context(self.root, DAY, READ)
        self.assertEqual(result['status'],'VERIFIED_AGGREGATE_SHADOW')
        self.assertEqual((result['source_scope_valid'],result['source_scope_total']), (1084,1088))
        self.assertEqual(result['matched_per_ticker_rows'],0)
        self.assertIsNone(result['first_vendor_receipt_taipei'])

    def test_finmind_wrong_cutoff_and_modified_hash_fail_closed(self):
        earlier = card_time('2026-11-17T13:05:11+08:00')
        self.assertEqual(finmind_context(self.root,DAY,earlier)['status'],'UNVERIFIED')
        self.assertEqual(finmind_context(self.root,date(2026,11,18),READ)['status'],'UNVERIFIED')
        path = self.root/FINMIND_FILES[0]
        data = json.loads(path.read_bytes())
        data['metric_unknown_count'] += 1
        path.write_bytes(canonical(data))
        self.assertEqual(finmind_context(self.root,DAY,READ)['status'],'UNVERIFIED')

    def test_fugle_receipt_hash_duplicate_and_late_read(self):
        raw = packet([quote()])
        quotes, info = fugle_context(raw,sha(raw),DAY,READ,READ)
        self.assertIn('2610', quotes)
        self.assertIsNone(info['first_vendor_receipt_taipei'])
        self.assertEqual(fugle_context(raw,'0'*64,DAY,READ,READ)[1]['status'],'UNVERIFIED')
        self.assertEqual(fugle_context(raw,sha(raw),DAY,READ,card_time(STAMP))[1]['status'],'UNVERIFIED')
        dup = packet([quote(),quote()])
        self.assertEqual(fugle_context(dup,sha(dup),DAY,READ,READ)[1]['reason'],'DUPLICATE_FUGLE_TICKER')

    def test_compare_only_same_session_confirmed_closing_prices(self):
        row = quote()
        self.assertEqual(reconcile_quote(eod_quote(),row,DAY,READ)['status'],'VERIFIED_SHADOW')
        row['open_twd'] = 22.9
        self.assertEqual(reconcile_quote(eod_quote(),row,DAY,READ)['different_fields'],['Open'])
        self.assertEqual(reconcile_quote(eod_quote(),row,DAY,READ)['status'],'CONFLICT')
        row['vendor_is_close'] = False
        self.assertEqual(reconcile_quote(eod_quote(),row,DAY,READ)['status'],'UNVERIFIED')
        self.assertEqual(reconcile_quote(eod_quote(),None,DAY,READ)['status'],'MISSING')

    def test_output_preserves_unknown_opening_and_rejects_mismatched_hba_universe(self):
        label = DAY.isoformat()
        proof = {'status':'VERIFIED','sha256':'a','mother_sha256':'b','available_at':STAMP}
        manifest = {'market_date':label,'evidence_cutoff_taipei':STAMP,
                    'provenance':{'eod':{label:{'price':proof}}}}
        card = {'ticker':'2610'}
        refs = {'stocks':{'2610':{'trading':{'status':'UNVERIFIED','opening_status':'UNVERIFIED',
                                            'observation':'TRADE_OBSERVED'},
                                  'corporate_action':{'status':'UNVERIFIED'}}},'sources':{}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'manifest.json').write_bytes(canonical(manifest))
            with patch('hengce_hba_market_source_reconcile.read_research_cards',
                       return_value=(manifest,{'2610':card})), patch('hengce_hba_market_source_reconcile.official_reference',
                       return_value=refs), patch('hengce_hba_market_source_reconcile.card_eod_leg') as eod:
                eod.return_value = ({'2610':eod_quote()}, proof)
                raw = packet([quote()])
                result = report(root,root,root,READ,raw,sha(raw),READ)
                self.assertEqual(result['stocks']['2610']['research_card_sha256'],sha(canonical(card)))
                self.assertEqual(result['stocks']['2610']['trading']['opening_status'],'UNVERIFIED')
                self.assertFalse(result['formal_settlement_allowed'])
                self.assertNotIn('last_price_twd',json.dumps(result))
                eod.return_value = ({'9933':eod_quote()}, proof)
                with self.assertRaisesRegex(ValueError,'UNIVERSE_MISMATCH'):
                    report(root,root,root,READ)
