#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("adapter", HERE / "hengce_unified_candidate_adapter.py")
adapter = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(adapter)


def canonical_q017(ticker="3008"):
    return {
        "schema_version": 1, "module": "HENGCE_CANONICAL_Q017_CANDIDATES",
        "producer": {"code_commit": "0" * 40, "input_hashes": {"synthetic": "0" * 64}},
        "generated_at": "2026-10-23T10:00:00+08:00",
        "system": "HENGCE",
        "binding_status": "PASS",
        "market_state": "GO",
        "trade_date": "2026-10-23",
        "canonical_q017_contract": dict(adapter.CANONICAL_Q017),
        "candidates": [{
            "ticker": ticker, "name": "測試", "rank": 1, "beta60": 1.10,
            "residual1": -0.02, "score": 1.65, "qualified": True,
            "filter_evidence": {"avg_turnover20": 30000000, "electronics_m1": -.01, "electronics_m5": -.03, "sox_1d": -.01, "sox_5d": -.04},
        }],
    }


def cases():
    legacy = {
        "run_id": "BASE",
        "rows": [
            {"Ticker": "2330", "AlphaScore": 0.9, "BreakoutLower": 100, "BreakoutUpper": 105, "NoChase": 110, "InvalidationPrice": 90, "FormalEntryTrigger": True},
            {"Ticker": "2454", "AlphaScore": 0.8, "FormalEntryTrigger": False},
        ],
    }

    out = adapter.build(legacy, canonical_q017("3008"))
    assert out["candidate_count"] == 3
    qrow = next(r for r in out["rows"] if r["Ticker"] == "3008")
    assert qrow["SourceProvenance"] == "Q017"
    assert qrow["GeometryStatus"] == "UNAVAILABLE"
    assert qrow["FormalEntryTrigger"] is False

    out2 = adapter.build(legacy, canonical_q017("2330"))
    assert out2["candidate_count"] == 2
    brow = next(r for r in out2["rows"] if r["Ticker"] == "2330")
    assert brow["SourceProvenance"] == "BOTH"
    assert brow["LegacyScore"] == 0.9 and brow["Q017Score"] == 1.65
    assert "UnifiedScore" not in brow and out2["score_fusion"] is False

    bad = canonical_q017("3008")
    bad["canonical_q017_contract"]["top_n"] = 3
    bad["canonical_q017_contract"]["dxy_used"] = True
    out3 = adapter.build(legacy, bad)
    assert out3["q017_contract_status"] == "FAIL_CLOSED_CONTRACT_MISMATCH"
    assert out3["candidate_count"] == 2
    assert all(r["SourceProvenance"] == "LEGACY" for r in out3["rows"])

    cash = canonical_q017("3008")
    cash["market_state"] = "CASH"
    cash["candidates"] = []
    out4 = adapter.build(legacy, cash)
    assert out4["q017_contract_status"] == "PASS"
    assert out4["candidate_count"] == 2

    out5 = adapter.build(legacy, None)
    assert out5["q017_contract_status"] == "NOT_PROVIDED"
    assert out5["candidate_count"] == 2

    print("PASS: HENGCE unified Q017 candidate integration")


def run():
    from unittest.mock import patch
    with patch.object(adapter, 'VERIFIED_Q017_PRODUCERS', frozenset({'0' * 40})):
        cases()

if __name__ == "__main__":
    run()
