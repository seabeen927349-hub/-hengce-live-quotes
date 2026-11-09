import copy
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_finmind_intraday_freshness_gate import (
    EXPECTED_METRIC_SHA, Rejected, payload_hash, validate,
)

TW = ZoneInfo("Asia/Taipei")
NOW = datetime(2026, 11, 9, 9, 40, tzinfo=TW)


def fixtures(now=NOW, latest=None):
    latest = latest or (now - timedelta(minutes=3))
    base = {
        "generated_at_taipei": (now - timedelta(minutes=1)).isoformat(),
        "metric_contract_sha256": EXPECTED_METRIC_SHA,
        "latest_source_timestamp": latest.strftime("%Y-%m-%d %H:%M:%S.%f"),
    }
    context = dict(base, market_date=now.date().isoformat(),
                   market={"return_observed_count": 1085})
    context["payload_sha256"] = payload_hash(context)
    status = dict(base, source="FinMind",
                  state="SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY",
                  active_universe_transport_full_coverage=True,
                  active_required_count=1088, active_covered_count=1088,
                  finmind_metric_observation_count=1085, metric_unknown_count=3,
                  formal_eod_authority=False, trading_authority=False,
                  context_payload_sha256=context["payload_sha256"])
    monitor = dict(base, market_date=now.date().isoformat(),
                   source="FinMind taiwan_stock_tick_snapshot",
                   monitor_state="LIVE_CONTEXT_READY",
                   active_universe_transport_full_coverage=True,
                   active_required_count=1088, active_covered_count=1088,
                   finmind_metric_observation_count=1085, metric_unknown_count=3,
                   formal_eod_authority=False, trading_authority=False,
                   formal_escape_authority=False, feature_detector_input_authority=False,
                   canonical_eod_legs_replaced=False)
    monitor["payload_sha256"] = payload_hash(monitor)
    return context, status, monitor


class FinMindMonitorFreshnessTests(unittest.TestCase):
    def test_current_twse_1088_valid(self):
        c, s, m = fixtures()
        x = validate(c, s, m, NOW)
        self.assertEqual(x["state"], "PASS_FINMIND_SHADOW_FRESHNESS")
        self.assertEqual(x["valid_metric_count"], 1085)
        self.assertTrue(x["intraday_recency_gate_applied"])

    def test_friday_snapshot_must_not_be_monday_intraday(self):
        c, s, m = fixtures()
        for obj in (c, m):
            obj["market_date"] = "2026-11-06"
        c["payload_sha256"] = payload_hash(c)
        s["context_payload_sha256"] = c["payload_sha256"]
        m["payload_sha256"] = payload_hash(m)
        with self.assertRaisesRegex(Rejected, "NOT_CURRENT_TW_MARKET_DAY"):
            validate(c, s, m, NOW)

    def test_twenty_six_minute_source_fails(self):
        c, s, m = fixtures(latest=NOW-timedelta(minutes=26))
        with self.assertRaisesRegex(Rejected, "INTRADAY_SOURCE_OLDER_THAN_25_MINUTES"):
            validate(c, s, m, NOW)

    def test_afterhours_recent_collection_of_same_day_snapshot(self):
        now = datetime(2026, 11, 9, 17, 0, tzinfo=TW)
        c, s, m = fixtures(now, latest=now.replace(hour=14, minute=30))
        x = validate(c, s, m, now)
        self.assertFalse(x["intraday_recency_gate_applied"])

    def test_missing_metric_coverage_is_fail_closed(self):
        c, s, m = fixtures()
        s["finmind_metric_observation_count"] = 900
        s["metric_unknown_count"] = 188
        with self.assertRaisesRegex(Rejected, "FINMIND_METRIC_COVERAGE_LOW"):
            validate(c, s, m, NOW)

    def test_digest_tampering_is_fail_closed(self):
        c, s, m = fixtures()
        c["market"]["return_observed_count"] = 1000
        with self.assertRaisesRegex(Rejected, "CONTEXT_PAYLOAD_TAMPERED"):
            validate(c, s, m, NOW)

    def test_no_escape_authority_promotion(self):
        c, s, m = fixtures()
        m["formal_escape_authority"] = True
        m["payload_sha256"] = payload_hash(m)
        with self.assertRaisesRegex(Rejected, "ESCAPE_AUTHORITY_FORBIDDEN"):
            validate(c, s, m, NOW)

    def test_future_source_timestamp_is_rejected(self):
        c, s, m = fixtures(latest=NOW+timedelta(minutes=5))
        with self.assertRaisesRegex(Rejected, "SOURCE_TIMESTAMP_IN_FUTURE"):
            validate(c, s, m, NOW)

    def test_old_collector_is_rejected(self):
        c, s, m = fixtures()
        stamp = (NOW - timedelta(minutes=20)).isoformat()
        for v in (c,s,m):
            v["generated_at_taipei"] = stamp
        c["payload_sha256"] = payload_hash(c)
        s["context_payload_sha256"] = c["payload_sha256"]
        m["payload_sha256"] = payload_hash(m)
        with self.assertRaisesRegex(Rejected, "COLLECTOR_OUTPUT_NOT_FRESH"):
            validate(c, s, m, NOW)


if __name__ == "__main__":
    unittest.main()
