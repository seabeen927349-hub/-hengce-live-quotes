#!/usr/bin/env python3
"""Research-only TWSE ISIN stock-universe structural probe.

Queries TWSE ISIN classification directly for security type=stock, separately
for the regular listed market and Taiwan Innovation Board. No raw HTML or full
security list is persisted. Output is aggregate metadata/samples only.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import urllib.request

from bs4 import BeautifulSoup

BASE = "https://isin.twse.com.tw/isin/class_main.jsp?chklike=Y&issuetype=1&market={}"
MARKETS = {"TWSE_LISTED": "1", "TWSE_TIB": "C"}
FOUR_DIGIT = re.compile(r"[1-9]\d{3}")


def clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def fetch_market(label: str, market_code: str) -> list[dict[str, str]]:
    url = BASE.format(market_code)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "HENGCE-TWSE-ISIN-CLASS-PROBE/2.0", "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
    soup = BeautifulSoup(raw, "html.parser")
    rows: list[dict[str, str]] = []
    for tr in soup.find_all("tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
        # Current TWSE classification table: serial, ISIN, code, name, market,
        # security type, industry, list/open date, CFI, remarks.
        if len(cells) < 9:
            continue
        code = cells[2]
        cfi = cells[8]
        if not FOUR_DIGIT.fullmatch(code):
            continue
        rows.append(
            {
                "source_market": label,
                "code": code,
                "isin": cells[1],
                "name": cells[3],
                "market_text": cells[4],
                "security_type_text": cells[5],
                "industry_text": cells[6],
                "listed_date": cells[7],
                "cfi": cfi,
            }
        )
    if not rows:
        raise RuntimeError(f"TWSE ISIN stock query produced no four-digit rows for {label}")
    return rows


def digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def main() -> None:
    per_market: dict[str, list[dict[str, str]]] = {}
    for label, market_code in MARKETS.items():
        per_market[label] = fetch_market(label, market_code)

    all_rows = [row for rows in per_market.values() for row in rows]
    code_counts = collections.Counter(row["code"] for row in all_rows)
    duplicates = sorted(code for code, count in code_counts.items() if count > 1)
    codes = sorted(code_counts)
    cfi_counts = collections.Counter(row["cfi"] for row in all_rows)

    market_receipts = {}
    for label, rows in per_market.items():
        market_codes = sorted({row["code"] for row in rows})
        market_receipts[label] = {
            "count": len(market_codes),
            "codes_sha256": digest(market_codes),
            "cfi_counts": dict(collections.Counter(row["cfi"] for row in rows).most_common()),
            "sample": [
                {"code": row["code"], "cfi": row["cfi"], "listed_date": row["listed_date"]}
                for row in rows[:10]
            ],
        }

    non_es = [row for row in all_rows if not row["cfi"].startswith("ES")]
    receipt = {
        "schema": "HENGCE_TWSE_ISIN_STOCK_CLASS_PROBE_V2",
        "source_template": BASE,
        "query_contract": "issuetype=1(stock), market=1(TWSE listed) union market=C(TWSE Taiwan Innovation Board)",
        "per_market": market_receipts,
        "union_four_digit_count": len(codes),
        "union_codes_sha256": digest(codes),
        "cross_market_duplicate_count": len(duplicates),
        "cross_market_duplicate_sample": duplicates[:20],
        "union_cfi_counts": dict(cfi_counts.most_common()),
        "non_es_cfi_count": len(non_es),
        "non_es_sample": [
            {"code": row["code"], "cfi": row["cfi"], "source_market": row["source_market"]}
            for row in non_es[:20]
        ],
        "raw_html_retained": False,
        "formal_universe_authority": False,
        "trading_authority": False,
    }
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
