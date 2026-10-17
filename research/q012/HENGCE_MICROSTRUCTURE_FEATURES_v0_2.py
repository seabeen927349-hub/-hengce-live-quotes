#!/usr/bin/env python3
"""Deterministic, provenance-preserving Q-012 event feature extractor."""
import argparse
import json
import math
from collections import Counter, deque

WINDOWS = (30, 60, 300)
EPS = 1e-12
BOOK_FIELDS = ("mid", "microprice", "obi5", "bid5", "ask5", "best_bid", "best_ask")


def micros_to_sec(us):
    return float(us) / 1_000_000.0


def finite_float(value):
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def book_features(payload):
    bids = payload.get("bids") or []
    asks = payload.get("asks") or []
    if not bids or not asks:
        return None
    try:
        bid_rows = [(finite_float(x.get("price")), finite_float(x.get("size"))) for x in bids[:5]]
        ask_rows = [(finite_float(x.get("price")), finite_float(x.get("size"))) for x in asks[:5]]
        if any(price is None or price<=0 or size is None or size<0 for price,size in bid_rows+ask_rows):
            return None
        if bid_rows[0][0]>ask_rows[0][0] or bid_rows[0][1]+ask_rows[0][1]<=0:
            return None
        bid_size = sum(size for _, size in bid_rows)
        ask_size = sum(size for _, size in ask_rows)
        best_bid, best_ask = bid_rows[0][0], ask_rows[0][0]
        b1, a1 = bid_rows[0][1], ask_rows[0][1]
        mid = (best_bid + best_ask) / 2
        microprice = (best_ask * b1 + best_bid * a1) / max(b1 + a1, EPS)
        obi5 = (bid_size - ask_size) / max(bid_size + ask_size, EPS)
        return {
            "mid": mid,
            "microprice": microprice,
            "obi5": obi5,
            "bid5": bid_size,
            "ask5": ask_size,
            "best_bid": best_bid,
            "best_ask": best_ask,
        }
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def aggressor(payload):
    price = finite_float(payload.get("price"))
    bid = finite_float(payload.get("bid"))
    ask = finite_float(payload.get("ask"))
    if price is None:
        return 0
    if ask is not None and price >= ask:
        return 1
    if bid is not None and price <= bid:
        return -1
    return 0


def _row_key(row):
    t, channel, payload, _valid = row
    priority = 0 if channel == "books" else 1 if channel == "trades" else 2
    serial = str(payload.get("serial") or "")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (t, priority, str(payload.get("symbol") or ""), serial, canonical)


def load(paths):
    rows = []
    for file_path in paths:
        with open(file_path, encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON in {file_path}:{line_number}") from exc
                payload = record.get("payload", {})
                timestamp = payload.get("time")
                if timestamp is None:
                    continue
                channel = record.get("channel")
                if channel not in ("books", "trades"):
                    continue
                rows.append((micros_to_sec(timestamp), channel, payload, record.get("validContinuous", True)))
    return sorted(rows, key=_row_key)


def compute(rows):
    latest_book = {}
    trades = deque()
    output = []
    for t, channel, payload, valid in sorted(rows, key=_row_key):
        symbol = payload.get("symbol")
        if not symbol or not valid:
            continue
        if channel == "books":
            features = book_features(payload)
            book_time = t
            prior = latest_book.get(symbol)
            canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            ambiguous = bool(prior and prior[0] == book_time and prior[2] != canonical)
            if prior and prior[0] == book_time:
                ambiguous = ambiguous or prior[3]
            latest_book[symbol] = (book_time, features, canonical, ambiguous)
            continue
        if channel != "trades":
            continue

        side = aggressor(payload)
        size = finite_float(payload.get("size")) or 0.0
        trades.append((t, symbol, side, size))
        cutoff = t - max(WINDOWS)
        while trades and trades[0][0] < cutoff:
            trades.popleft()

        book = latest_book.get(symbol)
        book_time = book[0] if book else None
        age_ms = round((t - book_time) * 1000.0, 3) if book else None
        trade_bid = finite_float(payload.get("bid"))
        trade_ask = finite_float(payload.get("ask"))
        if not book:
            book_status = "NO_PRIOR_BOOK"
            quote_match = None
        elif book[1] is None:
            book_status = "INVALID_BOOK"
            quote_match = None
        elif book[3]:
            book_status = "AMBIGUOUS_SAME_TIMESTAMP_BOOK"
            quote_match = None
        elif trade_bid is None or trade_ask is None:
            book_status = "TRADE_QUOTE_MISSING"
            quote_match = None
        else:
            quote_match = book[1]["best_bid"] == trade_bid and book[1]["best_ask"] == trade_ask
            book_status = "TOP_OF_BOOK_MATCH" if quote_match else "TOP_OF_BOOK_MISMATCH"

        aligned_features = book[1] if book_status == "TOP_OF_BOOK_MATCH" else {field: None for field in BOOK_FIELDS}
        record = {
            "time": t,
            "symbol": symbol,
            "trade_price": finite_float(payload.get("price")),
            "trade_size": size,
            "aggressor": side,
            "book_time": book_time,
            "book_age_ms": age_ms,
            "book_quote_match": quote_match,
            "book_feature_status": book_status,
            **aligned_features,
        }
        for window in WINDOWS:
            members = [trade for trade in trades if trade[1] == symbol and trade[0] >= t - window]
            buy = sum(quantity for _, _, trade_side, quantity in members if trade_side > 0)
            sell = sum(quantity for _, _, trade_side, quantity in members if trade_side < 0)
            total = buy + sell
            record[f"ati_{window}s"] = (buy - sell) / max(total, EPS)
            record[f"aggr_vol_{window}s"] = total
            record[f"net_aggr_{window}s"] = buy - sell
        output.append(record)
    return output


def summarize(rows):
    counts = Counter(row["book_feature_status"] for row in rows)
    return {
        "trade_rows": len(rows),
        "aligned_book_rows": counts.get("TOP_OF_BOOK_MATCH", 0),
        "book_feature_status_counts": dict(sorted(counts.items())),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary", default=None)
    parser.add_argument("--require-aligned", action="store_true")
    args = parser.parse_args()
    rows = compute(load(args.files))
    with open(args.out, "w", encoding="utf-8") as output_file:
        for row in rows:
            output_file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    summary = summarize(rows)
    if args.require_aligned and summary["aligned_book_rows"] == 0:
        summary["status"] = "QUALITY_FAIL_NO_ALIGNED_BOOK_ROWS"
        summary["schema"] = "HENGCE_Q012_FEATURES_V0_2"
        summary["out"] = args.out
        summary_path = args.summary or args.out + ".summary.json"
        with open(summary_path, "w", encoding="utf-8") as summary_file:
            json.dump(summary, summary_file, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps(summary, ensure_ascii=False))
        raise SystemExit(12)
    summary["status"] = "OK" if rows else "NO_TRADE_ROWS"
    summary["schema"] = "HENGCE_Q012_FEATURES_V0_2"
    summary["out"] = args.out
    summary_path = args.summary or args.out + ".summary.json"
    with open(summary_path, "w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, ensure_ascii=False, indent=2, allow_nan=False)
    summary["summary"] = summary_path
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
