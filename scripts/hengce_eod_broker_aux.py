#!/usr/bin/env python3
"""Broker HHI research auxiliary for the EXISTING HENGCE eod/YYYYMMDD vessel.

This module is not a collector/vessel on its own. It is called only by the
governed `HENGCE original EOD ingest` workflow after the original three-leg
ingest. It writes only derived HHI + lineage receipt into the same eod date
directory and updates that date's existing status.json.

Hard boundary:
- no parallel EOD tree
- no second mother
- no parallel universe
- no historical backfill relabeled prospective
- no raw licensed Broker rows persisted
- no model/trading/capital authority
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import hengce_daily_command_center_core_legacy as core

DATASET = "TaiwanStockTradingDailyReportSecIdAgg"
SOURCE_PLAN = "SponsorPro"
SOURCE_REVISION_CLASS = "FORWARD_COLLECTED_VENDOR_SNAPSHOT"
EXPECTED_COLS = [
    "date", "stock_id", "securities_trader_id",
    "buy_volume", "sell_volume", "buy_price", "sell_price",
]
DERIVED_FILE = "broker_hhi.csv"
RECEIPT_FILE = Path("receipts") / "broker_hhi.json"
RELEASE_HHMM = (18, 30)
VESSEL_GOVERNANCE = "ALL_NEW_DATA_ATTACH_TO_EXISTING_GOVERNED_HENGCE_VESSEL_NO_PARALLEL_COLLECTOR"


class NotReady(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_stock_id(x) -> str:
    s = str(x).strip()
    if re.fullmatch(r"\d+(?:\.0+)?", s):
        s = s.split(".")[0]
        if len(s) <= 4:
            return s.zfill(4)
    return s


def canonical_scalar(v):
    try:
        import numpy as np
        if isinstance(v, np.generic):
            return canonical_scalar(v.item())
    except Exception:
        pass
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v):
            return {"__nonfinite__": "NaN"}
        if math.isinf(v):
            return {"__nonfinite__": "+Inf" if v > 0 else "-Inf"}
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, bytes):
        return {"__bytes_hex__": v.hex()}
    return v


def logical_content_sha256(table) -> str:
    selected = table.select(EXPECTED_COLS)
    selected = selected.sort_by([(c, "ascending") for c in EXPECTED_COLS])
    h = hashlib.sha256()
    h.update(("HENGCE_LOGICAL_ROW_HASH_V2_NONFINITE_CANONICAL\n" + "\x1f".join(EXPECTED_COLS) + "\n").encode())
    for batch in selected.to_batches(max_chunksize=65536):
        cols = [batch.column(i).to_pylist() for i in range(batch.num_columns)]
        for vals in zip(*cols):
            row = [canonical_scalar(v) for v in vals]
            h.update(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())
            h.update(b"\n")
    return h.hexdigest()


def load_status(eod_dir: Path, iso: str) -> dict:
    p = eod_dir / "status.json"
    if not p.is_file():
        raise RuntimeError("ORIGINAL_EOD_STATUS_MISSING")
    st = json.loads(p.read_text(encoding="utf-8"))
    if st.get("target_date") != iso:
        raise RuntimeError("ORIGINAL_EOD_STATUS_DATE_MISMATCH")
    if st.get("artifact") != "EOD_ORIGINAL_VESSEL_INCREMENTAL_INGEST":
        raise RuntimeError("NOT_ORIGINAL_EOD_VESSEL")
    if st.get("parallel_eod_tree") is not False or st.get("second_mother") is not False:
        raise RuntimeError("ORIGINAL_VESSEL_GOVERNANCE_INVALID")
    return st


def save_status(eod_dir: Path, st: dict) -> None:
    st["data_vessel_governance"] = VESSEL_GOVERNANCE
    st["parallel_eod_tree"] = False
    st["second_mother"] = False
    st["parallel_universe"] = False
    st["broker_hhi_blocks_core_three_leg_or_mother"] = False
    st["broker_hhi_model_authority_created"] = False
    st["broker_hhi_trading_authority_created"] = False
    st["broker_hhi_capital_authority_created"] = False
    st["broker_order_execution"] = False
    st["updated_at_taipei"] = core.now_tw().isoformat()
    core.atomic_json(eod_dir / "status.json", st)


def existing_complete(eod_dir: Path, iso: str):
    rp = eod_dir / RECEIPT_FILE
    dp = eod_dir / DERIVED_FILE
    if not rp.exists() and not dp.exists():
        return None
    if not rp.exists() or not dp.exists():
        raise RuntimeError("BROKER_IMMUTABLE_PAIR_INCOMPLETE")
    rec = json.loads(rp.read_text(encoding="utf-8"))
    if rec.get("status") != "COMPLETE" or rec.get("event_date") != iso:
        raise RuntimeError("BROKER_EXISTING_RECEIPT_INVALID")
    actual = sha256_file(dp)
    if actual != rec.get("derived_hhi_sha256"):
        raise RuntimeError("BROKER_DERIVED_HASH_MISMATCH")
    return rec


async def download_raw(event_date: str, raw_path: Path) -> None:
    from finmind_mcp.client import FinMindClient
    client = FinMindClient()
    signed_url = await client.storage_object_url(DATASET, event_date)
    await client.download(signed_url, raw_path)


def derive_hhi(table, iso: str):
    import numpy as np
    import pandas as pd

    pdf = table.to_pandas()
    pdf["stock_norm"] = pdf["stock_id"].map(normalize_stock_id)
    pdf["trader_norm"] = pdf["securities_trader_id"].astype("string").str.strip()
    pdf["buy_num"] = pd.to_numeric(pdf["buy_volume"], errors="coerce")
    pdf["sell_num"] = pd.to_numeric(pdf["sell_volume"], errors="coerce")

    dup = pdf.duplicated(["date", "stock_id", "securities_trader_id"], keep=False)
    buy = pdf["buy_num"].to_numpy(float)
    sell = pdf["sell_num"].to_numpy(float)
    bad_vol = (~np.isfinite(buy)) | (~np.isfinite(sell)) | (buy < 0) | (sell < 0)
    bad_id = pdf["securities_trader_id"].isna() | pdf["trader_norm"].isna() | (pdf["trader_norm"] == "")

    bad_stocks = set(pdf.loc[dup | bad_vol | bad_id, "stock_norm"].astype(str))
    candidates = pdf[~pdf["stock_norm"].isin(bad_stocks)].copy()
    candidates["gross"] = candidates["buy_num"] + candidates["sell_num"]

    rows = []
    zero_total = 0
    for ticker, g0 in candidates.groupby("stock_norm", sort=True):
        ticker = str(ticker)
        if not re.fullmatch(r"[1-9]\d{3}", ticker):
            continue
        g = g0[g0["gross"] > 0]
        total = float(g["gross"].sum()) if not g.empty else 0.0
        if not np.isfinite(total) or total <= 0:
            zero_total += 1
            continue
        hhi = float(((g["gross"] / total) ** 2).sum())
        if not np.isfinite(hhi) or not (0.0 < hhi <= 1.0 + 1e-12):
            bad_stocks.add(ticker)
            continue
        rows.append({
            "Date": iso,
            "Ticker": ticker,
            "BROKER_GROSS_HHI_1D": format(hhi, ".17g"),
        })

    audit = {
        "invalid_duplicate_stock_count": len(set(pdf.loc[dup, "stock_norm"].astype(str))),
        "invalid_volume_stock_count": len(set(pdf.loc[bad_vol, "stock_norm"].astype(str))),
        "invalid_identity_stock_count": len(set(pdf.loc[bad_id, "stock_norm"].astype(str))),
        "zero_total_gross_stock_count": zero_total,
        "unique_stock_id_count": int(pdf["stock_norm"].nunique(dropna=True)),
        "unique_securities_trader_id_count": int(pdf["trader_norm"].nunique(dropna=True)),
    }
    return rows, audit


def write_derived(path: Path, rows: list[dict]) -> str:
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Date", "Ticker", "BROKER_GROSS_HHI_1D"])
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)
    return sha256_file(path)


def capture(eod_dir: Path, target: date) -> dict:
    iso = target.isoformat()
    st = load_status(eod_dir, iso)

    old = existing_complete(eod_dir, iso)
    if old:
        st.update({
            "broker_hhi_status": "COMPLETE",
            "broker_hhi_date": iso,
            "broker_hhi_rows": old.get("derived_hhi_row_count"),
            "broker_hhi_sha256": old.get("derived_hhi_sha256"),
            "broker_hhi_receipt": str(RECEIPT_FILE),
            "broker_hhi_source_revision_class": old.get("source_revision_class"),
            "broker_hhi_last_result": "ALREADY_COMPLETE_IMMUTABLE",
        })
        st.pop("broker_hhi_pending_reason", None)
        st.pop("broker_hhi_error", None)
        save_status(eod_dir, st)
        return st

    now = core.now_tw()
    try:
        if target != now.date():
            raise NotReady("BROKER_PROSPECTIVE_BACKFILL_FORBIDDEN")
        if (now.hour, now.minute) < RELEASE_HHMM:
            raise NotReady("BROKER_SOURCE_BEFORE_1830_TAIPEI")
        if not os.environ.get("FINMIND_TOKEN"):
            raise NotReady("BROKER_FINMIND_TOKEN_MISSING")

        import pyarrow.compute as pc
        import pyarrow.parquet as pq

        retrieval_utc = datetime.now(timezone.utc).isoformat()
        retrieval_taipei = now.isoformat()

        with tempfile.TemporaryDirectory(prefix="hengce-original-vessel-broker-") as td:
            raw = Path(td) / f"{iso}.parquet"
            try:
                asyncio.run(download_raw(iso, raw))
            except Exception as exc:
                raise NotReady(f"BROKER_SOURCE_NOT_READY:{type(exc).__name__}:{exc}") from exc
            if not raw.is_file() or raw.stat().st_size <= 0:
                raise NotReady("BROKER_SOURCE_OBJECT_UNAVAILABLE")

            physical_sha = sha256_file(raw)
            pf = pq.ParquetFile(raw)
            schema_fields = pf.schema_arrow.names
            missing = sorted(set(EXPECTED_COLS) - set(schema_fields))
            if missing:
                raise RuntimeError(f"BROKER_MISSING_REQUIRED_SCHEMA:{missing}")
            table = pf.read(columns=EXPECTED_COLS)
            if table.num_rows <= 0:
                raise RuntimeError("BROKER_EMPTY_SOURCE_OBJECT")
            observed_dates = {str(x) for x in pc.unique(table["date"]).to_pylist() if x is not None}
            if observed_dates != {iso}:
                raise RuntimeError(f"BROKER_SOURCE_DATE_MISMATCH:{sorted(observed_dates)}")

            logical_sha = logical_content_sha256(table)
            rows, audit = derive_hhi(table, iso)
            if not rows:
                raise RuntimeError("BROKER_NO_VALID_DERIVED_HHI_ROWS")
            derived_sha = write_derived(eod_dir / DERIVED_FILE, rows)

            receipt = {
                "system": "HENGCE",
                "artifact": "EOD_ORIGINAL_VESSEL_BROKER_HHI_AUXILIARY_RECEIPT",
                "status": "COMPLETE",
                "authority": "RESEARCH_SOURCE_VINTAGE_ONLY_NO_MODEL_TRADING_OR_CAPITAL_AUTHORITY",
                "target_date": iso,
                "dataset": DATASET,
                "event_date": iso,
                "retrieval_timestamp_utc": retrieval_utc,
                "retrieval_timestamp_taipei": retrieval_taipei,
                "query_or_download_mode": "FinMindClient.storage_object_url whole-day parquet",
                "source_plan": SOURCE_PLAN,
                "row_count": int(table.num_rows),
                "unique_stock_id_count": audit["unique_stock_id_count"],
                "unique_securities_trader_id_count": audit["unique_securities_trader_id_count"],
                "physical_object_sha256": physical_sha,
                "logical_content_sha256": logical_sha,
                "schema_field_list": schema_fields,
                "source_revision_class": SOURCE_REVISION_CLASS,
                "feature_id": "BROKER_GROSS_HHI_1D",
                "feature_formula": "sum_b ((buy_volume_b+sell_volume_b)/sum_b(buy_volume_b+sell_volume_b))^2",
                "derived_hhi_file": DERIVED_FILE,
                "derived_hhi_row_count": len(rows),
                "derived_hhi_sha256": derived_sha,
                **{k: audit[k] for k in (
                    "invalid_duplicate_stock_count",
                    "invalid_volume_stock_count",
                    "invalid_identity_stock_count",
                    "zero_total_gross_stock_count",
                )},
                "raw_broker_rows_persisted": False,
                "signed_url_persisted": False,
                "token_persisted": False,
                "immutable_first_observed": True,
                "same_vessel_path": f"eod/{target.strftime('%Y%m%d')}",
                "data_vessel_governance": VESSEL_GOVERNANCE,
                "parallel_eod_tree": False,
                "second_mother": False,
                "parallel_universe": False,
                "blocks_core_three_leg_or_mother": False,
                "model_authority_created": False,
                "trading_authority_created": False,
                "capital_authority_created": False,
                "earliest_feature_use": "next TWSE open after event date d",
            }
            core.atomic_json(eod_dir / RECEIPT_FILE, receipt)

        st.update({
            "broker_hhi_status": "COMPLETE",
            "broker_hhi_date": iso,
            "broker_hhi_rows": len(rows),
            "broker_hhi_sha256": derived_sha,
            "broker_hhi_receipt": str(RECEIPT_FILE),
            "broker_hhi_source_revision_class": SOURCE_REVISION_CLASS,
            "broker_hhi_last_result": "PROMOTED_SAME_ORIGINAL_VESSEL_RESEARCH_AUXILIARY",
        })
        st.pop("broker_hhi_pending_reason", None)
        st.pop("broker_hhi_error", None)
    except NotReady as exc:
        st["broker_hhi_status"] = "PENDING"
        st["broker_hhi_pending_reason"] = str(exc)
        st["broker_hhi_last_result"] = "PENDING_RESEARCH_AUXILIARY"
        st.pop("broker_hhi_error", None)
    except Exception as exc:
        st["broker_hhi_status"] = "ERROR"
        st["broker_hhi_error"] = f"{type(exc).__name__}:{exc}"
        st["broker_hhi_last_result"] = "ERROR_RESEARCH_AUXILIARY_ONLY"
        st.pop("broker_hhi_pending_reason", None)

    save_status(eod_dir, st)
    return st


def self_test() -> None:
    assert SOURCE_REVISION_CLASS == "FORWARD_COLLECTED_VENDOR_SNAPSHOT"
    assert VESSEL_GOVERNANCE.endswith("NO_PARALLEL_COLLECTOR")
    print(json.dumps({
        "self_test": "PASS",
        "same_original_eod_vessel_only": True,
        "parallel_collector_allowed": False,
        "second_mother": False,
        "parallel_universe": False,
        "raw_broker_rows_persisted": False,
        "blocks_core_three_leg_or_mother": False,
        "model_authority_created": False,
    }, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("capture", "self-test"), required=True)
    ap.add_argument("--date")
    ap.add_argument("--eod-dir")
    args = ap.parse_args()
    if args.mode == "self-test":
        self_test()
        return 0
    if not args.date or not args.eod_dir:
        raise SystemExit("--date and --eod-dir are required for capture")
    target = date.fromisoformat(args.date)
    result = capture(Path(args.eod_dir), target)
    print(json.dumps({
        "target_date": result.get("target_date"),
        "broker_hhi_status": result.get("broker_hhi_status"),
        "broker_hhi_rows": result.get("broker_hhi_rows"),
        "broker_hhi_pending_reason": result.get("broker_hhi_pending_reason"),
        "three_leg_complete": result.get("three_leg_complete"),
        "mother_status": result.get("mother_status"),
        "downstream_ready": result.get("downstream_ready"),
        "parallel_eod_tree": result.get("parallel_eod_tree"),
        "second_mother": result.get("second_mother"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
