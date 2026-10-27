"""Synthetic/offline data-quality and transport-retention contracts."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error

import evidence as e


class EvidenceContracts(unittest.TestCase):
    def fixture(self):
        return {'stat':'OK', 'strDate':'20250101', 'endDate':'20251231', 'title':'114年01月01日 至 114年12月31日 除權除息計算結果表',
                'fields':['資料日期','股票代號','股票名稱','除權息前收盤價','除權息參考價','權/息',
                          '最近一次申報資料 季別/日期','最近一次申報每股 (單位)盈餘'],
                'data':[['114年07月25日','6189','fixture','79.00','62.50','權息','115年第2季','2.01']]}

    def project(self, obj):
        return e.annual_projection(json.dumps(obj), 'TWT49U', 2025, {'2025-07-25':{'6189'}})

    def test_future_fundamentals_never_enter_historical_projection(self):
        obj = self.fixture()
        initial = self.project(obj)
        obj['data'][0][-2:] = ['999年第4季', '99999999.99']
        self.assertEqual(self.project(obj), initial)
        event = initial['events'][0]
        self.assertNotIn('2.01', json.dumps(event))
        self.assertIsNone(event['total_return_factor'])
        self.assertIsNone(event['share_adjustment_factor'])
        self.assertIsNone(event['original_first_seen_at'])
        self.assertFalse(event['adjusted_pnl_ready'])

    def test_no_current_membership_or_full_market_fallback(self):
        obj = self.fixture()
        obj['data'].append(['114年07月25日','0050','ETF','100','99','息','115年第2季','9'])
        self.assertEqual(len(self.project(obj)['events']), 1)
        self.assertEqual(e.annual_projection(json.dumps(obj),'TWT49U',2025,{})['events'], [])

    def test_http200_without_data_status_or_echo_never_passes(self):
        for key,value in [('stat','請稍後再試'),('strDate','20261023'),('endDate','20261023'),('title','115年')]:
            obj = self.fixture();obj[key]=value
            with self.assertRaises(ValueError): self.project(obj)

    def test_duplicate_event_rejected(self):
        obj=self.fixture();obj['data'].append(copy.deepcopy(obj['data'][0]))
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SOURCE_EVENT'):self.project(obj)

    def test_duplicate_missing_and_malformed_headers_rejected(self):
        for fields in (['股票代號','股票代號'], ['股票代號'], [None], [{}], None):
            obj=self.fixture();obj['fields']=fields
            with self.assertRaises(ValueError):self.project(obj)

    def test_row_width_and_invalid_effective_date_rejected(self):
        obj=self.fixture();obj['data'][0].pop()
        with self.assertRaises(ValueError):self.project(obj)
        for day in ('115年07月25日','114年02月30日','2025-07-25'):
            obj=self.fixture();obj['data'][0][0]=day
            with self.assertRaises(ValueError):self.project(obj)

    def test_invalid_prices_never_convert_to_zero_or_factor(self):
        for x in ('NaN','Inf','-1','0','--','除權息',None,True):
            obj=self.fixture();obj['data'][0][3]=x
            with self.assertRaises(ValueError):self.project(obj)

    def test_cash_reduction_is_separate_from_dividend(self):
        obj={'stat':'OK','strDate':'20250101','endDate':'20251231','title':'114年股票減資恢復買賣參考價格',
             'fields':['恢復買賣日期','股票代號','名稱','停止買賣前收盤價格','恢復買賣參考價','減資原因'],
             'data':[['114年07月25日','6189','fixture','100','190','退還股款']]}
        events=e.annual_projection(json.dumps(obj),'TWTAUU',2025,{'2025-07-25':{'6189'}})['events']
        self.assertEqual(events[0]['event_type_reported'],'退還股款')
        self.assertIsNone(events[0]['share_adjustment_factor'])

    def test_transport_failures_are_retained(self):
        task={'id':'synthetic','url':'https://example.invalid/fixture','kind':'PDF'}
        def fail(*a,**kw):raise OSError('synthetic offline transport fault')
        with tempfile.TemporaryDirectory() as td:
            record,raw=e.acquire(task,Path(td),opener=fail)
            self.assertEqual(record['transport'],'TRANSPORT_FAILURE_RETAINED')
            self.assertEqual(gzip.decompress((Path(td)/record['raw_path']).read_bytes()), b'')
            self.assertIsNone(record['original_first_seen_at'])
            self.assertIn('fetch_completed_at_utc',record)

    def test_http_error_body_retained_not_parsed_as_data(self):
        import io
        task={'id':'synthetic','url':'https://example.invalid/fixture','kind':'DETAIL'}
        def deny(*a,**kw):raise urllib.error.HTTPError(task['url'],403,'denied',{},io.BytesIO(b'NO_ACCESS'))
        with tempfile.TemporaryDirectory() as td:
            record,raw=e.acquire(task,Path(td),opener=deny)
            self.assertEqual(record['http_status'],403)
            self.assertEqual(raw,b'NO_ACCESS')
            self.assertEqual(gzip.decompress((Path(td)/record['raw_path']).read_bytes()),raw)

    def test_output_evidence_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'receipt.json';e.write_json(p,{'failed':True})
            with self.assertRaises(FileExistsError):e.write_json(p,{'failed':False})

    def test_no_model_run_or_authority_from_partial_sources(self):
        self.assertEqual(e.readiness()['new_model_evaluations'],0)
        self.assertEqual(e.readiness()['status'],'BLOCKED_DATA_READINESS')
        self.assertEqual(e.readiness()['authority']['capital_authority_twd'],0)
        with self.assertRaisesRegex(ValueError,'BLOCKED_DATA_READINESS'):e.require_adjusted_pnl_ready()
        self.assertEqual(len(e.requests()),13)


if __name__=='__main__':unittest.main()
