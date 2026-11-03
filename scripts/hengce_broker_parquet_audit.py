#!/usr/bin/env python3
"""Audit a locally supplied FinMind broker parquet for HENGCE feasibility.

No network access. No forward returns. No backtest. No ranking test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = {
    "TaiwanStockTradingDailyReportSecIdAgg": {
        "date",
        "stock_id",
        "securities_trader_id",
        "buy_volume",
        "sell_volume",
        "buy_price",
        "sell_price",
    },
    "TaiwanStockTradingDailyReport": {
        "date",
        "stock_id",
        "securities_trader_id",
        "price",
        "buy",
        "sell",
    },
}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest_symbols(path: Path | None) -> tuple[set[str], str | None]:
    if path is None or not path.exists():
        return set(), None
    raw = path.read_bytes()
    obj = json.loads(raw.decode("utf-8"))
    symbols: set[str] = set()

    def add_value(value):
        if isinstance(value, str) and value.strip():
            symbols.add(value.strip())
        elif isinstance(value, dict):
            s = value.get("symbol_id") or value.get("symbol") or value.get("ticker")
            if s:
                symbols.add(str(s).strip())

    if isinstance(obj, dict):
        for key in ("symbols", "universe", "tickers", "symbol_ids", "requests", "request_plan"):
            value = obj.get(key)
            if isinstance(value, list):
                for item in value:
                    add_value(item)
        # Recursive fallback for frozen manifest structures.
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    if k in {"symbol_id", "symbol", "ticker"}:
                        add_value(v)
                    elif isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)

    return symbols, hashlib.sha256(raw).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", required=True)
    p.add_argument("--dataset", required=True, choices=sorted(EXPECTED))
    p.add_argument("--date", required=True)
    p.add_argument("--manifest")
    p.add_argument("--output", required=True)
    args = p.parse_args()

    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    path = Path(args.parquet)
    manifest = Path(args.manifest) if args.manifest else None
    manifest_symbols, manifest_sha = load_manifest_symbols(manifest)

    result = {
        "schema_version": 1,
        "authority": "RESEARCH_ONLY_BROKER_TAPE_FEASIBILITY_NO_FORWARD_RETURN_AUTHORITY",
        "dataset": args.dataset,
        "requested_date": args.date,
        "status": "FAIL_CLOSED",
        "forward_returns_inspected": False,
        "backtest_run": False,
        "ranking_test_run": False,
        "threshold_tuning_run": False,
        "source_parquet_sha256": file_sha256(path),
        "source_parquet_bytes": path.stat().st_size,
        "request_manifest_sha256": manifest_sha,
        "errors": [],
    }

    try:
        pf = pq.ParquetFile(path)
        cols = pf.schema_arrow.names
        missing = sorted(EXPECTED[args.dataset] - set(cols))
        if missing:
            raise RuntimeError(f"MISSING_COLUMNS:{missing}")

        use_cols = [c for c in cols if c in EXPECTED[args.dataset]]
        table = pf.read(columns=use_cols)
        if table.num_rows == 0:
            raise RuntimeError("PARQUET_EMPTY")

        def unique_strings(name: str) -> set[str]:
            return {str(x) for x in pc.unique(table[name]).to_pylist() if x is not None}

        dates = unique_strings("date")
        stocks = unique_strings("stock_id")
        brokers = unique_strings("securities_trader_id")
        if dates != {args.date}:
            raise RuntimeError(f"SOURCE_DATE_MISMATCH:{sorted(dates)}")

        overlap = stocks & manifest_symbols if manifest_symbols else set()
        missing_manifest = manifest_symbols - stocks if manifest_symbols else set()

        result.update({
            "row_count": table.num_rows,
            "row_group_count": pf.metadata.num_row_groups,
            "columns": cols,
            "date_values": sorted(dates),
            "unique_stock_count": len(stocks),
            "unique_broker_branch_count": len(brokers),
            "null_counts": {c: int(table[c].null_count) for c in table.column_names},
            "manifest_symbol_count": len(manifest_symbols),
            "manifest_overlap_count": len(overlap),
            "manifest_coverage_rate": (len(overlap) / len(manifest_symbols)) if manifest_symbols else None,
            "manifest_missing_count": len(missing_manifest),
            "manifest_missing_symbols": sorted(missing_manifest),
            "status": "PASS_SCHEMA_DATE_COVERAGE_OBSERVED",
        })
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}:{exc}")

    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
