#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DATASET = "TaiwanStockTradingDailyReportSecIdAgg"
SOURCE_PLAN = "SponsorPro"
SOURCE_CLASS = "FORWARD_COLLECTED_VENDOR_SNAPSHOT"
EXPECTED_COLS = [
    "date",
    "stock_id",
    "securities_trader_id",
    "buy_volume",
    "sell_volume",
    "buy_price",
    "sell_price",
]
TZ = ZoneInfo("Asia/Taipei")
ROOT = Path("research/broker_prospective_20261103/captures")
NOT_BEFORE = time(18, 30)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_scalar(v):
    if v is None:
        return None
    if isinstance(v, np.generic):
        return _canonical_scalar(v.item())
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
    sorted_table = selected.sort_by([(c, "ascending") for c in EXPECTED_COLS])
    h = hashlib.sha256()
    h.update(("HENGCE_LOGICAL_ROW_HASH_V2_NONFINITE_CANONICAL\n" + "\x1f".join(EXPECTED_COLS) + "\n").encode())
    for batch in sorted_table.to_batches(max_chunksize=65536):
        pycols = [batch.column(i).to_pylist() for i in range(batch.num_columns)]
        for vals in zip(*pycols):
            canonical = [_canonical_scalar(v) for v in vals]
            h.update(json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())
            h.update(b"\n")
    return h.hexdigest()


def norm_stock(x) -> str:
    s = str(x).strip()
    if re.fullmatch(r"\d+(?:\.0+)?", s):
        s = s.split(".")[0]
        if len(s) <= 4:
            return s.zfill(4)
    return s


def build_stock_panel(pdf: pd.DataFrame) -> pd.DataFrame:
    p = pdf.copy()
    p["stock_norm"] = p["stock_id"].map(norm_stock)
    p["trader_norm"] = p["securities_trader_id"].astype("string").str.strip()
    p["buy_num"] = pd.to_numeric(p["buy_volume"], errors="coerce")
    p["sell_num"] = pd.to_numeric(p["sell_volume"], errors="coerce")

    duplicate = p.duplicated(["date", "stock_id", "securities_trader_id"], keep=False)
    bad_volume = (
        ~np.isfinite(p["buy_num"].to_numpy(float))
        | ~np.isfinite(p["sell_num"].to_numpy(float))
        | (p["buy_num"].to_numpy(float) < 0)
        | (p["sell_num"].to_numpy(float) < 0)
    )
    bad_identity = p["securities_trader_id"].isna() | p["trader_norm"].isna() | (p["trader_norm"] == "")

    rows = []
    for stock, g in p.groupby("stock_norm", sort=True, dropna=False):
        stock = str(stock)
        reasons = []
        idx = g.index
        if duplicate.loc[idx].any():
            reasons.append("DUPLICATE_KEY")
        if bool(np.asarray(bad_volume)[p.index.get_indexer(idx)].any()):
            reasons.append("INVALID_VOLUME")
        if bad_identity.loc[idx].any():
            reasons.append("INVALID_IDENTITY")

        hhi = None
        branch_count = None
        if not reasons:
            gg = g.copy()
            gg["gross"] = gg["buy_num"] + gg["sell_num"]
            gg = gg[gg["gross"] > 0]
            total = float(gg["gross"].sum()) if not gg.empty else 0.0
            if not np.isfinite(total) or total <= 0:
                reasons.append("ZERO_TOTAL_GROSS_VOLUME")
            else:
                hhi = float(((gg["gross"] / total) ** 2).sum())
                branch_count = int(len(gg))
                if not np.isfinite(hhi) or not (0.0 < hhi <= 1.0 + 1e-12):
                    reasons.append("HHI_RANGE_INVALID")
                    hhi = None
                    branch_count = None

        rows.append(
            {
                "stock_id": stock,
                "status": "PASS" if not reasons else "+".join(reasons),
                "broker_gross_hhi_1d": hhi,
                "positive_gross_branch_count": branch_count,
            }
        )
    out = pd.DataFrame(rows).sort_values("stock_id", kind="stable").reset_index(drop=True)
    return out


