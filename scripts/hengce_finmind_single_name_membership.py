#!/usr/bin/env python3
"""Quote-only current Taiwan equity rosters (separate from frozen Market State).

Use the already-fetched TWSE current official master and the TPEx official
current issuer rosters. This is a MEMBERSHIP CHECK within the existing HENGCE
FinMind snapshot runner, never a second quote collector or model/universe.
Historical TaiwanStockInfo records alone are NOT current-listing evidence.
The public receipts contain only aggregate counts, no vendor security rows.
"""
from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
from typing import Any, Mapping

FOUR_DIGIT = re.compile(r"[1-9][0-9]{3}\Z")
TPEx_OPENAPI = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_{}"
TPEx_OFFICIAL_CSV = "https://mopsfin.twse.com.tw/opendata/t187ap03_{}.csv"


def _issuer_codes(rows: list[dict[str, Any]]) -> set[str]:
    codes: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("公司代號") or row.get("股票代號") or "").strip()
        if not FOUR_DIGIT.fullmatch(code):
            continue
        issued = str(row.get("已發行普通股數或TDR原股發行股數") or "").strip()
        # Ordinary share count is present in most issuer rosters. Reject a
        # clearly zero count; do not reject missing fields used by other boards.
        if issued == "0":
            continue
        name = str(row.get("公司簡稱") or "").upper()
        industry = str(row.get("產業別") or "").strip()
        if industry == "91" or "-DR" in name:
            continue
        codes.add(code)
    return codes


def _fetch_roster(suffix: str) -> tuple[set[str], str]:
    if suffix not in {"O", "R"}:
        raise ValueError("UNSUPPORTED_TPEX_BOARD")
    sources = [
        (TPEx_OPENAPI.format(suffix), "TPEx_OPENAPI"),
        (TPEx_OFFICIAL_CSV.format(suffix), "TPEx_MOPS_OFFICIAL_CSV"),
    ]
    for url, label in sources:
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json,text/csv,*/*",
                              "User-Agent": "HENGCE-CURRENT-ISSUER-MEMBERSHIP/1.0"})
            with urllib.request.urlopen(req, timeout=15) as rsp:
                data = rsp.read()
                content_type = (rsp.headers.get("Content-Type") or "").lower()
            decoded = data.decode("utf-8-sig")
            if "csv" in content_type or url.endswith(".csv"):
                rows = list(csv.DictReader(io.StringIO(decoded)))
            else:
                obj = json.loads(decoded)
                rows = obj if isinstance(obj, list) else None
            if not isinstance(rows, list) or not rows:
                continue
            codes = _issuer_codes(rows)
            if len(codes) < (700 if suffix == "O" else 80):
                continue
            return codes, label
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            # An unavailable official endpoint is NOT a license to infer from
            # historical FinMind membership. Try only the official CSV mirror.
            continue
    raise RuntimeError("CURRENT_TPEX_ISSUER_ROSTER_UNAVAILABLE_" + suffix)


def current_official_quote_membership(
    twse_current_common: set[str],
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return current issuer membership by venue; fail closed on ambiguity."""
    if len(twse_current_common) < 900:
        raise RuntimeError("CURRENT_TWSE_ISSUER_ROSTER_TOO_SMALL")
    tpex, tpex_source = _fetch_roster("O")
    emerging, emerging_source = _fetch_roster("R")

    if (twse_current_common & tpex) or (twse_current_common & emerging) or (tpex & emerging):
        raise RuntimeError("CURRENT_EXCHANGE_ROSTER_DUPLICATE_IDS")
    mapped = {sid: "twse" for sid in twse_current_common}
    mapped.update({sid: "tpex" for sid in tpex})
    mapped.update({sid: "emerging" for sid in emerging})
    counts = {
        "twse": len(twse_current_common),
        "tpex": len(tpex),
        "emerging": len(emerging),
        "sources": {
            "twse": "EXISTING_TWSE_OPENAPI_CURRENT_MASTER",
            "tpex": tpex_source,
            "emerging": emerging_source,
        },
        "membership_rows_persisted": False,
    }
    return mapped, counts
