"""Strict parser, source receipts, PIT and isolated guarded-publisher checks."""
import datetime as dt
import hashlib
import json
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_taifex_taiwan_vix_v1 import parse_month, build, canonical, month_url
import hengce_publish as publish

TZ = ZoneInfo("Asia/Taipei")
HEADER = "交易日期\t時間(時/分/秒/毫秒)\t臺指選擇權波動率指數\t收盤前1分鐘平均指數\n"
ROWS = [
    "20261105\t13450000\t39.92\t39.91",
    "20261106\t13450000\t46.52\t46.50",
    "20261109\t13450000\t40.55\t40.53",
    "20261110\t13450000\t38.73\t38.70",
    "20261111\t13450000\t38.30\t38.34",
    "20261112\t13450000\t40.28\t40.28",
    "20261113\t13450000\t37.84\t37.84",
]


def raw(*rows):
    return (HEADER + "\n".join(rows) + "\n").encode("utf-8")


class TaiwanVixTests(unittest.TestCase):
    def test_official_1345_column_and_source_format(self):
        d = parse_month(raw(*ROWS), 2026, 11)
        self.assertEqual(d[dt.date(2026, 11, 13)], 37.84)
        self.assertNotEqual(d[dt.date(2026, 11, 11)], 38.34)
        self.assertEqual(d[dt.date(2026, 11, 5)], 39.92)

    def test_timestamp_and_month_integrity(self):
        for bad in (
            "20261113\t13440000\t37.84\t37.84",
            "20261013\t13450000\t37.84\t37.84",
            "20261114\t13450000\t37.84\t37.84",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_month(raw(*ROWS, bad), 2026, 11)
        with self.assertRaises(ValueError):
            parse_month(raw("20261113\t13450000\t-1\t37.84"), 2026, 11)
        with self.assertRaises(ValueError):
            parse_month(raw("20261113\t13450000\t37.84\t37.84",
                            "20261113\t13450000\t37.90\t37.84"), 2026, 11)

    def test_pit_readout_and_unchanged_core_model(self):
        s = parse_month(raw(*ROWS), 2026, 11)
        item = (2026, 11, s, "a" * 64, month_url(2026, 11))
        now = dt.datetime(2026, 11, 18, 9, 30, tzinfo=TZ)
        out = build(now, [item])
        self.assertEqual(out["vix_session_date"], "2026-11-13")
        self.assertEqual(out["vix_1345"], 37.84)
        self.assertEqual(out["change_1d_points"], -2.44)
        self.assertEqual(out["source"], "TAIFEX")
        self.assertFalse(out["formal_forecast"])
        self.assertFalse(out["trading_authority"])
        self.assertFalse(out["model_score_authority"])
        self.assertEqual(out["receipt_sha256"], canonical(
            {k:v for k,v in out.items() if k != "receipt_sha256"}))
        with self.assertRaisesRegex(ValueError, "TOO_OLD"):
            build(now + dt.timedelta(days=12), [item])
        future = dict(s); future[dt.date(2026,11,18)] = 60.
        early = build(now, [(2026,11,future,"b"*64,month_url(2026,11))])
        self.assertEqual(early["vix_session_date"], "2026-11-13")
        late = build(now.replace(hour=14), [(2026,11,future,"b"*64,month_url(2026,11))])
        self.assertEqual(late["vix_session_date"], "2026-11-18")
        with self.assertRaisesRegex(ValueError, "SOURCE_PROOF_INVALID"):
            build(now, [(2026,11,s,"z"*64,month_url(2026,11))])

    def test_no_new_stock_or_overseas_publication_authority(self):
        prof = publish.PROFILES["taifex-taiwan-vix"]
        self.assertTrue(publish.matches("environment/taifex_taiwan_vix/latest.json", prof["writes"]))
        self.assertTrue(publish.matches("environment/taifex_taiwan_vix/history/20261113_a.json", prof["writes"]))
        for target in ("overseas_premarket/latest.json", "eod/20261117/status.json",
                       "research/hba_surveillance/latest.json", "ownership/tdcc/latest.json"):
            self.assertFalse(publish.matches(target,prof["writes"]))


if __name__ == "__main__":
    unittest.main()
