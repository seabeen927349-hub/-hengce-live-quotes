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
        self.assertEqual(trading_status({'Trades':'1'},interval,None)['status'], 'HALT_RESUMED_DURING_SESSION')
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


class OfficialExcerptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Path(__file__).parent/'fixtures/twse_reference_20261117_excerpt.json'
        cls.sources = json.loads(fixture.read_bytes())['sources']

    def test_taiex_actual_fields_date_and_values(self):
        sample = self.sources['taiex']
        self.assertEqual(sample['source_url'], source_urls(DAY)['taiex'])
        self.assertEqual(sample['response'][0]['Date'], '1151117')
        observed = parse_taiex(sample['response'], DAY)
        self.assertEqual((observed['open'], observed['close']), ('40546.64', '40092.11'))

    def test_twta_wu_real_halt_and_resume_interval(self):
        sample = self.sources['halts']
        self.assertEqual(sample['source_url'], source_urls(DAY)['halts'])
        self.assertEqual(parse_halts(sample['response'], DAY), {})
        interval = parse_halts(sample['response'], date(2026,11,10))['2314']
        self.assertEqual(interval[0]['halted_at_taipei'], '2026-11-10T08:00:00+08:00')
        self.assertEqual(interval[0]['resumed_at_taipei'], '2026-11-11T08:00:00+08:00')
        self.assertEqual(trading_status({'Trades':'0'},interval,None)['status'], 'FULL_SESSION_HALT')

    def test_delisting_real_date_and_ticker(self):
        sample = self.sources['delistings']
        self.assertEqual(sample['source_url'], source_urls(DAY)['delistings'])
        self.assertEqual(parse_delistings(sample['response'], DAY)['2867'], date(2026,9,1))
        self.assertNotIn('2867', parse_delistings(sample['response'], date(2026,8,31)))

    def test_twt49u_actual_request_response_fields_and_missing_value(self):
        from urllib.parse import parse_qs, urlsplit

        sample = self.sources['corporate_actions']
        self.assertEqual(sample['source_url'], source_urls(DAY)['corporate_actions'])
        self.assertEqual(parse_qs(urlsplit(sample['source_url']).query),
                         {'startDate':['20261117'], 'endDate':['20261117'], 'response':['json']})
        response = sample['response']
        self.assertEqual((response['strDate'], response['endDate']), ('20261117', '20261117'))
        self.assertEqual(response['data'][0][0], '115年11月17日')
        self.assertEqual(response['data'][0][-1], 'N/A')
        result = parse_actions(response, DAY)
        self.assertEqual(result['006208'][0]['adjustment'], '3.880000')
        self.assertNotIn('2610', result)
        with self.assertRaisesRegex(ValueError, 'RANGE_MISMATCH'):
            parse_actions({**response,'endDate':'20261118'}, DAY)
        with self.assertRaisesRegex(ValueError, 'RANGE_MISMATCH'):
            parse_actions({**response,'strDate':'20261116'}, DAY)


class TradingClassificationTests(unittest.TestCase):
    def statuses(self, start, resume_date, resume_time, trades='0'):
        raw = [{'Code':'1234','TradingHaltDate':'1151117','TradingHaltTime':start,
                'TradingResumptionDate':resume_date,'TradingResumptionTime':resume_time}]
        interval = parse_halts(raw, DAY)['1234']
        return trading_status({'Trades':trades},interval,None)

    def test_intraday_halt_then_resume_leaves_opening_unverified(self):
        status = self.statuses('101500','1151117','111500','12')
        self.assertEqual(status['status'], 'HALT_RESUMED_DURING_SESSION')
        self.assertEqual(status['opening_status'], 'UNVERIFIED')
        opened = self.statuses('080000','1151117','103000','12')
        self.assertEqual(opened['status'], 'HALT_RESUMED_DURING_SESSION')
        self.assertEqual(opened['opening_status'], 'HALTED_AT_OPEN')

    def test_missing_resume_and_conflicting_trades_do_not_prove_full_halt(self):
        for missing in (None, '', '--', 'N/A'):
            state = self.statuses('080000',missing,missing)
            self.assertEqual(state['status'], 'UNVERIFIED')
            self.assertEqual(state['reason'], 'HALT_END_UNVERIFIED')
        with self.assertRaisesRegex(ValueError, 'FIELDS_INCOMPLETE'):
            self.statuses('080000',None,'103000')
        conflict = self.statuses('080000','1151118','080000','2')
        self.assertEqual(conflict['status'], 'UNVERIFIED')
        self.assertEqual(conflict['opening_status'], 'UNVERIFIED')
