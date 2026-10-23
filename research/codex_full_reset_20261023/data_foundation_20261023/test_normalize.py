"""Synthetic contracts for explicit representation fixes and positional schemas."""
import json
import unittest

import normalize as n


class NormalizationContracts(unittest.TestCase):
    def detail_fixture(self):
        obj={'stat':'ok','fields':n.DETAIL_FIELDS,'data':[['6189  ','fixture','4 元／股','','200 股',
              '0 股','0 股','0 元／股','0 股','0 股','0 股','0.00000000 股']]}
        parent={'ticker':'6189','effective_date':'2025-07-25','prior_close_reported':79,'reference_price_reported':62.5}
        return obj,parent

    def test_lower_case_status_supported_without_loosening_identity(self):
        obj,parent=self.detail_fixture()
        result=n.detail(json.dumps(obj).encode(),'6189','2025-07-25',parent)
        self.assertEqual(result['free_shares_per_1000_old_shares_reported'],'200')
        self.assertFalse(result['adjusted_pnl_ready'])
        obj['data'][0][0]='2364'
        with self.assertRaisesRegex(ValueError,'IDENTITY_MISMATCH'):n.detail(json.dumps(obj),'6189','2025-07-25',parent)

    def test_subscription_rights_and_reference_mismatch_rejected(self):
        obj,parent=self.detail_fixture();obj['data'][0][6]='100 股'
        with self.assertRaisesRegex(ValueError,'SUBSCRIPTION'):n.detail(json.dumps(obj),'6189','2025-07-25',parent)
        obj,parent=self.detail_fixture();parent['reference_price_reported']=70
        with self.assertRaisesRegex(ValueError,'FORMULA_MISMATCH'):n.detail(json.dumps(obj),'6189','2025-07-25',parent)

    def test_slash_date_normalizes_only_representation(self):
        obj={'stat':'OK','strDate':'20250101','endDate':'20251231','title':'114年減資恢復買賣參考價格',
             'fields':['恢復買賣日期','股票代號','名稱','停止買賣前收盤價格','恢復買賣參考價','減資原因'],
             'data':[['114/07/25','6189','fixture','100','190','退還股款']]}
        result=n.reduction(json.dumps(obj).encode(),2025,{'2025-07-25':{'6189'}})
        self.assertEqual(result['events'][0]['effective_date'],'2025-07-25')
        self.assertEqual(result['events'][0]['reference_price_reported'],190)
        self.assertIsNone(result['events'][0]['total_return_factor'])
        obj['data'][0][0]='114/02/30'
        with self.assertRaises(ValueError):n.reduction(json.dumps(obj).encode(),2025,{})

    def test_duplicate_reference_headers_keep_distinct_time_meanings(self):
        obj={'stat':'OK','date':'20250407','fields':n.LIMIT_FIELDS,
             'data':[['2330','fixture','110','100','90','101','101','100','102','114.04.02','可']]}
        result=n.limits(json.dumps(obj),{'2025-04-07':{'2330'}})[0]
        self.assertEqual(result['current_open_reference'],100)
        self.assertEqual(result['previous_open_reference'],101)
        self.assertFalse(result['auction_fill_proven'])
        obj['fields']=list(reversed(n.LIMIT_FIELDS))
        with self.assertRaises(ValueError):n.limits(json.dumps(obj),{'2025-04-07':{'2330'}})


if __name__=='__main__':unittest.main()
