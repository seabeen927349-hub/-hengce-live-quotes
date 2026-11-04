#!/usr/bin/env python3
"""Read-only Fugle / FinMind / TWSE source reconciliation for HENGCE Escape.

Consumes manually captured source excerpts. Does not fetch credentials, overwrite
canonical history, build detector packets, or grant any trading/model authority.
"""
from __future__ import annotations
import argparse
import json
from decimal import Decimal
from pathlib import Path

PRICE_FIELDS = ("open", "high", "low", "close", "volume_shares", "turnover_twd")
FLOW_FIELDS = ("foreign_net", "trust_net", "dealer_net", "total_net")


def dec(v):
    return None if v is None else Decimal(str(v))


def reconcile(snapshot):
    date = snapshot.get("observation_date")
    stocks = snapshot.get("stocks") or []
    if not date or len({s.get("ticker") for s in stocks}) != len(stocks):
        raise ValueError("INVALID_DATE_OR_DUPLICATE_TICKER")
    results = []
    for stock in stocks:
        ticker = stock["ticker"]
        fugle = stock["fugle_quote"]
        fm = stock["finmind_eod"]
        tw = stock["twse_eod"]
        if any(s.get("date") != date for s in (fugle, fm, tw)):
            raise ValueError("SOURCE_DATE_MISMATCH:" + ticker)
        sufficient = all(fm.get(k) is not None and tw.get(k) is not None
                         for k in PRICE_FIELDS)
        differences = ({k: str(dec(fm[k]) - dec(tw[k])) for k in PRICE_FIELDS}
                       if sufficient else None)
        equal_price = sufficient and all(dec(fm[k]) == dec(tw[k])
                                         for k in PRICE_FIELDS)
        quote_equal = (fugle.get("close") is not None
                       and tw.get("close") is not None
                       and dec(fugle["close"]) == dec(tw["close"]))
        price = {"eod_finmind_twse_exact": equal_price,
                 "difference_finmind_minus_twse": differences,
                 "fugle_close_matches_twse": quote_equal,
                 "fugle_quote_volume_not_authorized_as_eod": True}
        if fugle.get("trade_volume_raw") is not None and tw.get("volume_shares") is not None:
            # Provisional scale used only to diagnose scope mismatch, not as EOD data.
            quote_candidate = dec(fugle["trade_volume_raw"]) * 1000
            official = dec(tw["volume_shares"])
            price["fugle_quote_volume_x1000_candidate"] = str(quote_candidate)
            price["twse_eod_minus_quote_volume_candidate"] = str(official - quote_candidate)
            price["scope_mismatch_observed"] = quote_candidate != official
        institutional = None
        inst = stock.get("institutional_20261103")
        if inst:
            prior = inst.get("github_archived_twse_t86")
            current = inst.get("current_twse_t86")
            vendor = inst.get("finmind_t86_view")
            if prior is None or current is None:
                institutional = {"status": "INSUFFICIENT_T86_VERSIONS"}
            else:
                delta = {k: str(dec(current[k]) - dec(prior[k]))
                         for k in FLOW_FIELDS if current.get(k) is not None
                         and prior.get(k) is not None}
                mismatched = any(dec(current.get(k)) != dec(prior.get(k))
                                 for k in FLOW_FIELDS)
                vendor_equal = (None if vendor is None else
                                all(dec(vendor.get(k)) == dec(current.get(k))
                                    for k in FLOW_FIELDS))
                institutional = {
                    "status": ("HOLD_RECONCILE_NO_OVERWRITE" if mismatched
                               else "PASS_ARCHIVE_MATCHES_CURRENT"),
                    "delta_current_twse_minus_archived": delta,
                    "finmind_matches_current_twse": vendor_equal,
                    "may_overwrite_archived_evidence": False,
                }
        results.append({"ticker": ticker, "price": price,
                        "institutional": institutional})
    return {
        "schema": "HENGCE_ESCAPE_DUAL_SOURCE_RECONCILIATION_RESEARCH_V1",
        "status": "RESEARCH_SHADOW_ONLY_NO_FORMAL_AUTHORITY",
        "observation_date": date,
        "stock_count": len(results),
        "results": results,
        "all_finmind_twse_eod_price_equal":
            all(x["price"]["eod_finmind_twse_exact"] for x in results),
        "canonical_reconciliation_required":
            any(x["institutional"] is not None and
                x["institutional"].get("status") == "HOLD_RECONCILE_NO_OVERWRITE"
                for x in results),
        "feature_detector_input_authority": False,
        "formal_escape_state_authority": False,
        "selection_authority": False,
        "trading_authority": "NONE",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = reconcile(json.loads(args.snapshot.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"status": result["status"], "stocks": result["stock_count"],
                      "prices_equal": result["all_finmind_twse_eod_price_equal"],
                      "t86_reconciliation_required":
                          result["canonical_reconciliation_required"]}))


if __name__ == "__main__":
    main()
