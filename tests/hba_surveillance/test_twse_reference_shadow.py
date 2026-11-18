import base64
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from hengce_hba_context_bridge_v1 import card_time
from hengce_hba_research_ledger import canonical, sha
from hengce_hba_research_reference import official_sessions
from hengce_hba_twse_reference_shadow import (
    BLOCKED, build, capture, open_capture, parse_actions, parse_delistings,
    parse_halts, parse_taiex, source_urls, trading_status,
)

DAY = date(2026,11,17)


class ShadowTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.url = source_urls(DAY)['taiex']
        self.late = card_time('2026-11-18T11:00:00+08:00')
        self.cutoff = card_time('2026-11-18T12:00:00+08:00')
        self.payload = [{'Date':'1151117', 'OpeningIndex':'20,000.00', 'HighestIndex':'21,000.00',
                         'LowestIndex':'19,900.00', 'ClosingIndex':'20,500.00'}]

    def make(self):
        with patch('hengce_hba_twse_reference_shadow.fetch', return_value=(canonical(self.payload),self.late)):
            return capture(self.root, 'taiex', DAY, self.url)

    def test_verified_original_bytes_and_values(self):
        path = self.make()
        raw, proof = open_capture(self.root, 'taiex', DAY, self.url, self.cutoff)
        self.assertEqual(proof['source_raw_sha256'], sha(canonical(self.payload)))
        self.assertEqual(base64.b64decode(json.loads(path.read_bytes())['receipt']['raw_base64']), canonical(raw))
        self.assertEqual(parse_taiex(raw, DAY)['close'], '20500.00')
        self.assertIsNone(proof['announced_at_taipei'])
        self.assertEqual(proof['first_observed_at_taipei'], self.late.isoformat())

    def test_first_capture_idempotent_and_no_backfill(self):
        first = self.make().read_bytes()
        with patch('hengce_hba_twse_reference_shadow.fetch') as fetch:
            self.assertEqual(capture(self.root,'taiex',DAY,self.url).read_bytes(), first)
            fetch.assert_not_called()
        with self.assertRaisesRegex(ValueError,'INFORMATION_CUTOFF'):
            open_capture(self.root,'taiex',DAY,self.url,card_time('2026-11-17T23:59:00+08:00'))

    def test_mutated_raw_and_unapproved_url_blocked(self):
        path = self.make()
        receipt = json.loads(path.read_bytes())['receipt']
        receipt['raw_base64'] = 'e30='
        path.write_bytes(canonical({'receipt':receipt, 'receipt_sha256':sha(canonical(receipt))}))
        with self.assertRaisesRegex(ValueError,'SOURCE_RAW_SHA'):
            open_capture(self.root,'taiex',DAY,self.url,self.cutoff)
        with self.assertRaisesRegex(ValueError,'UNAPPROVED_SOURCE'):
            open_capture(self.root,'taiex',DAY,'https://www.twse.com.tw/other',self.cutoff)

    def test_ambiguous_index_session_rejected(self):
        self.payload *= 2
        with self.assertRaisesRegex(ValueError,'MISSING_OR_DUPLICATE'):
            parse_taiex(self.payload, DAY)

    def test_halt_delisting_and_zero_volume_are_distinct(self):
        payload = [{'Code':'1234', 'TradingHaltDate':'1151117','TradingHaltTime':'080000',
                   'TradingResumptionDate':'1151117','TradingResumptionTime':'103000'}]
        interval = parse_halts(payload,DAY)['1234']
        self.assertTrue(interval[0]['spans_session_open'])
        self.assertEqual(trading_status({'Trades':'1'},interval,None)['status'], 'HALTED')
        self.assertEqual(trading_status({'Trades':'0'},None,None)['status'], 'UNVERIFIED')
        self.assertEqual(trading_status({'Trades':'1'},None,None)['observation'], 'TRADE_OBSERVED')
        delisted = parse_delistings([{'Code':'1234','DelistingDate':'115/11/17'}],DAY)['1234']
        self.assertEqual(trading_status({},None,delisted)['status'], 'DELISTED')
        self.assertEqual(trading_status({'Trades':'1'},None,delisted)['status'], 'UNVERIFIED')

    def test_corporate_action_effective_date(self):
        payload = {'stat':'OK','strDate':'20261117','endDate':'20261117',
                   'fields':['資料日期','股票代號','股票名稱','除權息前收盤價','除權息參考價','權值+息值','權/息'],
                   'data':[['115年11月17日','2610','華航','25','24','1','息']]}
        self.assertEqual(parse_actions(payload,DAY)['2610'][0]['event_type'], '息')
        payload['data'][0][0] = '115年11月18日'
        with self.assertRaisesRegex(ValueError,'ROW_DATE'):
            parse_actions(payload,DAY)

    def test_missing_sources_and_unsigned_output_cannot_settle(self):
        with patch('hengce_hba_twse_reference_shadow.card_eod_leg',
                   return_value=({'2610':{'Trades':'1'}},{'status':'VERIFIED'})):
            result = build(self.root,self.root,DAY,self.cutoff)
        self.assertEqual(result['coverage']['universe'], 1)
        self.assertEqual(result['stocks']['2610']['corporate_action']['status'], 'UNVERIFIED')
        self.assertEqual(result['taiex']['status'], BLOCKED)
        with self.assertRaisesRegex(ValueError, 'OFFICIAL_REFERENCE_BUNDLE_REQUIRED'):
            official_sessions(result,self.cutoff,self.cutoff,{})
