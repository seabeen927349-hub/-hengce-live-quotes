#!/usr/bin/env python3
"""Derive frozen BROKER_GROSS_HHI_1D from one FinMind SecIdAgg day.

DATA/FEATURE VESSEL ONLY. This script never loads prices, controls, market state,
or forward returns. Raw licensed broker rows remain local to the runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

DATASET = "TaiwanStockTradingDailyReportSecIdAgg"
COLS = [
    "date",
    "stock_id",
    "securities_trader_id",
    "buy_volume",
    "sell_volume",
    "buy_price",
    "sell_price",
]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def logical_content_sha256(table) -> str:
    selected = table.select(COLS)
    sorted_table = selected.sort_by([(c, "ascending") for c in COLS])
    h = hashlib.sha256()
    h.update(("HENGCE_LOGICAL_ROW_HASH_V1\n" + "\x1f".join(COLS) + "\n").encode("utf-8"))
    for batch in sorted_table.to_batches(max_chunksize=65536):
        pycols = [batch.column(i).to_pylist() for i in range(batch.num_columns)]
        for values in zip(*pycols):
            line = json.dumps(values, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            h.update(line.encode("utf-8"))
            h.update(b"\n")
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--factor-output", required=True)
    ap.add_argument("--receipt-output", required=True)
    ap.add_argument("--transport-receipt")
    a = ap.parse_args()

    src = Path(a.parquet)
    factor_path = Path(a.factor_output)
    receipt_path = Path(a.receipt_output)
    factor_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    receipt = {
        "schema_version": 1,
        "system": "HENGCE",
        "artifact": "BROKER_GROSS_HHI_1D_DAILY_DERIVATION_RECEIPT",
        "authority": "RESEARCH_DERIVED_FEATURE_ONLY_NO_FORWARD_RETURN_NO_MODEL_AUTHORITY",
        "dataset": DATASET,
        "requested_date": a.date,
        "source_revision_class": "EVENT_DAY_FACT_RECONSTRUCTION",
        "retrieved_or_processed_at_taipei": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "feature_id": "BROKER_GROSS_HHI_1D",
        "feature_formula": "sum_b(((buy_volume_b+sell_volume_b)/sum_b(buy_volume_b+sell_volume_b))^2)",
        "feature_sign_hypothesis": "NONE_TWO_SIDED",
        "named_broker_selection": False,
        "beneficial_owner_interpretation": False,
        "smart_money_interpretation": False,
        "forward_returns_loaded": False,
        "controls_loaded": False,
        "market_state_loaded": False,
        "ranking_test_run": False,
        "threshold_tuning_run": False,
        "raw_broker_rows_persisted_by_this_script": False,
        "status": "FAIL_CLOSED",
        "errors": [],
    }

    try:
        if not src.is_file():
            raise RuntimeError("SOURCE_PARQUET_MISSING")
        receipt["source_parquet_bytes"] = src.stat().st_size
        receipt["source_parquet_sha256"] = file_sha256(src)

        pf = pq.ParquetFile(src)
        names = pf.schema_arrow.names
        missing = sorted(set(COLS) - set(names))
        if missing:
            raise RuntimeError(f"MISSING_REQUIRED_COLUMNS:{missing}")
        table = pf.read(columns=COLS)
        if table.num_rows == 0:
            raise RuntimeError("EMPTY_SOURCE")
        receipt["source_row_count"] = int(table.num_rows)
        receipt["source_row_group_count"] = int(pf.metadata.num_row_groups)
        receipt["source_logical_content_sha256"] = logical_content_sha256(table)

        dates = {str(x) for x in pc.unique(table["date"]).to_pylist() if x is not None}
        if dates != {a.date}:
            raise RuntimeError(f"SOURCE_DATE_MISMATCH:{sorted(dates)}")

        df = table.to_pandas()
        # IDs are semantic keys; null/blank IDs fail closed.
        for c in ("stock_id", "securities_trader_id"):
            if df[c].isna().any() or (df[c].astype(str).str.strip() == "").any():
                raise RuntimeError(f"INVALID_NULL_OR_BLANK_KEY:{c}")
            df[c] = df[c].astype(str).str.strip()

        dup = df.duplicated(["date", "stock_id", "securities_trader_id"], keep=False)
        if dup.any():
            receipt["duplicate_key_row_count"] = int(dup.sum())
            raise RuntimeError("UNEXPECTED_DUPLICATE_DATE_STOCK_BROKER_KEY")
        receipt["duplicate_key_row_count"] = 0

        for c in ("buy_volume", "sell_volume"):
            x = pd.to_numeric(df[c], errors="coerce")
            if x.isna().any():
                raise RuntimeError(f"NONNUMERIC_OR_NULL_VOLUME:{c}")
            if (~x.map(math.isfinite)).any():
                raise RuntimeError(f"NONFINITE_VOLUME:{c}")
            if (x < 0).any():
                raise RuntimeError(f"NEGATIVE_VOLUME:{c}")
            df[c] = x.astype("float64")

        df["gross"] = df["buy_volume"] + df["sell_volume"]
        grouped = df.groupby("stock_id", sort=True, observed=True)
        sum_gross = grouped["gross"].sum()
        sum_sq = grouped["gross"].apply(lambda s: float((s * s).sum()))
        branch_count = grouped["securities_trader_id"].nunique()
        bad_total = sum_gross <= 0
        if bad_total.any():
            receipt["zero_or_negative_gross_stock_count"] = int(bad_total.sum())
            raise RuntimeError("ZERO_OR_NEGATIVE_STOCK_GROSS_TOTAL")
        receipt["zero_or_negative_gross_stock_count"] = 0

        hhi = (sum_sq / (sum_gross * sum_gross)).rename("BROKER_GROSS_HHI_1D")
        out = pd.concat([hhi, branch_count.rename("broker_branch_count")], axis=1).reset_index()
        out.insert(0, "date", a.date)
        if out["BROKER_GROSS_HHI_1D"].isna().any() or (~out["BROKER_GROSS_HHI_1D"].map(math.isfinite)).any():
            raise RuntimeError("NONFINITE_HHI")
        if ((out["BROKER_GROSS_HHI_1D"] <= 0) | (out["BROKER_GROSS_HHI_1D"] > 1)).any():
            raise RuntimeError("HHI_OUT_OF_RANGE")

        # Deterministic derived factor bytes; no raw broker rows are written.
        out = out.sort_values(["date", "stock_id"], kind="mergesort").reset_index(drop=True)
        csv_bytes = out.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")
        factor_path.write_bytes(csv_bytes)

        receipt.update({
            "unique_stock_count": int(df["stock_id"].nunique()),
            "unique_broker_id_count": int(df["securities_trader_id"].nunique()),
            "derived_factor_row_count": int(len(out)),
            "derived_factor_sha256": sha256_bytes(csv_bytes),
            "hhi_min": float(out["BROKER_GROSS_HHI_1D"].min()),
            "hhi_max": float(out["BROKER_GROSS_HHI_1D"].max()),
            "status": "PASS_DERIVED_FEATURE_LINEAGE_ONLY",
        })

        if a.transport_receipt:
            tr = Path(a.transport_receipt)
            if not tr.is_file():
                raise RuntimeError("TRANSPORT_RECEIPT_MISSING")
            trobj = json.loads(tr.read_text(encoding="utf-8"))
            if trobj.get("requested_date") != a.date:
                raise RuntimeError("TRANSPORT_RECEIPT_DATE_MISMATCH")
            if trobj.get("raw_sha256") and trobj["raw_sha256"] != receipt["source_parquet_sha256"]:
                raise RuntimeError("TRANSPORT_SOURCE_SHA_MISMATCH")
            receipt["transport_receipt"] = trobj
    except Exception as exc:
        receipt["errors"].append(f"{type(exc).__name__}:{exc}")
        # A failed day must not leave a seemingly valid factor file behind.
        if factor_path.exists():
            factor_path.unlink()
        receipt["status"] = "FAIL_CLOSED"

    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["status"] == "PASS_DERIVED_FEATURE_LINEAGE_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