async def main() -> int:
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    from finmind_mcp.client import FinMindClient

    now_tpe = datetime.now(TZ)
    if now_tpe.time() < NOT_BEFORE:
        raise RuntimeError(f"TOO_EARLY_FOR_SAME_DAY_CAPTURE:{now_tpe.isoformat()}")
    event_date = now_tpe.date().isoformat()
    out_dir = ROOT / event_date
    receipt_path = out_dir / "lineage_receipt.json"
    panel_path = out_dir / "broker_hhi_all_stock.csv"

    if receipt_path.exists() or panel_path.exists():
        if not (receipt_path.exists() and panel_path.exists()):
            raise RuntimeError("PARTIAL_EXISTING_CAPTURE_FAIL_CLOSED")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        panel_sha = sha256_file(panel_path)
        if receipt.get("derived_panel_sha256") != panel_sha:
            raise RuntimeError("EXISTING_CAPTURE_HASH_MISMATCH")
        print(json.dumps({"status": "ALREADY_CAPTURED_IMMUTABLE", "event_date": event_date, "derived_panel_sha256": panel_sha}))
        return 0

    token = os.environ.get("FINMIND_TOKEN")
    if not token:
        raise RuntimeError("FINMIND_TOKEN_MISSING")

    retrieval_utc = datetime.now(timezone.utc).isoformat()
    retrieval_tpe = datetime.now(TZ).isoformat()
    client = FinMindClient()

    with tempfile.TemporaryDirectory(prefix="hengce-broker-prospective-") as td0:
        td = Path(td0)
        raw = td / f"{event_date}.parquet"
        last_exc = None
        for attempt in range(6):
            try:
                signed = await client.storage_object_url(DATASET, event_date)
                await client.download(signed, raw)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(min(60.0, 5.0 * (2 ** attempt)))
        if last_exc is not None or not raw.is_file():
            raise RuntimeError(f"SOURCE_UNAVAILABLE:{type(last_exc).__name__}:{last_exc}")

        physical_sha = sha256_file(raw)
        physical_bytes = raw.stat().st_size
        pf = pq.ParquetFile(raw)
        schema_fields = pf.schema_arrow.names
        missing_cols = sorted(set(EXPECTED_COLS) - set(schema_fields))
        if missing_cols:
            raise RuntimeError(f"MISSING_REQUIRED_SCHEMA:{missing_cols}")
        table = pf.read(columns=EXPECTED_COLS)
        if table.num_rows <= 0:
            raise RuntimeError("EMPTY_SOURCE_OBJECT")
        observed_dates = {str(x) for x in pc.unique(table["date"]).to_pylist() if x is not None}
        if observed_dates != {event_date}:
            raise RuntimeError(f"SOURCE_DATE_MISMATCH:{sorted(observed_dates)}")

        logical_sha = logical_content_sha256(table)
        pdf = table.to_pandas()
        panel = build_stock_panel(pdf)
        if panel.empty:
            raise RuntimeError("EMPTY_DERIVED_PANEL")

        out_dir.mkdir(parents=True, exist_ok=False)
        tmp_panel = out_dir / ".broker_hhi_all_stock.csv.tmp"
        panel.to_csv(tmp_panel, index=False, lineterminator="\n")
        tmp_panel.replace(panel_path)
        panel_sha = sha256_file(panel_path)

        valid = panel[panel["status"] == "PASS"]
        receipt = {
            "system": "HENGCE",
            "artifact": "BROKER_PROSPECTIVE_FIRST_OBSERVED_SOURCE_RECEIPT",
            "status": "PASS_FIRST_OBSERVED_SOURCE_CAPTURE_SOURCE_ONLY",
            "authority": "SOURCE_VINTAGE_AND_DERIVED_FEATURE_ONLY; NOT_YET_JUDGE_READY; NO_TRADING_OR_PRODUCTION_AUTHORITY",
            "dataset": DATASET,
            "event_date": event_date,
            "retrieval_timestamp_utc": retrieval_utc,
            "retrieval_timestamp_taipei": retrieval_tpe,
            "query_or_download_mode": "FinMindClient.storage_object_url whole-day parquet",
            "source_plan": SOURCE_PLAN,
            "source_revision_class": SOURCE_CLASS,
            "row_count": int(table.num_rows),
            "unique_stock_id_count": int(pdf["stock_id"].map(norm_stock).nunique(dropna=True)),
            "unique_securities_trader_id_count": int(pdf["securities_trader_id"].astype("string").str.strip().nunique(dropna=True)),
            "physical_object_sha256": physical_sha,
            "physical_object_bytes": int(physical_bytes),
            "logical_content_sha256": logical_sha,
            "schema_field_list": schema_fields,
            "derived_panel_path": str(panel_path),
            "derived_panel_sha256": panel_sha,
            "derived_stock_rows": int(len(panel)),
            "derived_valid_hhi_rows": int(len(valid)),
            "derived_invalid_stock_rows": int(len(panel) - len(valid)),
            "canonical_mother_sha256": None,
            "date_specific_mother_traded_symbol_count": None,
            "observed_missing_among_mother_traded_symbols": None,
            "mother_u100_lineage_status": "PENDING_FORWARD_MOTHER_U100_ADAPTER; BLOCKS_JUDGE_NOT_SOURCE_CAPTURE",
            "raw_broker_rows_persisted": False,
            "signed_url_persisted": False,
            "token_persisted": False,
            "forward_returns_loaded": False,
            "immutable_first_observed": True,
            "preregistration_path": "research/broker_prospective_20261103/PREREGISTRATION_PROSPECTIVE.json",
        }
        tmp_receipt = out_dir / ".lineage_receipt.json.tmp"
        tmp_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_receipt.replace(receipt_path)

        shutil.rmtree(td, ignore_errors=True)

    print(json.dumps({"status": receipt["status"], "event_date": event_date, "derived_valid_hhi_rows": receipt["derived_valid_hhi_rows"], "physical_object_sha256": physical_sha, "logical_content_sha256": logical_sha, "derived_panel_sha256": panel_sha}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False), file=sys.stderr)
        raise
