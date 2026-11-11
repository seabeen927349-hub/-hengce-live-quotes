#!/usr/bin/env python3
"""Read existing original HENGCE canonical Library mother for ATR, no new vessel.

The GitHub EOD original receipts remain the primary operational transport.
This adapter is OPTIONAL, local, read-only historical research: a fully
SHA-pinned canonical 2026 mother + original TDCC roster already in the user's
Library can resolve 21-session OHLC windows even when the repo has only a few
daily price_1..9.csv receipts. No 11/12 values are inferred from 11/11.
"""
from __future__ import annotations
import csv
import hashlib
import math
from datetime import date
from pathlib import Path

try:
    from scripts.hengce_v22_max5_atr_price_plan import (
        PriceEvidenceBlocked, _sessions_ending
    )
except ModuleNotFoundError:
    from hengce_v22_max5_atr_price_plan import PriceEvidenceBlocked, _sessions_ending

ORIGINAL_CANONICAL_2026_MOTHER_SHA256 = (
    "67cc7454094a884c4769d0fa5172bdfba175fc7b95182714a40ced3c42d28d5f")
ORIGINAL_G1_781_TDCC_MOTHER_SHA256 = (
    "71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88")
PINNED_SOURCE_END = date(2026, 11, 11)
MIN_ORIGINAL_MARKET_ROWS_PER_DAY = 900


def _hash(path: Path):
    h = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                h.update(block)
    except OSError as e:
        raise PriceEvidenceBlocked("PRIVATE_ORIGINAL_MOTHER_NOT_READABLE") from e
    return h.hexdigest()


def _n(s):
    try:
        v = float(str(s).replace(",", ""))
    except (TypeError, ValueError) as e:
        raise PriceEvidenceBlocked("ORIGINAL_CANONICAL_OHLC_MISSING") from e
    if not math.isfinite(v) or v <= 0:
        raise PriceEvidenceBlocked("ORIGINAL_CANONICAL_OHLC_NOT_POSITIVE")
    return v


