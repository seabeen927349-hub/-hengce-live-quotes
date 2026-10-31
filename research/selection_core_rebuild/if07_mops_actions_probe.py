#!/usr/bin/env python3
"""HENGCE IF-07 MOPS network/data capability probe.

NO price data. NO forward returns. NO alpha calculations.
The purpose is only to verify that GitHub Actions can reproducibly reach the
official MOPS/TWSE endpoints required to build the preregistered PIT accounting
panel.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import requests

OUT = Path("research/selection_core_rebuild/generated/IF07_MOPS_ACTIONS_PROBE.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 HENGCE-IF07-research-probe/0.1"
)
TIMEOUT = 30


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def security_blocked(text: str) -> bool:
    t = text.lower()
    needles = [
        "for security reasons",
        "this page can not be accessed",
        "this page cannot be accessed",
        "access denied",
    ]
    return any(n in t for n in needles)


def probe_post(session: requests.Session, name: str, url: str, data: dict[str, str], expected: list[str]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "method": "POST",
        "url": url,
        "params": data,
        "requested_at_utc": now_utc(),
    }
    try:
        r = session.post(url, data=data, timeout=TIMEOUT, allow_redirects=True)
        text = r.text
        row.update(
            {
                "http_status": r.status_code,
                "final_url": r.url,
                "content_type": r.headers.get("content-type"),
                "bytes": len(r.content),
                "sha256_utf8": digest(text),
                "security_blocked": security_blocked(text),
                "expected_markers": {x: (x in text) for x in expected},
                "all_expected_markers_present": all(x in text for x in expected),
                "body_prefix": text[:500],
            }
        )
        row["status"] = (
            "PASS"
            if r.status_code == 200
            and not row["security_blocked"]
            and row["all_expected_markers_present"]
            else "FAIL"
        )
    except Exception as exc:  # fail closed and persist the exact error class/text
        row.update({"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)})
    return row


def probe_get(session: requests.Session, name: str, url: str, params: dict[str, str], expected: list[str]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "method": "GET",
        "url": url,
        "params": params,
        "requested_at_utc": now_utc(),
    }
    try:
        r = session.get(url, params=params, timeout=TIMEOUT, allow_redirects=True)
        text = r.text
        row.update(
            {
                "http_status": r.status_code,
                "final_url": r.url,
                "content_type": r.headers.get("content-type"),
                "bytes": len(r.content),
                "sha256_utf8": digest(text),
                "security_blocked": security_blocked(text),
                "expected_markers": {x: (x in text) for x in expected},
                "all_expected_markers_present": all(x in text for x in expected),
                "body_prefix": text[:500],
            }
        )
        row["status"] = (
            "PASS"
            if r.status_code == 200
            and not row["security_blocked"]
            and row["all_expected_markers_present"]
            else "FAIL"
        )
    except Exception as exc:
        row.update({"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)})
    return row


def main() -> None:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
            "Referer": "https://mopsov.twse.com.tw/mops/web/index",
        }
    )

    common = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "TYPEK": "sii",
        "year": "112",
        "season": "01",
    }

    probes: list[dict[str, Any]] = []

    probes.append(
        probe_post(
            s,
            "MOPS_2023Q1_LISTED_AGGREGATE_INCOME",
            "https://mopsov.twse.com.tw/mops/web/ajax_t163sb04",
            common,
            ["公司代號", "2330", "2454", "營業收入"],
        )
    )

    probes.append(
        probe_post(
            s,
            "MOPS_2023Q1_LISTED_AGGREGATE_BALANCE",
            "https://mopsov.twse.com.tw/mops/web/ajax_t163sb05",
            common,
            ["公司代號", "2330", "2454", "資產總計"],
        )
    )

    cash_params = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "TYPEK": "sii",
        "co_id": "2330",
        "year": "112",
        "season": "01",
    }
    probes.append(
        probe_post(
            s,
            "MOPS_2330_2023Q1_CASH_FLOW",
            "https://mopsov.twse.com.tw/mops/web/ajax_t164sb05",
            cash_params,
            ["2330", "營業活動", "現金流"],
        )
    )

    doc_params = {
        "step": "1",
        "colorchg": "1",
        "co_id": "2330",
        "year": "112",
        "seamon": "",
        "mtype": "A",
    }
    probes.append(
        probe_get(
            s,
            "TWSE_EBOOK_2330_2023_UPLOAD_METADATA",
            "https://doc.twse.com.tw/server-java/t57sb01",
            doc_params,
            ["2330", "202301_2330_AI1.pdf", "112/05/12"],
        )
    )

    overall = "PASS" if all(x.get("status") == "PASS" for x in probes) else "FAIL"
    blocked_count = sum(bool(x.get("security_blocked")) for x in probes)

    report = {
        "system": "HENGCE",
        "artifact": "IF07_MOPS_GITHUB_ACTIONS_CAPABILITY_PROBE",
        "generated_at_utc": now_utc(),
        "research_only": True,
        "contains_price_or_forward_return_data": False,
        "preregistered_challenger": "IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1",
        "overall": overall,
        "security_blocked_probe_count": blocked_count,
        "interpretation": (
            "PASS means the Actions runner can reach and verify all four official source paths. "
            "FAIL is a data-acquisition/transport result only; it is not an alpha or hypothesis failure."
        ),
        "probes": probes,
    }

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"overall": overall, "security_blocked_probe_count": blocked_count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
