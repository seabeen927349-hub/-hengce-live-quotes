#!/usr/bin/env python3
"""Research-only TWSE official status probe for noncurrent FinMind quotes.

The probe requires current-date evidence. It queries:
- TWTAWU suspension/resumption data,
- STOCK_DAY_ALL (which may lag intraday),
- the canonical HENGCE/TWSE MI_INDEX price endpoint for today's date, and
- TWSE MIS current-session rows for only the target securities.

A prior-day row, source absence, or stale FinMind row is never reinterpreted as
zero trading, suspension, or a valid current metric observation. A current MIS
row proves current-session context only; this probe does not silently assign
field semantics or create a price/return observation from it.
No Escape, metric, selection, model, EOD, or trading authority is created.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
SUSPENSION_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWTAWU"
DAILY_CLOSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
DEFAULT_TARGETS = ["1413", "1423", "1538", "2321", "3593", "5906"]


def request_json(url: str, params: dict[str, str] | None = None, *, referer: str = "https://www.twse.com.tw/") -> Any:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "HENGCE-TWSE-SESSION-STATUS-PROBE/3.0", "Referer": referer})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def fetch_list(url: str) -> list[dict[str, Any]]:
    payload = request_json(url)
    if not isinstance(payload, list):
        raise RuntimeError(f"unexpected TWSE list payload shape for {url}")
    return [row for row in payload if isinstance(row, dict)]


def row_mentions_target(row: dict[str, Any], target: str) -> bool:
    return any(str(value).strip() == target for value in row.values())


def compact(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in row.items():
        text = str(value).strip()
        if text:
            out[str(key)] = text
    return out


def current_mi_index(target_date: str, targets: set[str]) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    payload = request_json(MI_INDEX_URL, {"date": target_date, "type": "ALLBUT0999", "response": "json"})
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected MI_INDEX payload shape")
    stat = str(payload.get("stat") or "")
    response_date = str(payload.get("date") or "")
    ready = stat.upper() == "OK" and response_date == target_date
    matched: dict[str, dict[str, str]] = {}
    if ready:
        table = next((t for t in payload.get("tables") or [] if "證券代號" in (t.get("fields") or []) and "收盤價" in (t.get("fields") or [])), None)
        if table is None:
            raise RuntimeError("current MI_INDEX response missing price table")
        fields = [str(x) for x in (table.get("fields") or [])]
        for values in table.get("data") or table.get("records") or []:
            if not isinstance(values, (list, tuple)):
                continue
            row = {fields[i]: str(values[i]).strip() for i in range(min(len(fields), len(values)))}
            code = row.get("證券代號", "").replace("=", "").replace('"', "").strip()
            if code in targets:
                matched[code] = compact(row)
    return {"stat": stat, "response_date": response_date, "requested_date": target_date, "current_date_ready": ready, "target_match_count": len(matched)}, matched


def current_mis(target_date: str, targets: list[str]) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    payload = request_json(MIS_URL, {"ex_ch": "|".join(f"tse_{code}.tw" for code in targets), "json": "1", "delay": "0", "_": str(int(time.time() * 1000))}, referer="https://mis.twse.com.tw/stock/index.jsp")
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected TWSE MIS payload shape")
    rows = [row for row in (payload.get("msgArray") or []) if isinstance(row, dict)]
    matched: dict[str, dict[str, str]] = {}
    for row in rows:
        code = str(row.get("c") or "").strip()
        if code in targets:
            matched[code] = compact(row)
    current_codes = sorted(code for code, row in matched.items() if str(row.get("d") or "").strip() == target_date)
    query_time = payload.get("queryTime") if isinstance(payload.get("queryTime"), dict) else {}
    return {"msg_array_count": len(rows), "target_match_count": len(matched), "current_date_target_count": len(current_codes), "current_date_target_codes": current_codes, "query_time": compact(query_time), "field_names": sorted({str(k) for row in rows for k in row.keys()})}, matched


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--targets", nargs="*", default=DEFAULT_TARGETS)
    args = p.parse_args()
    targets = sorted({str(x).strip() for x in args.targets if str(x).strip()})
    if not targets:
        raise RuntimeError("no target codes")
    now = datetime.now(TAIPEI)
    target_date = now.strftime("%Y%m%d")
    roc_date = f"{now.year - 1911:03d}{now.month:02d}{now.day:02d}"
    suspension_rows = fetch_list(SUSPENSION_URL)
    close_rows = fetch_list(DAILY_CLOSE_URL)
    close_dates = sorted({str(row.get("Date") or "").strip() for row in close_rows if str(row.get("Date") or "").strip()})
    close_latest_date = close_dates[-1] if close_dates else None
    close_source_current = close_latest_date == roc_date
    mi_meta, mi_matches = current_mi_index(target_date, set(targets))
    mis_meta, mis_matches = current_mis(target_date, targets)
    result: dict[str, Any] = {"schema": "HENGCE_TWSE_SESSION_STATUS_PROBE_V3", "queried_at_taipei": now.isoformat(), "expected_gregorian_date": target_date, "expected_roc_date": roc_date, "sources": {"suspension": SUSPENSION_URL, "daily_close": DAILY_CLOSE_URL, "mi_index": MI_INDEX_URL, "mis": MIS_URL}, "source_row_counts": {"suspension": len(suspension_rows), "daily_close": len(close_rows)}, "daily_close_latest_date": close_latest_date, "daily_close_source_current": close_source_current, "mi_index": mi_meta, "mis": mis_meta, "targets": {}, "mis_current_row_is_session_context_only": True, "mis_field_semantics_not_silently_assumed": True, "prior_day_row_is_not_current_evidence": True, "absence_is_not_zero": True, "absence_is_not_suspension": True, "formal_metric_authority": False, "formal_escape_authority": False, "formal_eod_authority": False, "trading_authority": False}
    unresolved_session = []
    unresolved_metric = []
    for target in targets:
        suspension_matches = [compact(row) for row in suspension_rows if row_mentions_target(row, target)]
        all_close_matches = [compact(row) for row in close_rows if str(row.get("Code") or "").strip() == target]
        current_close_matches = [row for row in all_close_matches if row.get("Date") == roc_date]
        mi_match = mi_matches.get(target)
        mis_match = mis_matches.get(target)
        mis_current = bool(mis_match and str(mis_match.get("d") or "").strip() == target_date)
        entry: dict[str, Any] = {"suspension_match_count": len(suspension_matches), "suspension_matches": suspension_matches[:5], "daily_close_match_count": len(all_close_matches), "daily_close_current_date_match_count": len(current_close_matches), "daily_close_matches": all_close_matches[:5], "mi_index_current_date_match": mi_match is not None, "mi_index_match": mi_match, "mis_current_date_match": mis_current, "mis_match": mis_match, "current_metric_observation_authorized": False}
        if suspension_matches:
            entry["session_evidence_class"] = "TWSE_SUSPENSION_DATA_MATCH"
        elif mi_meta["current_date_ready"] and mi_match is not None:
            entry["session_evidence_class"] = "TWSE_CURRENT_MI_INDEX_MATCH"
        elif current_close_matches:
            entry["session_evidence_class"] = "TWSE_CURRENT_STOCK_DAY_ALL_MATCH"
        elif mis_current:
            entry["session_evidence_class"] = "TWSE_MIS_CURRENT_SESSION_ROW_ONLY"
        else:
            entry["session_evidence_class"] = "UNRESOLVED_CURRENT_DATE_STATUS"
            unresolved_session.append(target)
        if not ((mi_meta["current_date_ready"] and mi_match is not None) or current_close_matches):
            unresolved_metric.append(target)
        result["targets"][target] = entry
    result["unresolved_session_targets"] = unresolved_session
    result["unresolved_metric_targets"] = unresolved_metric
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
