#!/usr/bin/env python3
"""Research-only structural probe for TWSE ISIN listed-equities classification.

No raw HTML or security list is persisted. The output contains only aggregate
counts and small samples needed to determine a defensible common-stock filter.
No trading/model/Escape authority is granted.
"""

from __future__ import annotations

import collections
import json
import re
import urllib.request

from bs4 import BeautifulSoup

URL = "https://isin.twse.com.tw/isin/e_C_public.jsp?strMode=2"
CODE_RE = re.compile(r"^[0-9A-Z]{4,6}$")


def clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def main() -> None:
    req = urllib.request.Request(
        URL,
        headers={"User-Agent": "HENGCE-TWSE-ISIN-CLASS-PROBE/1.0", "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read()
    soup = BeautifulSoup(raw, "html.parser")

    rows = []
    section = None
    section_counts = collections.Counter()
    cfi_counts = collections.Counter()
    market_counts = collections.Counter()
    section_cfi_counts = collections.Counter()
    samples_by_cfi: dict[str, list[dict[str, str]]] = collections.defaultdict(list)

    for tr in soup.find_all("tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
        if not cells:
            continue

        # Section rows on this TWSE public page are single-cell labels such as "Stocks".
        if len(cells) == 1 and cells[0]:
            section = cells[0]
            continue

        # Data rows are expected to expose code/name, ISIN, date, market, industry, CFI, remark.
        if len(cells) < 6:
            continue
        first = cells[0]
        parts = first.split(maxsplit=1)
        if not parts or not CODE_RE.fullmatch(parts[0]):
            continue
        code = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        isin = cells[1]
        listed_date = cells[2]
        market = cells[3]
        industry = cells[4]
        cfi = cells[5]
        row = {
            "code": code,
            "name": name,
            "isin": isin,
            "listed_date": listed_date,
            "market": market,
            "industry": industry,
            "cfi": cfi,
            "section": section or "",
        }
        rows.append(row)
        section_counts[row["section"]] += 1
        cfi_counts[cfi] += 1
        market_counts[market] += 1
        section_cfi_counts[(row["section"], cfi)] += 1
        if len(samples_by_cfi[cfi]) < 5:
            samples_by_cfi[cfi].append({"code": code, "name": name, "market": market, "section": row["section"]})

    if not rows:
        raise RuntimeError("TWSE ISIN page produced no parsed security rows")

    four_digit = [r for r in rows if re.fullmatch(r"[1-9]\d{3}", r["code"])]
    likely_common = [r for r in four_digit if r["cfi"].startswith("ES")]

    receipt = {
        "schema": "HENGCE_TWSE_ISIN_EQUITY_CLASS_PROBE_V1",
        "source": URL,
        "parsed_security_rows": len(rows),
        "four_digit_rows": len(four_digit),
        "section_counts": dict(section_counts.most_common()),
        "cfi_counts": dict(cfi_counts.most_common()),
        "market_counts": dict(market_counts.most_common()),
        "section_cfi_counts": [
            {"section": section_name, "cfi": cfi, "count": count}
            for (section_name, cfi), count in section_cfi_counts.most_common()
        ],
        "cfi_samples": {key: value for key, value in sorted(samples_by_cfi.items())},
        "four_digit_es_prefix_count": len(likely_common),
        "raw_html_retained": False,
        "formal_universe_authority": False,
        "trading_authority": False,
    }
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
