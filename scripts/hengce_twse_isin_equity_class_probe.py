#!/usr/bin/env python3
"""Research-only TWSE ISIN stock-universe structural probe.

Queries TWSE ISIN classification directly for stock instruments, separately
for the regular listed market and Taiwan Innovation Board. A zero-row optional
submarket is reported explicitly instead of being promoted into a false CI
failure. No raw HTML or full security list is persisted.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import urllib.request

from bs4 import BeautifulSoup

BASE = "https://isin.twse.com.tw/isin/class_main.jsp?chklike=Y&issuetype={issuetype}&market={market}"
MARKET_QUERIES = {
    "TWSE_LISTED": {"issuetype": "1", "market": "1", "required_nonempty": True},
    "TWSE_TIB": {"issuetype": "C", "market": "C", "required_nonempty": False},
}
FOUR_DIGIT = re.compile(r"[1-9]\d{3}")


def clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def fetch_market(label: str, issuetype: str, market: str) -> list[dict[str, str]]:
    url = BASE.format(issuetype=issuetype, market=market)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "HENGCE-TWSE-ISIN-CLASS-PROBE/3.1", "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
    soup = BeautifulSoup(raw, "html.parser")
    rows: list[dict[str, str]] = []
    for tr in soup.find_all("tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
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
    return rows


def digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def main() -> None:
    per_market: dict[str, list[dict[str, str]]] = {}
    market_status: dict[str, str] = {}
    for label, query in MARKET_QUERIES.items():
        rows = fetch_market(label, query["issuetype"], query["market"])
        per_market[label] = rows
        if rows:
            market_status[label] = "NONEMPTY"
        elif query["required_nonempty"]:
            raise RuntimeError(
                f"required TWSE ISIN query produced no four-digit rows for {label} "
                f"(issuetype={query['issuetype']}, market={query['market']})"
            )
        else:
            market_status[label] = "EMPTY_OPTIONAL_QUERY_UNRESOLVED_NO_AUTHORITY"

    all_rows = [row for rows in per_market.values() for row in rows]
    code_counts = collections.Counter(row["code"] for row in all_rows)
    duplicates = sorted(code for code, count in code_counts.items() if count > 1)
    codes = sorted(code_counts)
    cfi_counts = collections.Counter(row["cfi"] for row in all_rows)

    market_receipts = {}
    for label, rows in per_market.items():
        market_codes = sorted({row["code"] for row in rows})
        market_receipts[label] = {
            "query": {
                "issuetype": MARKET_QUERIES[label]["issuetype"],
                "market": MARKET_QUERIES[label]["market"],
            },
            "required_nonempty": MARKET_QUERIES[label]["required_nonempty"],
            "status": market_status[label],
            "count": len(market_codes),
            "codes_sha256": digest(market_codes),
            "cfi_counts": dict(collections.Counter(row["cfi"] for row in rows).most_common()),
            "sample": [
                {"code": row["code"], "cfi": row["cfi"], "listed_date": row["listed_date"]}
                for row in rows[:10]
            ],
        }

    non_es = [row for row in all_rows if not row["cfi"].startswith("ES")]
    unresolved_optional = sorted(
        label for label, status in market_status.items() if status.startswith("EMPTY_OPTIONAL")
    )
    receipt = {
        "schema": "HENGCE_TWSE_ISIN_STOCK_CLASS_PROBE_V3_1",
        "source_template": BASE,
        "query_contract": (
            "TWSE_LISTED issuetype=1,market=1 is required nonempty; "
            "TWSE_TIB issuetype=C,market=C is exploratory and a zero-row result is "
            "reported as unresolved rather than silently treated as an empty market"
        ),
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
        "unresolved_optional_market_queries": unresolved_optional,
        "raw_html_retained": False,
        "formal_universe_authority": False,
        "trading_authority": False,
    }
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
