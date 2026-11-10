import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from hengce_hba_context_bridge_v1 import read_existing_two_group_tdcc, price_pair_for_same_tdcc_weeks, build


class TwoGroupExistingVesselTests(unittest.TestCase):
    """No vendor downloads; input is an existing, SHA-pinned TDCC raw-vessel fixture."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        p = self.root / 'eod/20261109'
        p.mkdir(parents=True)
        with (p/'price_1.csv').open('w', newline='', encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['Date','Ticker','Close'])
            w.writeheader()
            w.writerow({'Date':'2026-11-09','Ticker':'1101','Close':25})
        self.add_snapshot('20261030', '2026-10-31T04:58:00+08:00', 1000, 2000, 5)
        self.add_snapshot('20261106', '2026-11-07T04:58:00+08:00', 1500, 1500, 4)

    def tearDown(self):
        self.temp.cleanup()

    def add_snapshot(self, snapshot, first_observed, small_grade1, other_grade4, first_people):
        p=self.root/'ownership/tdcc'/snapshot
        p.mkdir(parents=True,exist_ok=True)
        raw=p/'tdcc_1_5_raw.csv'
        rows=[]
        for grade in range(1,16):
            shares=small_grade1 if grade==1 else other_grade4 if grade==4 else 1000 if grade in (2,3) else 500
            people=first_people if grade==1 else 2
            rows.append({'資料日期':snapshot,'證券代號':'1101','持股分級':grade,
                         '人數':people,'股數':shares,'占集保庫存數比例%':0})
        total=sum(r['股數'] for r in rows)
        rows += [
            {'資料日期':snapshot,'證券代號':'1101','持股分級':16,'人數':0,'股數':0,'占集保庫存數比例%':0},
            {'資料日期':snapshot,'證券代號':'1101','持股分級':17,'人數':sum(r['人數'] for r in rows),
             '股數':total,'占集保庫存數比例%':100}]
        with raw.open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=['資料日期','證券代號','持股分級','人數','股數','占集保庫存數比例%'])
            w.writeheader()
            w.writerows(rows)
        receipt={'status':'COMPLETE','snapshot_date':snapshot,'observed_at_taipei':first_observed,
                 'source':'https://opendata.tdcc.com.tw/getOD.ashx?id=1-5',
                 'source_sha256':hashlib.sha256(raw.read_bytes()).hexdigest()}
        (p/'receipt.json').write_text(json.dumps(receipt),encoding='utf-8')
        return raw

    def test_real_shares_not_total_holders_and_no_trading_promotion(self):
        meta,rows=read_existing_two_group_tdcc(self.root,'2026-11-10','2026-11-09')
        self.assertEqual(meta['status'],'VERIFIED_TWO_GROUP_RESEARCH')
        self.assertEqual(meta['stock_count'],1)
        self.assertEqual(meta['comparable_stock_count'],1)
        self.assertEqual(meta['categories']['散戶持股比重增加'],1)
        x=rows['1101']
        self.assertEqual(x['small_shares_delta'],500)
        self.assertEqual(x['other_shares_delta'],-500)
        self.assertEqual(x['small_holders_delta'],-1)
        self.assertTrue(x['holder_shares_disagree'])
        self.assertAlmostEqual(x['other_share_delta_pp'],-x['small_share_delta_pp'])
        self.assertFalse(x['trade_authority'])
        self.assertFalse(meta['authority']['selection'])
        self.assertFalse(meta['historical_13week_continuity_verified'])

    def test_tampered_source_is_not_promoted(self):
        p=self.root/'ownership/tdcc/20261106/tdcc_1_5_raw.csv'
        p.write_bytes(p.read_bytes()+b'\n')
        meta,rows=read_existing_two_group_tdcc(self.root,'2026-11-10','2026-11-09')
        self.assertEqual(meta['status'],'INSUFFICIENT_VERIFIED_TDCC_SNAPSHOTS')
        self.assertEqual(rows,{})

    def test_late_observation_is_not_backfilled(self):
        p=self.root/'ownership/tdcc/20261106/receipt.json'
        receipt=json.loads(p.read_text())
        receipt['observed_at_taipei']='2026-11-11T04:58:00+08:00'
        p.write_text(json.dumps(receipt))
        meta,rows=read_existing_two_group_tdcc(self.root,'2026-11-10','2026-11-09')
        self.assertEqual(meta['status'],'INSUFFICIENT_VERIFIED_TDCC_SNAPSHOTS')
        self.assertEqual(rows,{})

    def test_capital_change_is_excluded_not_interpreted_as_transfer(self):
        self.add_snapshot('20261106', '2026-11-07T04:58:00+08:00', 4500,1500,4)
        meta,rows=read_existing_two_group_tdcc(self.root,'2026-11-10','2026-11-09')
        self.assertEqual(meta['status'],'VERIFIED_TWO_GROUP_RESEARCH')
        self.assertEqual(meta['comparable_stock_count'],0)
        self.assertEqual(meta['exclusions']['SHARE_CAPITAL_CHANGE_GT_1PCT'],1)
        self.assertEqual(rows,{})

    def test_week_gap_is_not_forward_filled(self):
        p=self.root/'ownership/tdcc/20261030'
        for file in p.iterdir():file.unlink()
        p.rmdir()
        self.add_snapshot('20261022','2026-10-23T04:58:00+08:00',1000,2000,5)
        meta,rows=read_existing_two_group_tdcc(self.root,'2026-11-10','2026-11-09')
        self.assertEqual(meta['status'],'GAPPED_OR_STALE_TDCC_SNAPSHOTS')
        self.assertEqual(rows,{})


    def test_same_week_prices_and_full_market_registry_are_not_buy_signals(self):
        # Price change must be 10/30 -> 11/06, not 10/30 -> 11/09.
        for snap,close in [('20261030',100),('20261106',110)]:
            p=self.root/'eod'/snap
            p.mkdir(parents=True,exist_ok=True)
            day=snap[:4]+'-'+snap[4:6]+'-'+snap[6:]
            (p/'status.json').write_text(json.dumps({
                'formal_complete_day':True,'downstream_ready':True,
                'price_date':day,'institutional_date':day,'margin_date':day}))
            with (p/'price_1.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['Date','Ticker','Close'])
                w.writeheader()
                w.writerow({'Date':day,'Ticker':'1101','Close':close})
        meta,prices=price_pair_for_same_tdcc_weeks(self.root,'20261030','20261106')
        self.assertEqual(meta['status'],'VERIFIED_REFERENCE_WEEK_PRICES')
        self.assertEqual(prices['1101'],10.0)
        original={'target_tw_date':'2026-11-10','latest_verified_eod':'2026-11-09',
                  'data_gate':'EOD_VALID_MACRO_UNKNOWN',
                  'all_candidates':[],'total_candidates_before_limit':0,
                  'external_environment':{'label':'資料不足','status':'資料不足'}}
        # Existing short-window alert list is empty, but the validated all-market
        # two-group research registry must still include the stock.
        output=build(self.root,original)
        self.assertEqual(output['candidates'],[])
        self.assertEqual(len(output['two_group_market_registry']),1)
        x=output['two_group_market_registry'][0]
        self.assertEqual(x['same_week_price_ownership_pattern'],'UP_SMALL_SHARE_GAIN')
        self.assertEqual(x['same_week_price_return_pct'],10.0)
        self.assertFalse(x['selection_authority'])
        self.assertFalse(output['authority']['new_selection'])
        self.assertFalse(output['two_group_research']['multiweek_a_to_b_cycle_validated'])

    def test_pair_rejects_missing_reference_week_instead_of_using_current_eod(self):
        meta,prices=price_pair_for_same_tdcc_weeks(self.root,'20261030','20261106')
        self.assertEqual(meta['status'],'MISSING_VERIFIED_MATCHED_WEEKLY_EOD_PRICES')
        self.assertEqual(prices,{})

    def test_future_target_rejected(self):
        meta,rows=read_existing_two_group_tdcc(self.root,'2026-11-08','2026-11-09')
        self.assertEqual(meta['status'],'INVALID_TIME')
        self.assertEqual(rows,{})


if __name__=='__main__':
    unittest.main()