class OriginalCanonicalMotherATR:
    """Implements same .ticker_day() / .atr20() as the original EOD reader."""

    def __init__(self, canonical_file: Path, tdcc_file: Path, *,
                 expected_canonical_sha=ORIGINAL_CANONICAL_2026_MOTHER_SHA256,
                 expected_tdcc_sha=ORIGINAL_G1_781_TDCC_MOTHER_SHA256):
        self.canonical_file = Path(canonical_file)
        self.tdcc_file = Path(tdcc_file)
        if _hash(self.canonical_file) != expected_canonical_sha:
            raise PriceEvidenceBlocked("ORIGINAL_CANONICAL_2026_SHA_MISMATCH")
        if _hash(self.tdcc_file) != expected_tdcc_sha:
            raise PriceEvidenceBlocked("ORIGINAL_G1_TDCC_781_SHA_MISMATCH")
        self.sha256 = expected_canonical_sha
        self.tdcc_sha256 = expected_tdcc_sha
        self.tickers = self._roster()
        if len(self.tickers) != 781:
            raise PriceEvidenceBlocked("ORIGINAL_781_COHORT_NOT_REPRODUCED")
        self.days = self._read_canonical()

    def _roster(self):
        initial = {}
        import gzip
        try:
            with gzip.open(self.tdcc_file, "rt", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                if not {"SnapshotDate","Ticker","TierStatus","Big400Pct"}.issubset(reader.fieldnames or ()):
                    raise PriceEvidenceBlocked("ORIGINAL_TDCC_COHORT_FIELDS_NOT_VERIFIED")
                for row in reader:
                    d = str(row.get("SnapshotDate", ""))
                    ticker = str(row.get("Ticker", ""))
                    if not (d.startswith("2018") and len(d)==8 and
                            len(ticker)==4 and ticker.isdigit() and
                            row.get("TierStatus") == "VALID"):
                        continue
                    if ticker not in initial or d < initial[ticker][0]:
                        initial[ticker] = (d, row.get("Big400Pct"))
        except (OSError, UnicodeError) as e:
            raise PriceEvidenceBlocked("ORIGINAL_TDCC_COHORT_UNREADABLE") from e
        result = set()
        for ticker, (_, raw) in initial.items():
            try:
                if math.isfinite(float(raw)) and float(raw) >= 50:
                    result.add(ticker)
            except (TypeError, ValueError):
                pass
        return result

    def _read_canonical(self):
        rows = {}
        try:
            with self.canonical_file.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not {"Date","Ticker","Open","High","Low","Close"}.issubset(reader.fieldnames or ()):
                    raise PriceEvidenceBlocked("ORIGINAL_CANONICAL_OHLC_FIELDS_NOT_VERIFIED")
                for r in reader:
                    ds = str(r.get("Date", ""))
                    if ds > PINNED_SOURCE_END.isoformat():
                        continue
                    ticker = str(r.get("Ticker", "")).strip()
                    if not (ds.startswith("2026-") and len(ds)==10 and
                            len(ticker)==4 and ticker.isdigit()):
                        continue
                    day = rows.setdefault(ds, {})
                    if ticker in day:
                        raise PriceEvidenceBlocked("ORIGINAL_CANONICAL_PRICE_DUPLICATE_KEY")
                    try:
                        o={key:_n(r[key]) for key in ("Open","High","Low","Close")}
                        if (o["High"] < max(o["Open"],o["Low"],o["Close"]) or
                            o["Low"] > min(o["Open"],o["High"],o["Close"])):
                            raise PriceEvidenceBlocked("ORIGINAL_CANONICAL_OHLC_RANGE_INVALID")
                    except PriceEvidenceBlocked:
                        o=None
                    day[ticker]=o
        except (OSError, UnicodeError) as e:
            raise PriceEvidenceBlocked("ORIGINAL_CANONICAL_2026_UNREADABLE") from e
        if (PINNED_SOURCE_END.isoformat() not in rows
                or len(rows[PINNED_SOURCE_END.isoformat()]) < MIN_ORIGINAL_MARKET_ROWS_PER_DAY):
            raise PriceEvidenceBlocked("PINNED_2026_11_11_SOURCE_MOTHER_NOT_COMPLETE")
        return rows

    def day(self, d: date):
        if d > PINNED_SOURCE_END or d.year != 2026:
            raise PriceEvidenceBlocked("DATE_OUTSIDE_SHA_PINNED_ORIGINAL_MOTHER")
        values = self.days.get(d.isoformat())
        if not isinstance(values, dict) or len(values) < MIN_ORIGINAL_MARKET_ROWS_PER_DAY:
            raise PriceEvidenceBlocked("ORIGINAL_CANONICAL_DAY_COVERAGE_MISSING:" + d.isoformat())
        return values

    def ticker_day(self, d: date, ticker: str):
        if ticker not in self.tickers:
            raise PriceEvidenceBlocked("TICKER_NOT_IN_FIXED_781")
        x = self.day(d).get(ticker)
        if x is None:
            raise PriceEvidenceBlocked("OFFICIAL_TICKER_OHLC_MISSING:" + d.isoformat()+":"+ticker)
        return x

    def atr20(self, d: date, ticker: str, calendar):
        dates = _sessions_ending(calendar, d, 21)
        observations = [self.ticker_day(x, ticker) for x in dates]
        tr = [max(
            c["High"]-c["Low"],
            abs(c["High"]-p["Close"]),
            abs(c["Low"]-p["Close"])
        ) for p,c in zip(observations[:-1],observations[1:])]
        atr = sum(tr)/20
        if not math.isfinite(atr) or atr <= 0:
            raise PriceEvidenceBlocked("ORIGINAL_CANONICAL_ATR20_NOT_VALID")
        return {
            "atr20":round(atr,8),
            "official_close":observations[-1]["Close"],
            "start_session":dates[0].isoformat(),
            "through_session":dates[-1].isoformat(),
            "observation_sessions":21,
            "method":"SMA20_OF_TRUE_RANGE",
            "original_2026_mother_sha256":self.sha256,
            "original_tdcc_fixed_781_sha256":self.tdcc_sha256,
            "prospective_tdcc_publication_certified":False,
            "not_a_broker_price":True,
        }
