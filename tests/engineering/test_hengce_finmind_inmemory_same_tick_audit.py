"""Offline contract tests: no FinMind/TWSE network access or licensed rows."""
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_finmind_inmemory_same_tick_audit import audit_snapshot, SCHEMA

TZ = ZoneInfo("Asia/Taipei")
DAY = "2026-11-18"
START = datetime(2026, 11, 18, 13, 5, 18, tzinfo=TZ)
END = datetime(2026, 11, 18, 13, 5, 19, tzinfo=TZ)


def finmind(price="20.5", stamp="2026-11-18 13:05:10"):
    return {"stock_id": "1101", "date": stamp, "close": price}


def mis(price="20.5", timestamp="13:05:10", day="20261118"):
    return {"d": day, "t": timestamp, "z": price, "c": "1101"}


class InMemorySameTickAuditTests(unittest.TestCase):
    def test_prices_and_timestamps_only_make_candidates(self):
        codes = {"1101", "1102", "1103", "1104", "1105", "1106"}
        fin = {
            "1101": finmind(),
            "1102": finmind("19.0"),
            "1103": finmind("50.5"),
            "1104": finmind(),
            "1105": finmind(stamp="2026-11-17 13:05:10"),
        }
        secondary = {
            "1101": mis(),
            "1102": mis("19.1"),
            "1103": mis("50.5", timestamp="13:05:00"),
        }
        result = audit_snapshot(codes, fin, secondary, DAY, START, END)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["status"], "CANDIDATES_ONLY")
        self.assertEqual(result["reason_counts"], {
            "DIFFERENT_PRICE_CANDIDATE": 1,
            "FINMIND_MISSING": 1,
            "FINMIND_NOT_TODAY": 1,
            "MATCHED_TRADE_TIME_PRICE_CANDIDATE": 1,
            "SECOND_SOURCE_NOT_COLLECTED": 1,
            "TRADE_TIMESTAMPS_DIFFER": 1,
        })
        self.assertEqual(result["cross_source_candidate_count"], 2)
        self.assertEqual(result["fully_independently_verified_count"], 0)
        self.assertEqual(result["mis_existing_scope_count"], 3)
        self.assertEqual(result["new_vendor_requests"], 0)
        self.assertFalse(result["trading_authority"])
        self.assertFalse(result["raw_vendor_rows_persisted"])
        self.assertFalse(result["per_security_rows_persisted"])
        packet = json.dumps(result)
        for value in ("1101", "1102", "1103", "50.5", "19.1"):
            self.assertNotIn(value, packet)

    def test_no_existing_mis_is_zero_cross_source_validation(self):
        result = audit_snapshot({"1101", "1102"}, {"1101": finmind(), "1102": finmind()}, {},
                                DAY, START, END)
        self.assertEqual(result["cross_source_candidate_count"], 0)
        self.assertEqual(result["reason_counts"]["SECOND_SOURCE_NOT_COLLECTED"], 2)
        self.assertEqual(result["status"], "BLOCKED_NO_SAME_TIME_SECOND_SOURCE")

    def test_wrong_price_time_and_missing_mis_do_not_promote(self):
        result = audit_snapshot(
            {"1101", "1102", "1103", "1104"},
            {
                "1101": finmind(price="0"),
                "1102": finmind(stamp="2026-11-18 12:00:00"),
                "1103": finmind(stamp="2026-11-18 13:05:40"),
                "1104": finmind(price="20.5"),
            },
            {"1104": mis(price="-")},
            DAY, START, END,
        )
        self.assertEqual(result["cross_source_candidate_count"], 0)
        self.assertEqual(result["reason_counts"], {
            "FINMIND_FUTURE_TIME": 1,
            "FINMIND_PRICE_NOT_COMPARABLE": 1,
            "FINMIND_STALE_TRADE_TIME": 1,
            "TWSE_LAST_PRICE_UNAVAILABLE": 1,
        })

    def test_mis_wrong_session_stale_or_missing_time(self):
        result = audit_snapshot(
            {"1101", "1102", "1103"},
            {"1101": finmind(), "1102": finmind(), "1103": finmind()},
            {
                "1101": mis(day="20261117"),
                "1102": mis(timestamp="13:03:10"),
                "1103": mis(timestamp="--"),
            },
            DAY, START, END,
        )
        self.assertEqual(result["cross_source_candidate_count"], 0)
        self.assertEqual(result["reason_counts"], {
            "TWSE_TRADE_TIME_UNVERIFIED": 2,
            "TWSE_NOT_CURRENT_TRADE": 1,
        })

    def test_scope_clocks_and_date_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "MIS_SCOPE"):
            audit_snapshot({"1101"}, {"1101": finmind()}, {"9999": mis()}, DAY, START, END)
        with self.assertRaisesRegex(ValueError, "CAPTURE_CLOCK"):
            audit_snapshot({"1101"}, {}, {}, DAY, END, START)
        with self.assertRaisesRegex(ValueError, "WRONG_SESSION"):
            audit_snapshot({"1101"}, {}, {}, "2026-11-17", START, END)


if __name__ == "__main__":
    unittest.main()
