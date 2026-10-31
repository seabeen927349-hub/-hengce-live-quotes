#!/usr/bin/env python3
"""HENGCE IF-07 MOPS capability probe V0.2.

Engineering-only correction to V0.1 false-negative marker logic and addition of
official aggregate cash-flow endpoint. NO price/return data are requested.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

OUT = Path("research/selection_core_rebuild/generated/IF07_MOPS_ACTIONS_PROBE_V0_2.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

TIMEOUT = 45
UA = "Mozilla/5.0 HENGCE-IF07-research-probe-v0.2"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def flat_cols(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in df.columns:
        if isinstance(c, tuple):
            parts = [str(x).strip() for x in c if str(x).strip() and not str(x).startswith("Unnamed")]
            cols.append(" | ".join(parts))
        else:
            cols.append(str(c).strip())
    return cols


def parse_mops_aggregate(session: requests.Session, name: str, url: str, params: dict[str, str], required_markers: list[str]) -> dict[str, Any]:
    row: dict[str, Any] = {"name": name, "url": url, "params": params, "requested_at_utc": now()}
    try:
        r = session.post(url, data=params, timeout=TIMEOUT)
        r.encoding = "utf-8"
        text = r.text
        tables = pd.read_html(io.StringIO(text))
        table_summaries: list[dict[str, Any]] = []
        ticker_2330_rows: list[dict[str, Any]] = []
        for i, df in enumerate(tables):
            cols = flat_cols(df)
            df = df.copy()
            df.columns = cols
            table_summaries.append({"table_index": i, "rows": int(len(df)), "columns": cols})
            # Find 2330 anywhere in row to avoid relying on one header spelling.
            mask = df.astype(str).apply(lambda s: s.str.contains(r"(^|\\D)2330(\\D|$)", regex=True, na=False)).any(axis=1)
            if mask.any():
                for _, rr in df.loc[mask].head(3).iterrows():
                    ticker_2330_rows.append({str(k): (None if pd.isna(v) else str(v)) for k, v in rr.items()})
        markers = {m: (m in text) for m in required_markers}
        row.update({
            "http_status": r.status_code,
            "bytes": len(r.content),
            "sha256_utf8": sha(text),
            "required_markers": markers,
            "tables": table_summaries,
            "ticker_2330_rows": ticker_2330_rows,
            "status": "PASS" if r.status_code == 200 and all(markers.values()) and bool(ticker_2330_rows) else "FAIL",
        })
    except Exception as exc:
        row.update({"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)})
    return row


def probe_ebook(session: requests.Session) -> dict[str, Any]:
    params = {"step":"1","colorchg":"1","co_id":"2330","year":"112","seamon":"","mtype":"A"}
    row: dict[str, Any] = {"name":"TWSE_EBOOK_2330_2023_UPLOAD_METADATA","params":params,"requested_at_utc":now()}
    try:
        r = session.get("https://doc.twse.com.tw/server-java/t57sb01", params=params, timeout=TIMEOUT)
        r.encoding = "big5"
        text = r.text
        target = "202301_2330_AI1.pdf"
        soup = BeautifulSoup(text, "lxml")
        target_tr_text = None
        for tr in soup.find_all("tr"):
            t = " ".join(tr.stripped_strings)
            if target in t:
                target_tr_text = t
                break
        markers = {target: target in text, "112/05/12": "112/05/12" in text}
        row.update({
            "http_status": r.status_code,
            "bytes": len(r.content),
            "sha256_decoded": sha(text),
            "markers": markers,
            "target_row_text": target_tr_text,
            "status": "PASS" if r.status_code == 200 and all(markers.values()) and target_tr_text else "FAIL",
        })
    except Exception as exc:
        row.update({"status":"FAIL","error_type":type(exc).__name__,"error":str(exc)})
    return row


def main() -> None:
    s = requests.Session()
    s.headers.update({"User-Agent":UA,"Referer":"https://mopsov.twse.com.tw/mops/web/index","Accept-Language":"zh-TW,zh;q=0.9"})
    p = {"encodeURIComponent":"1","step":"1","firstin":"1","off":"1","TYPEK":"sii","year":"112","season":"01"}
    probes = [
        parse_mops_aggregate(s,"MOPS_2023Q1_LISTED_AGGREGATE_INCOME","https://mopsov.twse.com.tw/mops/web/ajax_t163sb04",p,["2330","2454","營業收入"]),
        parse_mops_aggregate(s,"MOPS_2023Q1_LISTED_AGGREGATE_BALANCE","https://mopsov.twse.com.tw/mops/web/ajax_t163sb05",p,["2330","2454","資產總計"]),
        parse_mops_aggregate(s,"MOPS_2023Q1_LISTED_AGGREGATE_CASHFLOW","https://mopsov.twse.com.tw/mops/web/ajax_t163sb20",p,["2330","2454","營業活動"]),
        probe_ebook(s),
    ]
    overall = "PASS" if all(x.get("status") == "PASS" for x in probes) else "FAIL"
    obj = {
        "system":"HENGCE",
        "artifact":"IF07_MOPS_GITHUB_ACTIONS_CAPABILITY_PROBE_V0_2",
        "generated_at_utc":now(),
        "research_only":True,
        "contains_price_or_forward_return_data":False,
        "engineering_change_from_v0_1":"Removed false-negative dependency on literal header '公司代號'; added aggregate cash-flow endpoint and parsed-table evidence.",
        "overall":overall,
        "probes":probes,
    }
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"overall":overall,"statuses":[x.get("status") for x in probes]},ensure_ascii=False))


if __name__ == "__main__":
    main()
