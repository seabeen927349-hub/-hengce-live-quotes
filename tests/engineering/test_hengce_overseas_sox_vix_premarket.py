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
    build, nasdaq_rows, cboe_rows, vendor_url, canonical, COEFFICIENTS, CUTS, MODEL,
    source_observation, last_completed_us_weekday
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
    def test_individual_official_closes_survive_vendor_session_lag(self):
        expected=dt.date(2026,11,11)
        prior=dt.date(2026,11,10)
        self.s[prior]=9998.33;self.s[expected]=10564.11
        self.v[prior]=19.46
        observed=dt.datetime(2026,11,12,8,10,tzinfo=TZ)
        p=source_observation(observed,"2026-11-11",self.s,self.v,
                             self.sraw,self.vraw,vendor_url(observed.date()))
        self.assertEqual(p["sources"]["sox"]["latest_us_session"],"2026-11-11")
        self.assertEqual(p["sources"]["sox"]["latest_close"],10564.11)
        self.assertEqual(p["sources"]["vix"]["latest_us_session"],"2026-11-10")
        self.assertEqual(p["sources"]["vix"]["source_status"],"EXPECTED_US_EOD_NOT_YET_PUBLISHED")
        self.assertEqual(p["composite_readiness"],"BLOCKED_PENDING_ALIGNED_US_EOD")
        self.assertFalse(p["composite_forecast_emitted"])
        self.assertFalse(p["trading_authority"])
        self.assertEqual(p["source_observation_sha256"],
            canonical({k:v for k,v in p.items() if k!="source_observation_sha256"}))
        with self.assertRaisesRegex(ValueError,"LATEST_US_SOURCE_SESSION_MISMATCH"):
            build(observed,"2026-11-11",self.s,self.v,
                  self.sraw,self.vraw,vendor_url(observed.date()))

    def test_individual_observation_not_from_future_or_after_taipei_open(self):
        with self.assertRaisesRegex(ValueError,"NOT_TAIWAN_PREOPEN_WEEKDAY"):
            source_observation(dt.datetime(2026,11,12,9,1,tzinfo=TZ),
                "2026-11-11",self.s,self.v,self.sraw,self.vraw,
                vendor_url(dt.date(2026,11,12)))

    def test_two_individual_sources_ready_still_not_model_authorized(self):
        expected=dt.date(2026,11,11);prior=dt.date(2026,11,10)
        self.s[prior]=9998.33;self.s[expected]=10564.11
        self.v[prior]=19.46;self.v[expected]=19.25
        observed=dt.datetime(2026,11,12,8,10,tzinfo=TZ)
        p=source_observation(observed,"2026-11-11",self.s,self.v,
                             self.sraw,self.vraw,vendor_url(observed.date()))
        self.assertEqual(p["composite_readiness"],"BOTH_SOURCES_READY_FOR_SEPARATE_FORMAL_VALIDATION")
        self.assertFalse(p["composite_forecast_emitted"])

    def test_postopen_existing_vendor_eod_never_creates_backdated_forecast(self):
        expected=dt.date(2026,11,11)
        prior=dt.date(2026,11,10)
        self.s[prior]=9998.33
        self.s[expected]=10564.11
        self.v[prior]=19.46
        noon=dt.datetime(2026,11,12,12,7,tzinfo=TZ)
        observation=source_observation(noon,"2026-11-11",self.s,self.v,
                self.sraw,self.vraw,vendor_url(noon.date()),late_source_only=True)
        self.assertEqual(observation["observation_window"],"POST_OPEN_SOURCE_ONLY")
        self.assertEqual(observation["sources"]["sox"]["latest_us_session"],"2026-11-11")
        self.assertEqual(observation["sources"]["vix"]["latest_us_session"],"2026-11-10")
        self.assertFalse(observation["composite_forecast_emitted"])
        self.assertFalse(observation["trading_authority"])
        self.assertEqual(observation["composite_readiness"],
                         "POST_OPEN_SOURCE_ONLY_NO_PREOPEN_FORECAST")
        self.assertEqual(observation["source_observation_sha256"],
            canonical({k:v for k,v in observation.items()
                       if k!="source_observation_sha256"}))
        with self.assertRaisesRegex(ValueError,"NOT_TAIWAN_PREOPEN_WEEKDAY"):
            build(noon,"2026-11-11",self.s,self.v,
                  self.sraw,self.vraw,vendor_url(noon.date()))
        with self.assertRaisesRegex(ValueError,"NOT_POSTOPEN_TAIWAN_WEEKDAY"):
            source_observation(noon.replace(hour=8),"2026-11-11",self.s,self.v,
                               self.sraw,self.vraw,vendor_url(noon.date()),late_source_only=True)

    def test_late_official_observation_old_tdcc_context_not_promoted(self):
        noon=dt.datetime(2026,11,12,12,10,tzinfo=TZ)
        o=source_observation(noon,"2026-10-01",self.s,self.v,
               self.sraw,self.vraw,vendor_url(noon.date()),late_source_only=True)
        self.assertIsNone(o["reference_prev_tw_date"])
        self.assertFalse(o["composite_forecast_emitted"])

    def test_unrestricted_official_source_observation_us_winter_close(self):
        # On 2026-11-12 04:30 Taipei, NY is still 15:30 on 11/11.
        # 11/11 may appear prematurely in a source dump but MUST be ignored.
        before=dt.datetime(2026,11,12,4,30,tzinfo=TZ)
        self.s[dt.date(2026,11,10)]=9998.33
        self.s[dt.date(2026,11,11)]=10564.11
        self.v[dt.date(2026,11,10)]=19.46
        self.v[dt.date(2026,11,11)]=19.2
        self.assertEqual(last_completed_us_weekday(before),dt.date(2026,11,10))
        early=source_observation(before,None,self.s,self.v,self.sraw,self.vraw,
            vendor_url(before.date()),continuous_source_only=True)
        self.assertEqual(early["expected_us_session"],"2026-11-10")
        self.assertEqual(early["sources"]["sox"]["latest_us_session"],"2026-11-10")
        self.assertFalse(early["composite_forecast_emitted"])
        self.assertEqual(early["observation_window"],"ANYTIME_SOURCE_ONLY")
        self.assertEqual(early["composite_readiness"],
                         "ANYTIME_SOURCE_ONLY_NO_PREOPEN_FORECAST")
        self.assertIsNone(early["reference_prev_tw_date"])
        # At 05:30 Taiwan (NY 16:30) the US session is completed.
        after=before.replace(hour=5,minute=30)
        late=source_observation(after,None,self.s,self.v,self.sraw,self.vraw,
            vendor_url(after.date()),continuous_source_only=True)
        self.assertEqual(late["expected_us_session"],"2026-11-11")
        self.assertEqual(late["sources"]["sox"]["latest_us_session"],"2026-11-11")
        self.assertEqual(late["sources"]["vix"]["latest_us_session"],"2026-11-11")
        self.assertFalse(late["trading_authority"])
        self.assertEqual(late["source_observation_sha256"],canonical(
            {k:v for k,v in late.items() if k!="source_observation_sha256"}))

    def test_weekend_and_taipei_after_open_official_source_observation(self):
        # No weekday or Taipei hour gate on pure source information.
        t=dt.datetime(2026,11,14,19,17,tzinfo=TZ)
        self.s[dt.date(2026,11,13)]=10000
        self.v[dt.date(2026,11,13)]=21
        obs=source_observation(t,None,self.s,self.v,self.sraw,self.vraw,
             vendor_url(t.date()),continuous_source_only=True)
        self.assertEqual(obs["target_tw_date"],"2026-11-14")
        self.assertEqual(obs["expected_us_session"],"2026-11-13")
        self.assertEqual(obs["sources"]["sox"]["source_status"],"EXPECTED_US_EOD_PRESENT")
        self.assertEqual(obs["observation_window"],"ANYTIME_SOURCE_ONLY")
        self.assertFalse(obs["composite_forecast_emitted"])
        self.assertNotIn("direction_forecast",obs)
        with self.assertRaisesRegex(ValueError,"SOURCE_OBSERVATION_MODE_CONFLICT"):
            source_observation(t,None,self.s,self.v,self.sraw,self.vraw,
                 vendor_url(t.date()),continuous_source_only=True,late_source_only=True)

    def test_summer_daylight_savings_closing_cutoff(self):
        # NY EDT close maps to Taipei 04:00 in July; EST maps to 05:00 in Nov.
        self.assertEqual(last_completed_us_weekday(
            dt.datetime(2026,7,16,3,59,tzinfo=TZ)),dt.date(2026,7,14))
        self.assertEqual(last_completed_us_weekday(
            dt.datetime(2026,7,16,4,5,tzinfo=TZ)),dt.date(2026,7,15))

    def test_continuous_sources_can_have_different_publisher_dates(self):
        t=dt.datetime(2026,11,12,13,35,tzinfo=TZ)
        self.s[dt.date(2026,11,11)]=10564.11
        self.v[dt.date(2026,11,10)]=19.46
        obs=source_observation(t,None,self.s,self.v,self.sraw,self.vraw,
                vendor_url(t.date()),continuous_source_only=True)
        self.assertEqual(obs["sources"]["sox"]["latest_us_session"],"2026-11-11")
        self.assertEqual(obs["sources"]["vix"]["latest_us_session"],"2026-11-10")
        self.assertEqual(obs["sources"]["vix"]["source_status"],"EXPECTED_US_EOD_NOT_YET_PUBLISHED")
        self.assertFalse(obs["composite_forecast_emitted"])

    def test_original_official_source_workflow_monitors_all_taipei_hours(self):
        source=(Path(__file__).resolve().parents[2]/
                ".github/workflows/hengce-overseas-sox-vix-premarket.yml").read_text()
        self.assertIn("- cron: '17 */2 * * *'",source)
        self.assertIn("--mode observe --observations-out",source)
        self.assertIn("source_status_anytime_latest.json",source)
        self.assertIn("group: hengce-hba-surveillance-research",source)
        self.assertIn("steps.observe_official_us_eod.outcome == 'success'",source)
        self.assertIn("continue-on-error: true",source)
        self.assertIn("steps.official_preopen_model.outcome == 'success'",source)
        self.assertIn("PREOPEN_MODEL_WINDOW_CLOSED; 24H_SOURCE_MONITOR_STILL_RUNS",source)
        self.assertNotIn("BLOCKED_PREOPEN_MISSED",source)
        self.assertIn("--profile conservative-all",source)

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
