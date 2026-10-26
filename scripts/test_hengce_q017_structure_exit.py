#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import hengce_alert_ledger as alert_ledger
import hengce_q017_position_watch as position_watch
import hengce_q017_structure_exit as structure


def bar(day, high, low, close):
    return {"date": day, "open": close, "high": high, "low": low, "close": close}


SETUP = {
    "prev_high": 10.0,
    "prev_high_date": "2026-01-02",
    "lower_high": 9.0,
    "lower_high_date": "2026-01-04",
    "break_level": 5.0,
    "swing_low_date": "2026-01-03",
    "activation_index": 5,
    "activation_date": "2026-01-06",
}


class StructureStateMachineTest(unittest.TestCase):
    def test_first_touch_is_warning_not_exit(self):
        bars = [
            bar("2026-01-01", 8, 7, 7.5), bar("2026-01-02", 10, 8, 9),
            bar("2026-01-03", 8, 5, 6), bar("2026-01-04", 9, 7, 8),
            bar("2026-01-05", 8, 6, 7), bar("2026-01-06", 7.5, 6, 6.5),
        ]
        event = structure._evaluate_setup(SETUP, bars, "2330", 0, 4.9, 4.9, "2026-01-07")
        self.assertEqual(event["state"], "STRUCTURE_WARNING")
        row = {"FinalAction": "ABSTAIN"}
        structure.apply(row, event, True)
        self.assertEqual(row["FinalAction"], "HOLD")
        self.assertEqual(row["AlertLevel"], "WARNING")

    def test_reclaim_then_rebreak_is_exit(self):
        bars = [
            bar("2026-01-01", 8, 7, 7.5), bar("2026-01-02", 10, 8, 9),
            bar("2026-01-03", 8, 5, 6), bar("2026-01-04", 9, 7, 8),
            bar("2026-01-05", 8, 6, 7),
            bar("2026-01-06", 4.9, 4.5, 4.7),
            bar("2026-01-07", 6.0, 4.8, 5.5),
            bar("2026-01-08", 5.4, 4.7, 4.9),
        ]
        event = structure._evaluate_setup(SETUP, bars, "2330", 0, None, None, "2026-01-09")
        self.assertEqual(event["state"], "STRUCTURE_EXIT_REBREAK")
        row = {"FinalAction": "HOLD"}
        structure.apply(row, event, True)
        self.assertEqual(row["FinalAction"], "EXIT_ALL")
        self.assertEqual(row["AlertLevel"], "EXIT")

    def test_failed_reclaim_then_reaction_low_break_is_exit(self):
        bars = [
            bar("2026-01-01", 8, 7, 7.5), bar("2026-01-02", 10, 8, 9),
            bar("2026-01-03", 8, 5, 6), bar("2026-01-04", 9, 7, 8),
            bar("2026-01-05", 8, 6, 7),
            bar("2026-01-06", 4.7, 4.5, 4.6),
            bar("2026-01-07", 4.6, 4.3, 4.4),
            bar("2026-01-08", 4.9, 4.4, 4.7),
            bar("2026-01-09", 4.5, 4.35, 4.4),
            bar("2026-01-10", 4.4, 4.2, 4.3),
        ]
        event = structure._evaluate_setup(SETUP, bars, "2330", 0, None, None, "2026-01-11")
        self.assertEqual(event["state"], "STRUCTURE_EXIT_FAILED_RECLAIM")
        self.assertEqual(event["reaction_low"], 4.3)


class PositionWatchTest(unittest.TestCase):
    def test_watch_adds_exit_only_held_row_without_entry_authority(self):
        unified = {"rows": [], "source_provenance_counts": {"LEGACY": 0, "Q017": 0, "BOTH": 0}}
        watch = {"schema_version": 1, "module": "HENGCE_Q017_POSITION_WATCH", "positions": [
            {"Ticker": "2330", "PositionHeld": True, "PositionEntryDate": "2026-10-01", "SourceProvenance": "Q017"}
        ]}
        out = position_watch.merge(unified, watch)
        row = out["rows"][0]
        self.assertTrue(row["PositionHeld"])
        self.assertFalse(row["FormalEntryTrigger"])
        self.assertFalse(row["FormalCandidate"])
        self.assertEqual(row["GeometryStatus"], "UNAVAILABLE")


class AlertLedgerTest(unittest.TestCase):
    def test_same_warning_dedupes_but_exit_is_new(self):
        now = datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            alerts_path = Path(tmp) / "alerts.json"
            ledger_path = Path(tmp) / "ledger.json"
            warning = {
                "rows": [{"Ticker": "2330", "AlertRequired": True, "AlertKey": "W:2330:1",
                          "AlertLevel": "WARNING", "StructureExitState": "STRUCTURE_WARNING",
                          "FinalAction": "HOLD"}],
                "trade_date": "2026-10-26", "generated_at": now.isoformat(),
            }
            a1, _ = alert_ledger.update(warning, alerts_path, ledger_path, now=now)
            a2, _ = alert_ledger.update(warning, alerts_path, ledger_path, now=now)
            self.assertEqual(a1["new_alert_count"], 1)
            self.assertEqual(a2["new_alert_count"], 0)
            exit_action = {
                "rows": [{"Ticker": "2330", "AlertRequired": True, "AlertKey": "X:2330:1",
                          "AlertLevel": "EXIT", "StructureExitState": "STRUCTURE_EXIT_REBREAK",
                          "FinalAction": "EXIT_ALL"}],
                "trade_date": "2026-10-26", "generated_at": now.isoformat(),
            }
            a3, ledger = alert_ledger.update(exit_action, alerts_path, ledger_path, now=now)
            self.assertEqual(a3["new_alert_count"], 1)
            self.assertEqual(ledger["seen_count"], 2)


if __name__ == "__main__":
    unittest.main()
