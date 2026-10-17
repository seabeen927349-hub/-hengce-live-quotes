import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("HENGCE_MICROSTRUCTURE_FEATURES_v0_2.py")
SPEC = importlib.util.spec_from_file_location("q012_features", MODULE_PATH)
features = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(features)


def book(time, bid=99.0, ask=101.0, bid_size=10.0, ask_size=5.0):
    return (time, "books", {
        "symbol": "2330", "time": int(time * 1_000_000),
        "bids": [{"price": bid, "size": bid_size}],
        "asks": [{"price": ask, "size": ask_size}],
    }, True)


def trade(time, price=101.0, bid=99.0, ask=101.0, size=2.0, serial="1"):
    return (time, "trades", {
        "symbol": "2330", "time": int(time * 1_000_000),
        "price": price, "bid": bid, "ask": ask, "size": size, "serial": serial,
    }, True)


class MicrostructureFeatureIntegrityTests(unittest.TestCase):
    def test_empty_book_invalidates_prior_depth(self):
        empty=(1.05,"books",{"symbol":"2330","time":1050000,"bids":[],"asks":[]},True)
        row=features.compute([book(1.0),empty,trade(1.1)])[0]
        self.assertEqual(row["book_feature_status"],"INVALID_BOOK")
        self.assertIsNone(row["obi5"])
        self.assertEqual(row["book_time"],1.05)

    def test_crossed_negative_nonfinite_and_zero_size_books_rejected(self):
        bad=[book(1,bid=102,ask=101),book(1,bid_size=-1),book(1,bid_size=float("nan")),book(1,bid_size=0,ask_size=0)]
        for invalid in bad:
            with self.subTest(invalid=invalid):
                row=features.compute([invalid,trade(1.1)])[0]
                self.assertEqual(row["book_feature_status"],"INVALID_BOOK")
                self.assertIsNone(row["microprice"])

    def test_aligned_quote_emits_depth_features_and_age(self):
        rows = features.compute([book(1.0), trade(1.1)])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["book_feature_status"], "TOP_OF_BOOK_MATCH")
        self.assertAlmostEqual(row["book_age_ms"], 100.0)
        self.assertAlmostEqual(row["obi5"], (10 - 5) / (10 + 5))
        self.assertEqual(row["aggressor"], 1)

    def test_quote_mismatch_suppresses_all_book_features_but_keeps_trade(self):
        rows = features.compute([book(1.0, bid=99.0, ask=101.0), trade(1.1, bid=100.0, ask=102.0, price=102.0)])
        row = rows[0]
        self.assertEqual(row["book_feature_status"], "TOP_OF_BOOK_MISMATCH")
        self.assertFalse(row["book_quote_match"])
        self.assertIsNone(row["obi5"])
        self.assertIsNone(row["microprice"])
        self.assertEqual(row["aggressor"], 1)
        self.assertEqual(row["ati_30s"], 1.0)

    def test_trade_without_prior_book_is_retained_in_denominator(self):
        rows = features.compute([trade(1.1)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["book_feature_status"], "NO_PRIOR_BOOK")
        self.assertIsNone(rows[0]["obi5"])
        self.assertEqual(features.summarize(rows)["trade_rows"], 1)
        self.assertEqual(features.summarize(rows)["aligned_book_rows"], 0)

    def test_trade_does_not_borrow_another_symbols_book(self):
        other = book(1.0)
        other[2]["symbol"] = "2317"
        row = features.compute([other, trade(1.1)])[0]
        self.assertEqual(row["book_feature_status"], "NO_PRIOR_BOOK")
        self.assertIsNone(row["book_time"])

    def test_missing_trade_quote_does_not_claim_book_alignment(self):
        event = trade(1.1)
        event[2].pop("bid")
        event[2].pop("ask")
        row = features.compute([book(1.0), event])[0]
        self.assertEqual(row["book_feature_status"], "TRADE_QUOTE_MISSING")
        self.assertIsNone(row["book_quote_match"])
        self.assertIsNone(row["obi5"])

    def test_conflicting_same_timestamp_books_are_flagged_deterministically(self):
        first = book(1.0, bid_size=10.0)
        second = book(1.0, bid_size=20.0)
        t = trade(1.0)
        with tempfile.TemporaryDirectory() as temp:
            paths = []
            for name, row in [("a.ndjson", first), ("b.ndjson", second), ("c.ndjson", t)]:
                path = Path(temp) / name
                time_s, channel, payload, valid = row
                record = {"channel": channel, "validContinuous": valid, "payload": payload}
                path.write_text(json.dumps(record) + "\n", encoding="utf-8")
                paths.append(str(path))
            result_a = features.compute(features.load(paths))
            result_b = features.compute(features.load(list(reversed(paths))))
        self.assertEqual(result_a, result_b)
        self.assertEqual(result_a[0]["book_feature_status"], "AMBIGUOUS_SAME_TIMESTAMP_BOOK")
        self.assertIsNone(result_a[0]["obi5"])

    def test_invalid_nonfinite_trade_price_serializes_as_strict_json_null(self):
        event = trade(1.1)
        event[2]["price"] = float("nan")
        row = features.compute([event])[0]
        self.assertIsNone(row["trade_price"])
        json.dumps(row, allow_nan=False)

    def test_require_aligned_fails_closed_but_preserves_diagnostic_output(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            book_record = {"channel": "books", "payload": book(1.0)[2]}
            trade_record = {"channel": "trades", "payload": trade(1.1, bid=100.0, ask=102.0, price=102.0)[2]}
            raw = base / "raw.ndjson"
            raw.write_text("\n".join(json.dumps(x) for x in (book_record, trade_record)) + "\n", encoding="utf-8")
            output = base / "features.ndjson"
            summary = base / "features.ndjson.summary.json"
            result = subprocess.run(
                [sys.executable, str(MODULE_PATH), str(raw), "--out", str(output), "--require-aligned"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 12)
            self.assertIn("QUALITY_FAIL_NO_ALIGNED_BOOK_ROWS", result.stdout)
            saved_summary = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(saved_summary["trade_rows"], 1)
            self.assertEqual(saved_summary["aligned_book_rows"], 0)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["book_feature_status"], "TOP_OF_BOOK_MISMATCH")


if __name__ == "__main__":
    unittest.main()
