#!/usr/bin/env python3
"""Network-free tests for current official TWSE / TPEx / Emerging membership."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_finmind_single_name_membership import (
    _issuer_codes, current_official_quote_membership,
)

TWSE={str(code) for code in range(1000,2000)}
TPEX={str(code) for code in range(3000,3800)}
EMERGING={str(code) for code in range(7000,7100)}

class OfficialMembershipTests(unittest.TestCase):
    def test_three_venues_no_historical_guessing(self):
        def rosters(board):
            return (TPEX, "TPEx_OPENAPI") if board=="O" else (EMERGING,"TPEx_MOPS_OFFICIAL_CSV")
        with patch("hengce_finmind_single_name_membership._fetch_roster",side_effect=rosters):
            current, meta=current_official_quote_membership(TWSE)
        self.assertEqual(current["3420"],"tpex")
        self.assertEqual(current["3042"],"tpex")
        self.assertEqual(current["7888"] if "7888" in current else current["7001"],"emerging")
        self.assertEqual(meta["twse"],1000)
        self.assertEqual(meta["tpex"],800)
        self.assertEqual(meta["emerging"],100)
        self.assertFalse(meta["membership_rows_persisted"])

    def test_block_duplicate_current_ids(self):
        with patch("hengce_finmind_single_name_membership._fetch_roster",side_effect=[(TPEX|{"1101"},"OPENAPI"),(EMERGING,"OPENAPI")]):
            with self.assertRaisesRegex(RuntimeError,"DUPLICATE_IDS"):
                current_official_quote_membership(TWSE)

    def test_block_unavailable_issuer_source(self):
        with patch("hengce_finmind_single_name_membership._fetch_roster",side_effect=RuntimeError("UNAVAILABLE")):
            with self.assertRaisesRegex(RuntimeError,"UNAVAILABLE"):
                current_official_quote_membership(TWSE)

    def test_issuer_filters_receipts_and_zero_shares(self):
        rows=[
            {"公司代號":"3420","公司簡稱":"A","產業別":"24"},
            {"公司代號":"3421","公司簡稱":"B","產業別":"24","已發行普通股數或TDR原股發行股數":"0"},
            {"公司代號":"3422","公司簡稱":"TEST-DR","產業別":"24"},
            {"公司代號":"3423","公司簡稱":"X","產業別":"91"},
            {"公司代號":"9X24","公司簡稱":"X","產業別":"24"},
        ]
        self.assertEqual(_issuer_codes(rows),{"3420"})

if __name__=="__main__":
    unittest.main()
