"""Offline regressions for reconstruction, independent scope and exact-set gates."""
import unittest
from unittest.mock import patch
import stage_b_build_twse_year as b

HEADER='證券代號,證券名稱,開盤價,最高價,最低價,收盤價,成交股數,成交金額\n'
def source(rows='2330,台積電,100,101,99,100,1000,100000\n3036A,文曄甲特,40,41,39,40,1000,40000\n'):
    return '"112年01月03日 每日收盤行情(電子工業)"\n'+HEADER+rows

class ContractTests(unittest.TestCase):
    def test_scope_independent_of_expected_set(self):
        rows,qa=b.validate_daily(source(),'2023-01-03',{'2330'})
        self.assertEqual(qa['status'],'PASS')
        self.assertEqual([r['ticker'] for r in rows],['2330'])
        self.assertEqual(qa['excluded_non_common_tickers'],['3036A'])
    def test_extra_common_stock_still_fails(self):
        _,qa=b.validate_daily(source()+'2454,聯發科,100,101,99,100,1000,100000\n','2023-01-03',{'2330'})
        self.assertEqual(qa['status'],'MEMBERSHIP_SET_MISMATCH')
        self.assertEqual(qa['extra_sample'],['2454'])
    def test_missing_member_still_fails(self):
        _,qa=b.validate_daily(source(),'2023-01-03',{'2330','2454'})
        self.assertEqual(qa['status'],'MEMBERSHIP_SET_MISMATCH')
    def test_duplicate_still_fails(self):
        _,qa=b.validate_daily(source()+'2330,台積電,100,101,99,100,1000,100000\n','2023-01-03',{'2330'})
        self.assertEqual(qa['status'],'DUPLICATE_TICKERS')
    def test_wrong_date_or_table_fails(self):
        for text in [source().replace('01月03日','01月04日'),source().replace('電子工業','金融保險')]:
            _,qa=b.validate_daily(text,'2023-01-03',{'2330'})
            self.assertEqual(qa['status'],'SOURCE_DATE_OR_SECTOR_MISMATCH')
    def test_missing_or_duplicate_header_fails(self):
        for text in [source().replace('收盤價','未知'),source().replace('最高價','收盤價')]:
            with self.assertRaises(ValueError):b.validate_daily(text,'2023-01-03',{'2330'})
    def test_malformed_stock_record_fails(self):
        with self.assertRaises(ValueError): b.validate_daily(source('2330,,100\n'),'2023-01-03',{'2330'})

if __name__=='__main__':unittest.main(argv=[__file__])
