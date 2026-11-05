#!/usr/bin/env python3
"""Download one FinMind SponsorPro whole-day broker parquet via FinMind's official client.

The official finmind-mcp package resolves FINMIND_TOKEN from the environment and
handles the short-lived signed object-storage redirect. HENGCE does not persist
that URL and this script does not inspect forward returns.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from finmind_mcp.client import FinMindClient

ALLOWED = {
    "TaiwanStockTradingDailyReportSecIdAgg",
    "TaiwanStockTradingDailyReport",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


async def run(dataset: str, date: str, output: Path, receipt_path: Path) -> int:
    receipt = {
        "schema_version": 1,
        "generated_at_taipei": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "authority": "RESEARCH_ONLY_BROKER_TAPE_FEASIBILITY_NO_FORWARD_RETURN_AUTHORITY",
        "source_client": "FinMind official finmind-mcp",
        "dataset": dataset,
        "requested_date": date,
        "status": "FAIL_CLOSED",
        "signed_url_persisted": False,
        "forward_returns_inspected": False,
        "errors": [],
    }
    try:
        client = FinMindClient()
        signed_url = await client.storage_object_url(dataset, date)
        output.parent.mkdir(parents=True, exist_ok=True)
        byte_count = await client.download(signed_url, output)
        receipt.update({
            "status": "PASS_TRANSPORT",
            "raw_byte_count": byte_count,
            "raw_sha256": sha256(output),
        })
    except Exception as exc:
        receipt["errors"].append(f"{type(exc).__name__}:{exc}")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS_TRANSPORT" else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", choices=sorted(ALLOWED), default="TaiwanStockTradingDailyReportSecIdAgg")
    p.add_argument("--date", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--receipt", required=True)
    a = p.parse_args()
    return asyncio.run(run(a.dataset, a.date, Path(a.output), Path(a.receipt)))


if __name__ == "__main__":
    raise SystemExit(main())
