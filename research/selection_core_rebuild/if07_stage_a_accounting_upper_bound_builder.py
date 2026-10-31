#!/usr/bin/env python3
"""HENGCE IF-07 V0.1 Stage A accounting upper-bound builder.

Research-only and deliberately outcome-blind:
- NO price data
- NO forward returns
- NO null outcomes
- NO upload timestamps / signal dates

Purpose:
1. acquire the 12 official MOPS bulk iXBRL quarters needed to cover all fiscal
   periods that could map into the preregistered 2023-2024 Discovery signal-date
   window plus their prior-year same-quarter comparators;
2. use the official quarterly MOPS correction list only as an early exclusion
   accelerator for consolidated-report corrections;
3. parse the eight frozen accounting fields from original-equivalent,
   non-corrected consolidated iXBRL files;
4. calculate the six frozen ZERO_RED_FLAG accounting conditions;
5. report the maximum remaining candidate count before the exact t57 metadata,
   upload-time, signal-date and PIT-universe gates.

A low count may prove sample insufficiency because all later gates can only
remove candidates. A high count does NOT authorize return testing.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import math
import re
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import html

ROOT = Path('research/selection_core_rebuild')
SUPERSET = ROOT / 'IF07_DISCOVERY_ACCOUNTING_ACQUISITION_SUPERSET_2022_2024.json'
OUT_ROWS = ROOT / 'generated/IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_NO_RETURNS.json'
OUT_AUDIT = ROOT / 'generated/IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_AUDIT_NO_RETURNS.json'
OUT_ROWS.parent.mkdir(parents=True, exist_ok=True)

BULK_URL = 'https://mopsov.twse.com.tw/server-java/FileDownLoad'
CORR_URL = 'https://mopsov.twse.com.tw/mops/web/ajax_t56sb31_q1'
UA = 'Mozilla/5.0 HENGCE-IF07-stage-a-accounting-upper-bound/0.1'

# Signal-date split was frozen before returns. These are the only fiscal periods
# that can map into Discovery 2023-01-01..2024-12-31 under ordinary filing law.
CURRENT_PERIODS = [
    (2022, 4),
    (2023, 1), (2023, 2), (2023, 3), (2023, 4),
    (2024, 1), (2024, 2), (2024, 3),
]
REQUIRED_PERIODS = sorted(set(CURRENT_PERIODS + [(y - 1, q) for y, q in CURRENT_PERIODS]))

CODES = {
    'Revenue_YTD': '4000',
    'COGS_YTD': '5000',
    'OperatingIncome_YTD': '6900',
    'CFO_YTD': 'AAAA',
    'AR': '1170',
    'Inventory': '130X',
    'Assets': '1XXX',
    'Liabilities': '2XXX',
}
FLOW_FIELDS = {'Revenue_YTD', 'COGS_YTD', 'OperatingIncome_YTD', 'CFO_YTD'}
QEND = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def local(tag: Any) -> str:
    s = str(tag).lower()
    return s.split('}')[-1].split(':')[-1]


def element_text(e: Any) -> str:
    return ''.join(e.itertext()).replace('\xa0', ' ').strip()


def parse_visible_number(s: str, sign: str | None = None) -> float | None:
    x = str(s).strip().replace(',', '').replace(' ', '')
    if not x or x in {'-', '--', '—'}:
        return None
    neg = x.startswith('(') and x.endswith(')')
    if neg:
        x = x[1:-1]
    x = re.sub(r'[^0-9.+-]', '', x)
    try:
        v = float(x)
    except Exception:
        return None
    if sign == '-' and v > 0:
        v = -v
    if neg and v > 0:
        v = -v
    return v if math.isfinite(v) else None


def fast_contexts(root: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for e in root.iter():
        if local(e.tag) != 'context':
            continue
        cid = e.get('id') or e.get('ID')
        if not cid:
            continue
        instant = start = end = None
        segmented = False
        for d in e.iter():
            k = local(d.tag)
            if k == 'instant':
                instant = (d.text or '').strip()
            elif k == 'startdate':
                start = (d.text or '').strip()
            elif k == 'enddate':
                end = (d.text or '').strip()
            elif k in {'segment', 'scenario'}:
                segmented = True
        out[cid] = {'instant': instant, 'start': start, 'end': end, 'segmented': segmented}
    return out


def fast_parse(content: bytes, year: int, q: int) -> tuple[dict[str, float] | None, str | None]:
    try:
        root = html.fromstring(content)
    except Exception as e:
        return None, f'FAST_HTML_PARSE:{type(e).__name__}:{e}'
    ctx = fast_contexts(root)
    m, d = QEND[q]
    end = f'{year}-{m:02d}-{d:02d}'
    start = f'{year}-01-01'
    rows: dict[str, list[dict[str, Any]]] = {}
    for tr in root.iter('tr'):
        cells = [c for c in tr if local(c.tag) in {'td', 'th'}]
        if not cells:
            continue
        code = re.sub(r'\s+', '', element_text(cells[0]))
        if code not in CODES.values():
            continue
        facts = []
        for x in tr.iter():
            if local(x.tag) != 'nonfraction':
                continue
            cref = x.get('contextref') or x.get('contextRef')
            c = ctx.get(cref or '')
            if not c or c['segmented']:
                continue
            v = parse_visible_number(element_text(x), x.get('sign'))
            if v is None:
                continue
            facts.append({'contextref': cref, 'context': c, 'value': v, 'name': x.get('name')})
        rows[code] = facts

    vals: dict[str, float] = {}
    for field, code in CODES.items():
        facts = rows.get(code, [])
        if field in FLOW_FIELDS:
            hits = [f for f in facts if f['context']['start'] == start and f['context']['end'] == end]
        else:
            hits = [f for f in facts if f['context']['instant'] == end]
        values = sorted(set(float(f['value']) for f in hits))
        if len(values) != 1:
            return None, f'FAST_AMBIGUOUS:{field}:{code}:values={values[:10]}'
        vals[field] = values[0]
    return vals, None


def flat_col(c: Any) -> str:
    if isinstance(c, tuple):
        return ' | '.join(str(x).strip() for x in c if str(x).strip() and not str(x).startswith('Unnamed'))
    return str(c).strip()


def compact(s: str) -> str:
    return re.sub(r'\s+', '', str(s)).replace('～', 'To').replace('至', 'To')


def numeric(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (int, float)) and math.isfinite(float(v)):
        return float(v)
    s = str(v).strip().replace(',', '').replace(' ', '')
    if not s or s in {'--', '-', '—', 'N/A', 'NA', 'nan', 'None'}:
        return None
    neg = s.startswith('(') and s.endswith(')')
    if neg:
        s = s[1:-1]
    try:
        x = float(s)
    except Exception:
        return None
    if neg and x > 0:
        x = -x
    return x if math.isfinite(x) else None


def statement_kind(cols: list[str]) -> str | None:
    joined = ' '.join(cols)
    if '資產負債表' in joined or 'Balance Sheet' in joined:
        return 'balance'
    if '綜合損益表' in joined or 'Comprehensive Income' in joined:
        return 'income'
    if '現金流量表' in joined or 'Cash Flows' in joined:
        return 'cashflow'
    return None


def target_column(cols: list[str], kind: str, year: int, q: int) -> str | None:
    m, d = QEND[q]
    if kind == 'balance':
        needle = f'{year}/{m}/{d}'
        hits = [c for c in cols[2:] if needle in compact(c) and 'To' not in compact(c)]
    else:
        needle = f'{year}/1/1To{m}/{d}'
        hits = [c for c in cols[2:] if needle in compact(c)]
    return hits[0] if len(hits) == 1 else None


def norm_code(x: Any) -> str:
    s = str(x).strip()
    if re.fullmatch(r'\d+\.0', s):
        s = s[:-2]
    return re.sub(r'\s+', '', s)


def slow_table_parse(content: bytes, year: int, q: int) -> tuple[dict[str, float] | None, str | None]:
    try:
        tabs = pd.read_html(io.BytesIO(content))
    except Exception as e:
        return None, f'SLOW_READ_HTML:{type(e).__name__}:{e}'
    tables: dict[str, pd.DataFrame] = {}
    for df in tabs:
        x = df.copy()
        x.columns = [flat_col(c) for c in x.columns]
        k = statement_kind(list(x.columns))
        if k and k not in tables:
            tables[k] = x
    if not {'balance', 'income', 'cashflow'}.issubset(tables):
        return None, f'SLOW_MISSING_STATEMENTS:{sorted(tables)}'
    vals: dict[str, float] = {}
    for field, code in CODES.items():
        kind = 'income' if field in {'Revenue_YTD', 'COGS_YTD', 'OperatingIncome_YTD'} else ('cashflow' if field == 'CFO_YTD' else 'balance')
        df = tables[kind]
        col = target_column(list(df.columns), kind, year, q)
        if col is None:
            return None, f'SLOW_PERIOD_COLUMN:{kind}:{field}'
        code_col = df.columns[0]
        mask = df[code_col].map(norm_code) == code
        if int(mask.sum()) != 1:
            return None, f'SLOW_CODE_COUNT:{field}:{code}:{int(mask.sum())}'
        v = numeric(df.loc[mask].iloc[0][col])
        if v is None:
            return None, f'SLOW_NONNUMERIC:{field}:{code}'
        vals[field] = v
    return vals, None


def parse_with_fallback(content: bytes, year: int, q: int) -> tuple[dict[str, float] | None, str, str | None]:
    fast, err = fast_parse(content, year, q)
    if fast is not None:
        return fast, 'FAST', None
    slow, slow_err = slow_table_parse(content, year, q)
    if slow is not None:
        return slow, 'SLOW_FALLBACK', err
    return None, 'FAIL', f'{err};{slow_err}'


def decode_best(b: bytes) -> str:
    candidates = [b.decode('utf-8', errors='replace'), b.decode('big5', errors='replace')]
    return min(candidates, key=lambda x: x.count('\ufffd'))


def get_corrections(s: requests.Session, year: int, q: int) -> tuple[set[str], dict[str, Any]]:
    data = {
        'step': '1', 'firstin': 'ture', 'off': '1', 'isQuery': 'Y',
        'TYPEK': 'sii', 'year': str(year - 1911), 'season': f'{q:02d}',
    }
    last: dict[str, Any] | None = None
    for attempt in range(3):
        try:
            r = s.post(CORR_URL, data=data, timeout=90)
            text = decode_best(r.content)
            blocked = any(x in text.lower() for x in ['access denied', 'for security reasons', 'this page can not be accessed', 'this page cannot be accessed']) or '查詢過量' in text
            soup = BeautifulSoup(text, 'lxml')
            issuer_rows = []
            corrected: set[str] = set()
            for tr in soup.find_all('tr'):
                cells = [' '.join(td.stripped_strings) for td in tr.find_all(['td', 'th'])]
                if len(cells) < 4 or not re.fullmatch(r'\d{4}', cells[0].strip()):
                    continue
                issuer_rows.append(cells)
                # Only a correction to a consolidated report is an early exclusion.
                # Individual-only corrections must not shrink the Stage-A upper bound.
                report_type = cells[3]
                if '合併財報' in report_type:
                    corrected.add(cells[0].strip())
            structurally_valid = ('YEAR_SEASON' in text and 'ajax_t56sb31_q1' in text)
            receipt = {
                'year': year, 'quarter': q, 'attempt': attempt + 1,
                'http_status': r.status_code, 'bytes': len(r.content), 'sha256': sha256(r.content),
                'security_or_rate_blocked': blocked, 'structurally_valid': structurally_valid,
                'issuer_row_count': len(issuer_rows), 'consolidated_corrected_count': len(corrected),
                'consolidated_corrected_in_acquisition_scope': None,
            }
            if r.status_code == 200 and not blocked and structurally_valid:
                return corrected, receipt
            last = receipt
        except Exception as e:
            last = {'year': year, 'quarter': q, 'attempt': attempt + 1, 'error': f'{type(e).__name__}:{e}'}
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'CORRECTION_QUERY_FAILED:{year}Q{q}:{last}')


def download_bulk(s: requests.Session, year: int, q: int) -> tuple[bytes, dict[str, Any]]:
    fn = f'tifrs-{year}Q{q}.zip'
    params = {'step': '9', 'functionName': 'show_file2', 'fileName': fn, 'filePath': f'/ifrs/{year}/'}
    last = None
    for attempt in range(3):
        try:
            r = s.get(BULK_URL, params=params, headers={'Referer': 'https://mopsov.twse.com.tw/mops/web/t203sb02'}, timeout=300)
            b = r.content
            receipt = {
                'year': year, 'quarter': q, 'attempt': attempt + 1,
                'http_status': r.status_code, 'bytes': len(b), 'sha256': sha256(b),
                'content_type': r.headers.get('content-type'), 'zip_magic': b[:2] == b'PK',
            }
            if r.status_code == 200 and b[:2] == b'PK':
                return b, receipt
            last = receipt
        except Exception as e:
            last = {'year': year, 'quarter': q, 'attempt': attempt + 1, 'error': f'{type(e).__name__}:{e}'}
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'BULK_DOWNLOAD_FAILED:{year}Q{q}:{last}')


def member_map(z: zipfile.ZipFile, year: int, q: int) -> dict[str, str]:
    pat = re.compile(rf'^tifrs-fr1-m1-ci-cr-(\d{{4}})-{year}Q{q}\.html$', re.I)
    out: dict[str, str] = {}
    duplicates: set[str] = set()
    for n in z.namelist():
        m = pat.match(Path(n).name)
        if not m:
            continue
        t = m.group(1)
        if t in out:
            duplicates.add(t)
        else:
            out[t] = n
    for t in duplicates:
        out.pop(t, None)
    return out


def derive(cur: dict[str, float], prev: dict[str, float]) -> tuple[dict[str, float] | None, str | None]:
    # Exact denominators implied by frozen formulas.
    positive = [
        ('current Revenue_YTD', cur['Revenue_YTD']),
        ('prior Revenue_YTD', prev['Revenue_YTD']),
        ('prior COGS_YTD', prev['COGS_YTD']),
        ('prior AR', prev['AR']),
        ('prior Inventory', prev['Inventory']),
        ('current Assets', cur['Assets']),
        ('prior Assets', prev['Assets']),
    ]
    bad = [name for name, value in positive if not math.isfinite(value) or value <= 0]
    if bad:
        return None, 'NONPOSITIVE_DENOMINATOR:' + ','.join(bad)
    cash = cur['CFO_YTD'] / cur['Revenue_YTD']
    cashp = prev['CFO_YTD'] / prev['Revenue_YTD']
    rev = cur['Revenue_YTD'] / prev['Revenue_YTD'] - 1
    ar = cur['AR'] / prev['AR'] - 1
    cogs = cur['COGS_YTD'] / prev['COGS_YTD'] - 1
    inv = cur['Inventory'] / prev['Inventory'] - 1
    gm = (cur['Revenue_YTD'] - cur['COGS_YTD']) / cur['Revenue_YTD']
    gmp = (prev['Revenue_YTD'] - prev['COGS_YTD']) / prev['Revenue_YTD']
    om = cur['OperatingIncome_YTD'] / cur['Revenue_YTD']
    omp = prev['OperatingIncome_YTD'] / prev['Revenue_YTD']
    lev = cur['Liabilities'] / cur['Assets']
    levp = prev['Liabilities'] / prev['Assets']
    return {
        'cash_conversion': cash, 'cash_conversion_prev': cashp, 'D_CASH': cash - cashp,
        'REV_YOY': rev, 'AR_YOY': ar, 'AR_GAP': rev - ar,
        'COGS_YOY': cogs, 'INV_YOY': inv, 'INV_GAP': cogs - inv,
        'GM': gm, 'GM_prev': gmp, 'D_GM': gm - gmp,
        'OM': om, 'OM_prev': omp, 'D_OM': om - omp,
        'LEV': lev, 'LEV_prev': levp, 'D_LEV': lev - levp,
    }, None


def main() -> None:
    superset = json.loads(SUPERSET.read_text(encoding='utf-8'))
    tickers = sorted(str(x) for x in superset['tickers'])
    if len(tickers) != int(superset['union_ticker_count']):
        raise SystemExit('SUPERSET_COUNT_MISMATCH')

    s = requests.Session()
    s.headers.update({'User-Agent': UA, 'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.7'})

    # 1) Official correction lists for every required quarter.
    corrections: dict[tuple[int, int], set[str]] = {}
    correction_receipts = []
    for y, q in REQUIRED_PERIODS:
        c, receipt = get_corrections(s, y, q)
        receipt['consolidated_corrected_in_acquisition_scope'] = len(c.intersection(tickers))
        corrections[(y, q)] = c
        correction_receipts.append(receipt)
        print(f'CORRECTIONS {y}Q{q}: consolidated={len(c)} in_scope={receipt["consolidated_corrected_in_acquisition_scope"]}', flush=True)
        time.sleep(0.8)

    # 2) Parse every relevant uncorrected company-quarter from official bulk files.
    parsed: dict[tuple[str, int, int], dict[str, float]] = {}
    parser_mode: dict[tuple[str, int, int], str] = {}
    parse_failure: dict[tuple[str, int, int], str] = {}
    bulk_receipts = []
    parse_stats_by_period: dict[str, dict[str, int]] = {}
    crosscheck_mismatches = []

    for y, q in REQUIRED_PERIODS:
        b, receipt = download_bulk(s, y, q)
        period_key = f'{y}Q{q}'
        stats = Counter()
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            mmap = member_map(z, y, q)
            receipt['zip_member_count'] = len(z.namelist())
            receipt['consolidated_member_count'] = len(mmap)
            for idx, ticker in enumerate(tickers):
                key = (ticker, y, q)
                if ticker in corrections[(y, q)]:
                    parse_failure[key] = 'OFFICIAL_CONSOLIDATED_CORRECTION_LISTED'
                    stats['correction_excluded'] += 1
                    continue
                member = mmap.get(ticker)
                if not member:
                    parse_failure[key] = 'CONSOLIDATED_MEMBER_MISSING_OR_AMBIGUOUS'
                    stats['member_missing'] += 1
                    continue
                content = z.read(member)
                vals, mode, err = parse_with_fallback(content, y, q)
                if vals is None:
                    parse_failure[key] = err or 'PARSE_FAIL'
                    stats['parse_fail'] += 1
                    continue
                parsed[key] = vals
                parser_mode[key] = mode
                stats['fast_pass' if mode == 'FAST' else 'slow_fallback_pass'] += 1

                # Deterministic independent cross-check: first successful FAST rows in each period.
                if mode == 'FAST' and stats['crosschecked'] < 3:
                    slow_vals, slow_err = slow_table_parse(content, y, q)
                    if slow_vals is not None:
                        stats['crosschecked'] += 1
                        if any(slow_vals[k] != vals[k] for k in CODES):
                            crosscheck_mismatches.append({
                                'ticker': ticker, 'year': y, 'quarter': q,
                                'fast': vals, 'slow': slow_vals,
                            })
                    else:
                        stats['crosscheck_slow_unavailable'] += 1
        bulk_receipts.append(receipt)
        parse_stats_by_period[period_key] = dict(stats)
        print(f'PARSED {period_key}: {dict(stats)}', flush=True)
        del b

    if crosscheck_mismatches:
        audit = {
            'system': 'HENGCE', 'artifact': 'IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_AUDIT_NO_RETURNS',
            'generated_at_utc': now(), 'contains_price_or_forward_return_data': False,
            'status': 'DATA_BLOCKED_PARSER_DIVERGENCE',
            'crosscheck_mismatches': crosscheck_mismatches,
            'correction_receipts': correction_receipts, 'bulk_receipts': bulk_receipts,
            'parse_stats_by_period': parse_stats_by_period,
        }
        OUT_AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
        raise SystemExit('DATA_BLOCKED_PARSER_DIVERGENCE')

    # 3) Build accounting-only current/prior pairs for eight possible Discovery fiscal periods.
    rows = []
    reason_counts = Counter()
    candidates = []
    by_period = Counter()
    eligible_by_period = Counter()
    candidate_by_period = Counter()

    for y, q in CURRENT_PERIODS:
        pkey = f'{y}Q{q}'
        for ticker in tickers:
            by_period[pkey] += 1
            ck = (ticker, y, q)
            pk = (ticker, y - 1, q)
            row: dict[str, Any] = {
                'ticker': ticker, 'fiscal_year': y, 'quarter': q,
                'prior_year': y - 1,
                'contains_market_outcome': False,
                'upload_ts_known': False, 'signal_date_known': False,
                'pit_electronics_membership_checked': False,
                'current_correction_listed': ticker in corrections[(y, q)],
                'prior_correction_listed': ticker in corrections[(y - 1, q)],
                'current_parser_mode': parser_mode.get(ck),
                'prior_parser_mode': parser_mode.get(pk),
            }
            if ticker in corrections[(y, q)]:
                reason = 'CURRENT_CONSOLIDATED_CORRECTION_LISTED'
            elif ticker in corrections[(y - 1, q)]:
                reason = 'PRIOR_CONSOLIDATED_CORRECTION_LISTED'
            elif ck not in parsed:
                reason = 'CURRENT_ACCOUNTING_UNAVAILABLE:' + parse_failure.get(ck, 'UNKNOWN')
            elif pk not in parsed:
                reason = 'PRIOR_ACCOUNTING_UNAVAILABLE:' + parse_failure.get(pk, 'UNKNOWN')
            else:
                derived, derr = derive(parsed[ck], parsed[pk])
                if derr:
                    reason = derr
                else:
                    conditions = {
                        'D_CASH_ge_0': derived['D_CASH'] >= 0,
                        'AR_GAP_ge_0': derived['AR_GAP'] >= 0,
                        'INV_GAP_ge_0': derived['INV_GAP'] >= 0,
                        'D_GM_ge_0': derived['D_GM'] >= 0,
                        'D_OM_ge_0': derived['D_OM'] >= 0,
                        'D_LEV_le_0': derived['D_LEV'] <= 0,
                    }
                    candidate = all(conditions.values())
                    row.update({
                        'accounting_pair_available': True,
                        'current': parsed[ck], 'prior': parsed[pk],
                        'derived': derived, 'conditions': conditions,
                        'accounting_6of6_pre_metadata_candidate': candidate,
                    })
                    eligible_by_period[pkey] += 1
                    if candidate:
                        candidate_by_period[pkey] += 1
                        candidates.append(row)
                    rows.append(row)
                    continue
            row.update({
                'accounting_pair_available': False,
                'exclusion_reason': reason,
                'accounting_6of6_pre_metadata_candidate': False,
            })
            reason_counts[reason] += 1
            rows.append(row)

    candidate_unique = len({r['ticker'] for r in candidates})
    candidate_count = len(candidates)

    # Later metadata/PIT gates can only remove candidates, never add them.
    impossible_minimum = candidate_count < 80 or candidate_unique < 40
    sufficiency = (
        'INCONCLUSIVE_SAMPLE_INSUFFICIENT_PRE_RETURN_UPPER_BOUND'
        if impossible_minimum else
        'UPPER_BOUND_SUFFICIENT_TO_CONTINUE_EXACT_METADATA_GATE'
    )

    audit = {
        'system': 'HENGCE',
        'artifact': 'IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_AUDIT_NO_RETURNS',
        'generated_at_utc': now(),
        'challenger': 'IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1',
        'contains_price_or_forward_return_data': False,
        'status': 'PASS_NO_RETURN_STAGE_A',
        'formal_pit_universe_applied': False,
        'upload_timestamp_applied': False,
        'signal_date_applied': False,
        'acquisition_superset_count': len(tickers),
        'current_periods': [f'{y}Q{q}' for y, q in CURRENT_PERIODS],
        'required_bulk_periods': [f'{y}Q{q}' for y, q in REQUIRED_PERIODS],
        'pair_attempt_count': len(rows),
        'pair_attempts_by_period': dict(by_period),
        'accounting_pair_available_count': sum(r['accounting_pair_available'] for r in rows),
        'accounting_pair_available_by_period': dict(eligible_by_period),
        'accounting_6of6_pre_metadata_candidate_count': candidate_count,
        'accounting_6of6_pre_metadata_candidate_unique_tickers': candidate_unique,
        'accounting_6of6_pre_metadata_candidate_by_period': dict(candidate_by_period),
        'sample_sufficiency_upper_bound_verdict': sufficiency,
        'minimum_required_events': 80,
        'minimum_required_unique_tickers': 40,
        'signal_date_minimum_not_yet_assessable': 20,
        'later_gates_can_only_remove_candidates': True,
        'correction_policy': 'Quarterly official MOPS correction list is used only for consolidated-report early exclusion; individual-only corrections do not shrink the upper bound. Final t57 exact-無 remains mandatory in Stage B.',
        'correction_receipts': correction_receipts,
        'bulk_receipts': bulk_receipts,
        'parse_stats_by_period': parse_stats_by_period,
        'parser_crosscheck_mismatch_count': len(crosscheck_mismatches),
        'exclusion_reason_counts': dict(reason_counts),
        'forward_return_lock': 'CLOSED',
        'next_legal_step': (
            'STOP_INCONCLUSIVE_NO_RETURNS' if impossible_minimum
            else 'STAGE_B_T57_EXACT_METADATA_ONLY_FOR_ACCOUNTING_6OF6_CANDIDATES'
        ),
    }
    OUT_ROWS.write_text(json.dumps({
        'system': 'HENGCE',
        'artifact': 'IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_NO_RETURNS',
        'generated_at_utc': now(),
        'contains_price_or_forward_return_data': False,
        'rows': rows,
    }, ensure_ascii=False), encoding='utf-8')
    OUT_AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'status': audit['status'],
        'pair_attempt_count': audit['pair_attempt_count'],
        'accounting_pair_available_count': audit['accounting_pair_available_count'],
        'candidate_count': candidate_count,
        'candidate_unique_tickers': candidate_unique,
        'sample_sufficiency_upper_bound_verdict': sufficiency,
        'next_legal_step': audit['next_legal_step'],
    }, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
