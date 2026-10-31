#!/usr/bin/env python3
"""HENGCE IF-07 official MOPS bulk correction-list probe.

NO price data. NO forward returns. NO alpha calculations.
Purpose: determine whether the quarterly MOPS correction query can replace
rate-limited per-ticker t57 metadata for the correction gate only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import requests

OUT = Path('research/selection_core_rebuild/generated/IF07_BULK_CORRECTION_PROBE.json')
OUT.parent.mkdir(parents=True, exist_ok=True)
URL = 'https://mopsov.twse.com.tw/mops/web/ajax_t56sb31_q1'
UA = 'Mozilla/5.0 HENGCE-IF07-bulk-correction-probe/0.1'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def decode_best(b: bytes) -> str:
    cand = [b.decode('utf-8', errors='replace'), b.decode('big5', errors='replace')]
    return min(enumerate(cand), key=lambda x: (x[1].count('\ufffd'), x[0]))[1]


def probe(s: requests.Session, year: int, q: int) -> dict[str, Any]:
    data = {
        'step': '1',
        'firstin': 'ture',
        'off': '1',
        'isQuery': 'Y',
        'TYPEK': 'sii',
        'year': str(year - 1911),
        'season': f'{q:02d}',
    }
    r = s.post(URL, data=data, timeout=90)
    text = decode_best(r.content)
    # Extract every 4-digit ticker that appears inside a table row.
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', text, flags=re.I | re.S)
    tickers = []
    row_texts = []
    for row in rows:
        clean = re.sub(r'<[^>]+>', ' ', row)
        clean = re.sub(r'\s+', ' ', clean).strip()
        hits = re.findall(r'(?<!\d)(\d{4})(?!\d)', clean)
        # Prefer rows whose first 4-digit token looks like an issuer code.
        if hits:
            t = hits[0]
            if t not in tickers:
                tickers.append(t)
            row_texts.append(clean[:500])
    low = text.lower()
    blocked = any(x in low for x in [
        'access denied', 'this page can not be accessed',
        'this page cannot be accessed', 'for security reasons', '查詢過量'
    ])
    return {
        'year': year,
        'quarter': q,
        'http_status': r.status_code,
        'bytes': len(r.content),
        'sha256': sha(r.content),
        'content_type': r.headers.get('content-type'),
        'security_or_rate_blocked': blocked,
        'ticker_count_parsed': len(tickers),
        'tickers': tickers,
        'row_text_sample': row_texts[:10],
        'contains_2464': '2464' in tickers,
        'contains_2330': '2330' in tickers,
        'body_prefix': re.sub(r'\s+', ' ', text[:1000]),
    }


def main() -> None:
    s = requests.Session()
    s.headers.update({
        'User-Agent': UA,
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.7',
        'Referer': 'https://mopsov.twse.com.tw/mops/web/t56sb31_q1',
    })
    q2023 = probe(s, 2023, 1)
    q2024 = probe(s, 2024, 2)

    # Known pre-return controls:
    # 2464 2024Q2 is a known correction case from the electronic-book gate.
    # 2330 2023Q1 electronic-book correction field was exact 無.
    control_pass = (
        q2023['http_status'] == 200
        and q2024['http_status'] == 200
        and not q2023['security_or_rate_blocked']
        and not q2024['security_or_rate_blocked']
        and q2024['contains_2464']
        and not q2023['contains_2330']
    )
    obj = {
        'system': 'HENGCE',
        'artifact': 'IF07_BULK_CORRECTION_PROBE',
        'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'contains_price_or_forward_return_data': False,
        'endpoint': URL,
        'controls': {
            'known_corrected_2464_2024Q2_must_be_listed': True,
            'known_exact_none_2330_2023Q1_must_not_be_listed': True,
        },
        'queries': [q2023, q2024],
        'control_pass': control_pass,
        'verdict': 'PASS_AS_QUARTERLY_CORRECTION_LIST_CAPABILITY' if control_pass else 'FAIL_OR_INCONCLUSIVE',
        'boundary': 'This probe does not by itself amend the frozen implementation contract or authorize returns.'
    }
    OUT.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'verdict': obj['verdict'], '2023Q1_count': q2023['ticker_count_parsed'], '2024Q2_count': q2024['ticker_count_parsed'], '2464_2024Q2': q2024['contains_2464'], '2330_2023Q1': q2023['contains_2330']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
