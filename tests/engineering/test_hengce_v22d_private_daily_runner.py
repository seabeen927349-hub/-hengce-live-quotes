"""Real original-vessel EOD continuation: synthetic receipts only, no downloads."""
import csv
from datetime import date, datetime, timedelta
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.hengce_v22d_private_daily_runner import (
    COLUMNS, DailyBlocked, valid_day, official_days,
    extend_original_mother, latest_original_day, read_json
)
from scripts.hengce_v22d_private_original_inference import digest

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime.fromisoformat("2026-11-12T11:10:00+08:00")
DAY = date(2026, 11, 12)


class OriginalVesselPrivateDailyRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.eod = self.root / "eod" / "20261112"
        (self.eod / "receipts").mkdir(parents=True)
        for name in ("TWSE_TRADING_CALENDAR_2026_v1.json",
                     "TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json"):
            d = self.root / "governance" / name
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_bytes((ROOT / "governance" / name).read_bytes())
        self.create_day()

    @staticmethod
    def record_sha(paths):
        h = hashlib.sha256()
        for p in sorted(paths):
            h.update(p.name.encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
        return h.hexdigest()

    def write_json(self, path, obj):
        Path(path).write_text(json.dumps(obj, sort_keys=True))
        return obj

    def create_day(self):
        rows = {}
        codes = [str(i) for i in range(1000, 1901)]
        for leg in ("price", "margin", "institutional"):
            file = self.eod / (leg + "_1.csv")
            if leg == "price":
                head = ["Date", "Ticker", "Name", "VolumeShares", "TurnoverTWD",
                        "Open", "High", "Low", "Close"]
                body = [[DAY.isoformat(), ticker, "Synthetic", 10000, 250000,
                         24, 26, 24, 25] for ticker in codes]
            elif leg == "margin":
                head = ["Date", "Ticker", "MarginBalance"]
                body = [[DAY.isoformat(), ticker, 300] for ticker in codes]
            else:
                head = ["Date", "Ticker", "ForeignNet", "TrustNet", "TotalNet"]
                body = [[DAY.isoformat(), ticker, 1000, 0, 900] for ticker in codes]
            with file.open("w", encoding="utf-8", newline="") as dest:
                writer = csv.writer(dest)
                writer.writerow(head)
                writer.writerows(body)
            sha = self.record_sha([file])
            rows[leg] = sha
            self.write_json(self.eod / "receipts" / (leg + ".json"), {
                "status": "COMPLETE", "target_date": DAY.isoformat(),
                "leg": leg, "files": [file.name], "rows": len(codes),
                "sha256": sha, "model_authority_created": False,
                "promoted_at_taipei": "2026-11-12T10:00:00+08:00"})
        self.write_json(self.eod / "receipts/mother.json", {
            "artifact": "EOD_TO_CANONICAL_HISTORICAL_MOTHER_BRIDGE_RECEIPT",
            "status": "PASS", "target_date": DAY.isoformat(),
            "mother_latest_date": DAY.isoformat(),
            "promoted_leg_sha256": rows, "mother_sha256": "f"*64,
            "integrity_status": "PASS", "model_or_schema_mutated": False,
            "second_mother": False, "three_leg_complete": True,
            "missing_evidence_is_null": True})
        self.write_json(self.eod / "status.json", {
            "status": "COMPLETE", "target_date": DAY.isoformat(),
            "three_leg_complete": True, "formal_complete_day": True,
            "downstream_ready": True, "mother_status": "COMPLETE",
            "second_mother": False, "broker_order_execution": False,
            "model_authority_created": False,
            "updated_at_taipei": "2026-11-12T10:10:00+08:00",
            "mother_sha256": "f"*64,
            **{leg + "_sha256": sha for leg, sha in rows.items()},
            **{leg + "_rows": len(codes) for leg in rows},
        })

    def test_three_original_source_receipts_produce_correct_eod_schema(self):
        rows, proof = valid_day(self.root, DAY, NOW)
        self.assertEqual(len(rows), 901)
        self.assertEqual(proof["price_rows"], 901)
        self.assertEqual(proof["margin_rows"], 901)
        self.assertEqual(proof["institutional_rows"], 901)
        self.assertEqual(list(rows[0]), COLUMNS)
        self.assertEqual(rows[0]["Ticker"], "1000")
        self.assertEqual(rows[0]["Volume"], "10000")
        self.assertEqual(rows[0]["Margin_MarginBalance"], "300")
        self.assertEqual(rows[0]["TotalNet"], "900")

    def test_any_changed_original_leg_rejects(self):
        path = self.eod / "price_1.csv"
        with path.open("a") as out:
            out.write("\n")
        with self.assertRaisesRegex(DailyBlocked, "ORIGINAL_EOD_LEG_SHA_MISMATCH:price"):
            valid_day(self.root, DAY, NOW)

    def test_missing_margin_blocks_original_three_leg(self):
        path = self.eod / "margin_1.csv"
        path.unlink()
        with self.assertRaisesRegex(DailyBlocked, "ORIGINAL_EOD_LEG_SET_INVALID:margin"):
            valid_day(self.root, DAY, NOW)

    def test_future_source_receipt_never_enters_prediction(self):
        rec = self.eod / "receipts/institutional.json"
        obj = read_json(rec)
        obj["promoted_at_taipei"] = "2026-11-12T12:00:00+08:00"
        self.write_json(rec, obj)
        with self.assertRaisesRegex(DailyBlocked, "ORIGINAL_EOD_LEG_NOT_YET_OBSERVED:institutional"):
            valid_day(self.root, DAY, NOW)

    def test_future_mother_receipt_rejected(self):
        path = self.eod / "status.json"
        obj = read_json(path)
        obj["updated_at_taipei"] = "2026-11-13T00:00:00+08:00"
        self.write_json(path, obj)
        with self.assertRaisesRegex(DailyBlocked, "ORIGINAL_EOD_RECEIPT_FROM_FUTURE"):
            valid_day(self.root, DAY, NOW)

    def test_2026_calendar_preserves_original_market_days(self):
        self.assertEqual(official_days(self.root, date(2026,11,11), DAY), [DAY])
        self.assertEqual(official_days(self.root, date(2026,10,22),
                                      date(2026,10,26)), [])

    def test_extending_original_private_mother_never_overwrites_it(self):
        original = self.root / "private_original_canonical.csv"
        sample = "2026-11-11,1000,Synthetic,10000,250000,24,26,24,25,300,1000,0,900\n"
        original.write_text(",".join(COLUMNS) + "\n" + sample*100000)
        original_sha = digest(original)
        inp, sha, proof = extend_original_mother(
            self.root, original, DAY.isoformat(), self.root / "private_work",
            baseline_sha=original_sha, observed_at=NOW)
        self.assertNotEqual(inp, original)
        self.assertEqual(digest(original), original_sha)
        self.assertNotEqual(digest(inp), original_sha)
        self.assertEqual(sha, digest(inp))
        self.assertEqual(proof[0]["date"], DAY.isoformat())
        with inp.open(encoding="utf-8") as source:
            last = list(csv.DictReader(source))[-1]
        self.assertEqual(last["Date"], DAY.isoformat())

    def test_session_not_fresh_can_not_be_selected(self):
        older = self.root / "eod" / "20261109"
        older.mkdir()
        (older/"status.json").write_text(
            json.dumps({"status":"COMPLETE","three_leg_complete":True}))
        with self.assertRaisesRegex(DailyBlocked, "NO_COMPLETED_ORIGINAL_MON_THU_EOD"):
            latest_original_day(self.root, datetime.fromisoformat("2026-11-10T11:00:00+08:00"))
        current = latest_original_day(self.root, NOW)
        self.assertEqual(current, DAY)
        with self.assertRaisesRegex(DailyBlocked,
                                    "LATEST_ORIGINAL_EOD_TOO_STALE_FOR_DAILY_REPLAY"):
            latest_original_day(self.root, datetime.fromisoformat(
                "2026-11-16T11:00:00+08:00"))


if __name__ == "__main__":
    unittest.main()
