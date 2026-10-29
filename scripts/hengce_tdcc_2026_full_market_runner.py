#!/usr/bin/env python3
"""Runner for HENGCE 2026 TDCC full-market backfill.

Eliminates the intermediate ticker-copy file. The candidate universe is derived
byte-for-byte from the validated HENGCE consolidated TDCC mother already in repo.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
from pathlib import Path

import hengce_tdcc_2026_jan_apr_backfill as b

PARENT = b.ROOT / "ownership" / "tdcc" / "consolidated_candidate" / "tdcc_fourth_leg_best_available.csv.gz"
EXPECTED_PARENT_GZIP_SHA256 = "d10a3576e09f42041135dae3884f59c73e555c05ce23e524131feee94f1e8b8f"
EXPECTED_UNION_SERIALIZED_SHA256 = "70229d9b1bcef321deaad73b96fcb65c84227e30d173cd0b20a7e7e524a52936"
EXPECTED_UNIQUE_TICKERS = 3091


def sha256_bytes(x: bytes) -> str:
    return hashlib.sha256(x).hexdigest()


def load_candidates_from_parent() -> list[str]:
    if not PARENT.exists():
        raise RuntimeError(f"HENGCE_PARENT_MISSING:{PARENT}")
    parent_raw = PARENT.read_bytes()
    parent_sha = sha256_bytes(parent_raw)
    if parent_sha != EXPECTED_PARENT_GZIP_SHA256:
        raise RuntimeError(f"HENGCE_PARENT_GZIP_SHA_MISMATCH:{parent_sha}")

    tickers = set()
    with gzip.open(PARENT, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ticker = str(row.get("Ticker", "")).strip()
            if len(ticker) == 4 and ticker.isdigit():
                tickers.add(ticker)
    out = sorted(tickers)
    if len(out) != EXPECTED_UNIQUE_TICKERS:
        raise RuntimeError(f"HENGCE_PARENT_UNION_COUNT_CHANGED:{len(out)}")

    canonical_serialization = ("Ticker\n" + "\n".join(out) + "\n").encode("utf-8")
    union_sha = sha256_bytes(canonical_serialization)
    if union_sha != EXPECTED_UNION_SERIALIZED_SHA256:
        raise RuntimeError(f"HENGCE_PARENT_UNION_SHA_MISMATCH:{union_sha}")
    return out


# Replace only the candidate-loader. All TDCC transport/parser/fail-closed gates
# remain the existing HENGCE implementation in the base module.
b.load_candidates = load_candidates_from_parent

if __name__ == "__main__":
    b.main()
