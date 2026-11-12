#!/usr/bin/env python3
"""PIT and vendor-source tests. Production vendor downloader is separately probed in CI."""
import csv
import datetime as dt
import io
import json
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from hengce_overseas_sox_vix_premarket_v1 import (
    build, nasdaq_rows, cboe_rows, vendor_url, canonical, COEFFICIENTS, CUTS, MODEL
)

TZ=ZoneInfo("Asia/Taipei")
NOW=dt.datetime(2026,11,9,8,15,tzinfo=TZ)
PREVIOUS="2026-11-06"

def synthetic_xlsx():
    from openpyxl import Workbook
    w=Workbook();s=w.active
    s.append(["Trade Date","Index Value"])
    s.append(["11/05/2026","9,011.14"])
    s.append(["11/06/2026","9,390.25"])
    f=io.BytesIO();w.save(f);w.close()
    return f.getvalue()

VIX=b"DATE,OPEN,HIGH,LOW,CLOSE\n11/05/2026,28.18,28.18,28.18,28.18\n11/06/2026,25.64,25.64,25.64,25.64\n"

class OverseasProducerTests(unittest.TestCase):
    def setUp(self):
        self.sraw=synthetic_xlsx();self.vraw=VIX
        self.s=nasdaq_rows(self.sraw);self.v=cboe_rows(self.vraw)
    def packet(self,when=NOW,previous=PREVIOUS):
        return build(when,previous,self.s,self.v,self.sraw,self.vraw,vendor_url(when.date()))
    def test_synthetic_vendor_parsing(self):
        self.assertEqual(self.s[dt.date(2026,11,6)],9390.25)
        self.assertEqual(self.v[dt.date(2026,11,6)],25.64)
    def test_model_grade_and_reproducible_digest(self):
        p=self.packet()
        self.assertEqual(p["direction_forecast"]["grade"],5)
        self.assertGreater(p["direction_forecast"]["expected_taiex_open_gap_log_pct"],0.6)
        self.assertLess(p["direction_forecast"]["expected_taiex_open_gap_log_pct"],0.9)
        self.assertEqual(p["latest_us_session"],"2026-11-06")
        self.assertEqual(p["packet_sha256"],canonical({k:v for k,v in p.items() if k!="packet_sha256"}))
        self.assertEqual(p["status"],"PASS_VERIFIED_VENDOR_EOD")
        self.assertFalse(p["trading_authority"])
    def test_weekend_rejected(self):
        with self.assertRaisesRegex(ValueError,"NOT_TAIWAN_PREOPEN_WEEKDAY"):
            self.packet(dt.datetime(2026,11,7,8,15,tzinfo=TZ))
    def test_postopen_rejected(self):
        with self.assertRaisesRegex(ValueError,"NOT_TAIWAN_PREOPEN_WEEKDAY"):
            self.packet(dt.datetime(2026,11,9,9,1,tzinfo=TZ))
    def test_us_session_mismatch_rejected(self):
        self.v.pop(dt.date(2026,11,6))
        with self.assertRaisesRegex(ValueError,"LATEST_US_SOURCE_SESSION_MISMATCH"):self.packet()
    def test_both_sources_publish_expected_wednesday(self):
        # Thursday Taipei preopen must use Wednesday's US session,
        # not whichever publisher happens to have the most rows.
        w=dt.date(2026,11,11); t=dt.date(2026,11,10)
        self.s[t]=9050.0; self.v[t]=23.0
        self.s[w]=9150.0; self.v[w]=22.0
        p=self.packet(dt.datetime(2026,11,12,8,15,tzinfo=TZ),
                      previous="2026-11-11")
        self.assertEqual(p["latest_us_session"],"2026-11-11")
        self.assertEqual(p["base_us_session"],"2026-11-10")
        self.assertEqual(p["status"],"PASS_VERIFIED_VENDOR_EOD")

    def test_delayed_vix_never_falls_back_to_stale_common_day(self):
        # Diagnostic must reveal each publisher's newest completed date.
        t=dt.date(2026,11,10); w=dt.date(2026,11,11)
        self.s[t]=9050.0; self.v[t]=23.0; self.s[w]=9150.0
        when=dt.datetime(2026,11,12,8,15,tzinfo=TZ)
        with self.assertRaisesRegex(ValueError,
                 "LATEST_US_SOURCE_SESSION_MISMATCH sox=2026-11-11 "
                 "vix=2026-11-10 common=2026-11-10 expected=2026-11-11"):
            self.packet(when,previous="2026-11-11")

    def test_unexpected_weekend_row_is_not_a_us_session(self):
        self.s[dt.date(2026,11,7)]=99999.0
        self.v[dt.date(2026,11,7)]=999.0
        self.assertEqual(self.packet()["latest_us_session"],"2026-11-06")

    def test_both_sources_stale_still_blocks(self):
        when=dt.datetime(2026,11,12,8,15,tzinfo=TZ)
        with self.assertRaisesRegex(ValueError,"LATEST_EXPECTED_US_EOD_NOT_VERIFIED"):
            self.packet(when,previous="2026-11-11")

    def test_stale_us_friday_rejected(self):
        t=dt.datetime(2026,11,13,8,15,tzinfo=TZ)
        with self.assertRaisesRegex(ValueError,"LATEST_EXPECTED_US_EOD_NOT_VERIFIED"):
            self.packet(t)
    def test_early_tuesday_before_new_us_eod_fails_closed(self):
        # If GitHub runs an early retry promptly, Friday's US EOD must NOT
        # masquerade as Monday US EOD for the Tuesday Taipei premarket.
        t=dt.datetime(2026,11,10,5,12,tzinfo=TZ)
        with self.assertRaisesRegex(ValueError,"LATEST_EXPECTED_US_EOD_NOT_VERIFIED"):
            self.packet(t)
    def test_no_taiwan_stale_eod(self):
        with self.assertRaisesRegex(ValueError,"STALE_PREVIOUS_TW_SESSION"):
            self.packet(previous="2026-10-20")
    def test_invalid_vendor_format(self):
        with self.assertRaisesRegex(ValueError,"NASDAQ_NOT_XLSX"):
            nasdaq_rows(b"<html>blocked</html>")
        with self.assertRaisesRegex(ValueError,"CBOE_CSV_SCHEMA_INVALID"):
            cboe_rows(b"error,message\nfail,blocked")
    def test_wrong_source_no_future_price(self):
        self.s[dt.date(2026,11,10)]=99999.0
        self.assertEqual(self.packet()["latest_us_session"],"2026-11-06")
    def test_no_fabricated_last_close(self):
        self.assertEqual(self.packet()["sources"]["sox"]["latest_close"],9390.25)
        self.assertEqual(self.packet()["sources"]["sox"]["prior_close"],9011.14)

if __name__=="__main__":
    unittest.main()
