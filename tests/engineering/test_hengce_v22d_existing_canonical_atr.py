"""Optional private ORIGINAL 2026 canonical mother: no new vessel, no predictions.

Synthetic fixtures contain 21 official dates, 900 distinct tickers per date
and 781 pre-2019 fixed-cohort entries. Production SHA is never bypassed:
unit tests inject expected digests for their temporary SYNTHETIC files only.
"""
import csv
import gzip
import hashlib
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from scripts.hengce_v22d_existing_canonical_atr import OriginalCanonicalMotherATR, PriceEvidenceBlocked
from scripts.hengce_v22_max5_atr_price_plan import _calendar, _sessions_ending
from scripts.hengce_v22d_max5_operations import worklist
from scripts.hengce_scan_once_router import report

ROOT=Path(__file__).resolve().parents[2]
DAY=date(2026,11,11)
NOW=datetime.fromisoformat("2026-11-11T23:55:00+08:00")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OriginalCanonicalATRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.tmp.name)
        for path in (
            "governance/TWSE_TRADING_CALENDAR_2026_v1.json",
            "governance/TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json",
            "hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json",
            "research/retail_top5/v22d_historical_20261105.json",
        ):
            dest=cls.root/path
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/path).read_bytes())
        cls.cal=_calendar(cls.root)
        cls.days=_sessions_ending(cls.cal,DAY,22)
        cls.mother=cls.root/"original_2026_mother.csv"
        cls.tdcc=cls.root/"original_fixed_781_tdcc.csv.gz"
        with cls.mother.open("w",encoding="utf-8",newline="") as f:
            w=csv.writer(f)
            w.writerow(("Date","Ticker","Open","High","Low","Close"))
            for d in cls.days:
                for ticker in range(1100,2000):
                    w.writerow((d.isoformat(),str(ticker),100,103,100,102))
        with gzip.open(cls.tdcc,"wt",encoding="utf-8",newline="") as f:
            w=csv.writer(f)
            w.writerow(("SnapshotDate","Ticker","TierStatus","Big400Pct"))
            for ticker in range(1100,2000):
                w.writerow(("20180105",str(ticker),"VALID",
                            "50" if ticker<=1880 else "49"))
        cls.original_mother_sha=digest(cls.mother)
        cls.original_tdcc_sha=digest(cls.tdcc)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def vessel(self, mother=None, tdcc=None, override_mother_sha=None):
        return OriginalCanonicalMotherATR(
            mother or self.mother,tdcc or self.tdcc,
            expected_canonical_sha=override_mother_sha or self.original_mother_sha,
            expected_tdcc_sha=self.original_tdcc_sha)

    def test_fixed_original_cohort_781_and_21_consecutive_sessions(self):
        v=self.vessel()
        self.assertEqual(len(v.tickers),781)
        self.assertIn("1802",v.tickers)
        self.assertNotIn("1999",v.tickers)
        x=v.atr20(DAY,"1802",self.cal)
        self.assertEqual(x["atr20"],3)
        self.assertEqual(x["official_close"],102)
        self.assertEqual(x["start_session"],self.days[-21].isoformat())
        self.assertEqual(x["through_session"],DAY.isoformat())
        self.assertEqual(x["observation_sessions"],21)
        self.assertEqual(x["method"],"SMA20_OF_TRUE_RANGE")
        self.assertFalse(x["prospective_tdcc_publication_certified"])

    def test_noncohort_stock_cannot_inject_price(self):
        v=self.vessel()
        with self.assertRaisesRegex(PriceEvidenceBlocked,"TICKER_NOT_IN_FIXED_781"):
            v.ticker_day(DAY,"1999")

    def test_modified_existing_canonical_sha_blocks_before_any_price(self):
        modified=self.root/"changed_mother.csv"
        modified.write_bytes(self.mother.read_bytes()+b"\\n")
        with self.assertRaisesRegex(PriceEvidenceBlocked,"ORIGINAL_CANONICAL_2026_SHA_MISMATCH"):
            self.vessel(mother=modified)

    def test_modified_tdcc_roster_sha_blocks_before_any_price(self):
        changed=self.root/"changed_tdcc.csv.gz"
        changed.write_bytes(self.tdcc.read_bytes()+b"\\n")
        with self.assertRaisesRegex(PriceEvidenceBlocked,"ORIGINAL_G1_TDCC_781_SHA_MISMATCH"):
            self.vessel(tdcc=changed)

    def test_one_missing_official_ohlc_blocks_just_that_ticker(self):
        modified=self.root/"no_close_mother.csv"
        # Test fixture changed ONE official field and its source SHA is
        # re-pinned explicitly, to test no-price handling (not a bypass).
        data=self.mother.read_text(encoding="utf-8")
        needle=DAY.isoformat()+",1802,100,103,100,102"
        self.assertEqual(data.count(needle),1)
        modified.write_text(data.replace(needle,DAY.isoformat()+",1802,--,--,--,--"),
                            encoding="utf-8")
        v=self.vessel(mother=modified,override_mother_sha=digest(modified))
        with self.assertRaisesRegex(PriceEvidenceBlocked,"OFFICIAL_TICKER_OHLC_MISSING"):
            v.atr20(DAY,"1802",self.cal)
        self.assertEqual(v.atr20(DAY,"1801",self.cal)["atr20"],3)

    def test_no_future_date_supported_from_11_11_sha_pin(self):
        v=self.vessel()
        with self.assertRaisesRegex(PriceEvidenceBlocked,"DATE_OUTSIDE_SHA_PINNED"):
            v.ticker_day(date(2026,11,12),"1802")
        with self.assertRaisesRegex(PriceEvidenceBlocked,"DATE_OUTSIDE_SHA_PINNED"):
            v.atr20(date(2026,11,12),"1802",self.cal)

    def test_20_true_ranges_and_same_source_replay_are_deterministic(self):
        v=self.vessel()
        a=v.atr20(DAY,"1802",self.cal)
        b=v.atr20(DAY,"1802",self.cal)
        self.assertEqual(a,b)
        self.assertEqual(a["original_2026_mother_sha256"],digest(self.mother))
        self.assertEqual(a["original_tdcc_fixed_781_sha256"],digest(self.tdcc))

    def test_max5_holdings_can_use_source_without_unlocking_trades(self):
        v=self.vessel()
        account=[{
            "ticker":"1802","entry_date":"2026-11-10",
            "entry_fill":"110","quantity":"1000","signal_atr20":"3",
            "peak_close":"110","risk_floor":"104","pending_exit":"false",
        }]
        x=worklist(NOW,self.root,holdings=account,journal=[],vessel=v,calendar=self.cal)
        self.assertEqual(x["review_eod_session"],DAY.isoformat())
        self.assertEqual(x["position_states"][0]["initial_risk_floor"],104)
        self.assertEqual(x["position_states"][0]["latest_verified_close"],102)
        self.assertEqual(x["position_states"][0]["status"],"EXIT_PENDING_MANUAL_CONFIRMATION")
        self.assertEqual(x["status"],"WAITING_VERIFIED_CURRENT_V22D_DAILY_FORECAST")
        self.assertIsNone(x["candidate"])
        self.assertFalse(x["broker_execution"])
        self.assertFalse(x["buy_signal"])

    def test_scan_report_accepts_explicit_verified_canonical_only(self):
        v=self.vessel()
        x=report(NOW,self.root,holdings=[],journal=[],vessel=v)
        self.assertEqual(x["status"],"NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(x["rows"],[])
        self.assertEqual(x["reporting"]["v22d_max5_daily_account_worklist"]["position_count"],0)
        self.assertFalse(x["broker_order_execution"])
        self.assertFalse(x["buy_signal"])
        self.assertFalse(x["sell_signal"])


if __name__=="__main__":
    unittest.main()
