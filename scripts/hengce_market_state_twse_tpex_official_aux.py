#!/usr/bin/env python3
"""Bind the TWSE+TPEx Market State observer to official current security masters.

This adapter replaces the FinMind-history-derived membership function used by
hengce_market_state_twse_tpex_aux with current official issuer masters:
- TWSE OpenAPI t187ap03_L (listed companies; TDR excluded by existing HENGCE helper)
- TPEx OpenAPI mopsfin_t187ap03_O (current OTC companies)

FinMind remains the realtime snapshot source only. Emerging-board equities are
not part of the HENGCE all-Taiwan Market State universe.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any

import requests

import hengce_market_state_twse_tpex_aux as base
from hengce_finmind_twse_common_snapshot_probe import _fetch_twse_master, _twse_common_universe

TPEX_MASTER_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
FOUR_DIGIT = re.compile(r"[1-9]\d{3}")


def _sha_lines(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _fetch_tpex_payload() -> list[dict[str, Any]]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "HENGCE-TPEX-CURRENT-MASTER/1.1",
        "Connection": "close",
    }
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            response = requests.get(TPEX_MASTER_URL, timeout=(10, 45), headers=headers)
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows:
                raise RuntimeError("TPEX_CURRENT_MASTER_EMPTY_OR_MALFORMED")
            return rows
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt < 4:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"TPEX_CURRENT_MASTER_FETCH_FAILED_AFTER_RETRIES:{type(last_error).__name__}:{last_error}")


def _fetch_tpex_current_common() -> tuple[list[str], str | None, list[dict[str, Any]]]:
    rows = _fetch_tpex_payload()

    codes: list[str] = []
    normalized: list[dict[str, Any]] = []
    dates: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("SecuritiesCompanyCode") or "").strip()
        if not FOUR_DIGIT.fullmatch(code):
            continue
        name = str(row.get("CompanyAbbreviation") or "").strip()
        industry = str(row.get("SecuritiesIndustryCode") or "").strip()
        d = str(row.get("Date") or "").strip()
        codes.append(code)
        if d:
            dates.append(d)
        normalized.append({"code": code, "name": name, "industry": industry, "date": d})

    codes = sorted(set(codes))
    if len(codes) < 700:
        raise RuntimeError(f"TPEX_CURRENT_COMMON_UNIVERSE_TOO_SMALL:{len(codes)}")
    if len(codes) != len(normalized):
        seen: set[str] = set()
        dupes: set[str] = set()
        for row in normalized:
            code = row["code"]
            if code in seen:
                dupes.add(code)
            seen.add(code)
        if dupes:
            raise RuntimeError(f"TPEX_CURRENT_MASTER_DUPLICATE_CODES:{sorted(dupes)[:20]}")

    return codes, max(dates) if dates else None, normalized


def _official_membership(target_date: str) -> tuple[dict[str, list[str]], dict[str, Any]]:
    twse_rows, twse_report_date = _fetch_twse_master()
    twse_codes, _tdr_codes, _tdr_meta = _twse_common_universe(twse_rows)
    tpex_codes, tpex_report_date, tpex_rows = _fetch_tpex_current_common()

    if len(twse_codes) < 900:
        raise RuntimeError(f"TWSE_CURRENT_COMMON_UNIVERSE_TOO_SMALL:{len(twse_codes)}")
    overlap = sorted(set(twse_codes) & set(tpex_codes))
    if overlap:
        raise RuntimeError(f"TWSE_TPEX_CURRENT_MASTER_OVERLAP:{overlap[:20]}")

    all_codes = sorted(set(twse_codes) | set(tpex_codes))
    if len(all_codes) < 1700:
        raise RuntimeError(f"ALL_TAIWAN_CURRENT_COMMON_UNIVERSE_TOO_SMALL:{len(all_codes)}")

    membership_lines = [f"TWSE|{code}" for code in twse_codes] + [f"TPEX|{code}" for code in tpex_codes]
    meta = {
        "target_date": target_date,
        "membership_authority": "OFFICIAL_CURRENT_TWSE_AND_TPEX_MASTERS",
        "market_type_rule": "twse+tpex_only_excludes_emerging",
        "twse_master_endpoint": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "twse_master_report_date": twse_report_date,
        "tpex_master_endpoint": TPEX_MASTER_URL,
        "tpex_master_report_date": tpex_report_date,
        "twse_count": len(twse_codes),
        "tpex_count": len(tpex_codes),
        "all_taiwan_equity_count": len(all_codes),
        "membership_sha256": _sha_lines(membership_lines),
        "raw_membership_rows_persisted": False,
        "finmind_membership_used": False,
        "emerging_included": False,
        "tpex_master_fetch_policy": "BOUNDED_4_ATTEMPTS_FAIL_CLOSED",
        "tpex_master_field_schema": {
            "code": "SecuritiesCompanyCode",
            "name": "CompanyAbbreviation",
            "industry": "SecuritiesIndustryCode",
            "date": "Date"
        },
        "tpex_normalized_row_count": len(tpex_rows),
    }
    return {"twse": twse_codes, "tpex": tpex_codes, "all": all_codes}, meta


base._membership = _official_membership


def main() -> None:
    base.main()


if __name__ == "__main__":
    main()
