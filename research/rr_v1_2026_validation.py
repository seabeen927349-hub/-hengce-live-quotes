#!/usr/bin/env python3
"""Frozen 2026-only validation for HENGCE Residual Reversal V1.

Research only. No production authority. No parameter tuning.

Universe: exact daily TWSE electronics table from official MI_INDEX type=13.
Signal model (fixed before seeing 2026 result):
    score = 0.45*(-z_resid5) + 0.20*rank(trend20)
            + 0.15*rank(trend60) + 0.10*rank(liquidity20)
            - 0.10*rank(volatility20)
Filters:
    z_resid5 < -1.5, trend20 > 0, trend60 > 0,
    liquidity rank >= 0.30.
Portfolio:
    top 5, equal-weight, next-session open entry, close after 10 sessions,
    non-overlapping baskets, 1.2% aggregate round-trip cost.

The electronic-market factor is the official TWSE electronics price index from
MI_INDEX (ALLBUT0999 fallback request when it is not present in type=13 output).
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

START = date(2025, 5, 1)      # enough pre-2026 lookback for beta60 + resid5 z60
END = date(2026, 10, 23)
SIGNAL_START = date(2026, 1, 1)
COST = 0.012
HOLD = 10
TOP_N = 5
MAX_WORKERS = 6
URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
UA = "Mozilla/5.0 (HENGCE RR-V1 2026 frozen research validation)"
OUT = Path("research/rr_v1_2026_validation_result.json")


def clean(s: str) -> str:
    return (s or "").strip().replace("\ufeff", "")


def num(s: str):
    s = clean(s).replace(",", "")
    s = s.replace("=", "").replace('"', "")
    if s in {"", "--", "---", "----", "除權息", "除息", "除權"}:
        return None
    # TWSE can prefix comparison symbols/signs in some fields; price/amount fields
    # should be numeric. Fail closed instead of guessing.
    try:
        x = float(s)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def decode(b: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace")


def get(url: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                b = r.read()
                if getattr(r, "status", 200) == 200 and b:
                    return b
                last = RuntimeError(f"HTTP/EMPTY {getattr(r, 'status', None)} {len(b)}")
        except Exception as exc:
            last = exc
        time.sleep(0.7 * (2 ** attempt))
    raise RuntimeError(f"fetch failed: {url}: {type(last).__name__}: {last}")


def make_url(d: date, kind: str) -> str:
    q = urllib.parse.urlencode({"date": d.strftime("%Y%m%d"), "type": kind, "response": "csv"})
    return f"{URL}?{q}"


def parse_stocks(text: str):
    rows = list(csv.reader(io.StringIO(text)))
    hi = None
    for i, row in enumerate(rows):
        joined = "|".join(row)
        if "證券代號" in joined and "證券名稱" in joined and "收盤價" in joined and "開盤價" in joined:
            hi = i
            break
    if hi is None:
        return {}
    headers = [clean(x) for x in rows[hi]]
    out = {}
    for row in rows[hi + 1:]:
        if not row:
            continue
        row = row + [""] * max(0, len(headers) - len(row))
        rec = {headers[k]: clean(row[k]) for k in range(len(headers))}
        ticker = clean(rec.get("證券代號", "")).replace("=", "").replace('"', "")
        name = clean(rec.get("證券名稱", ""))
        if not re.fullmatch(r"[0-9A-Za-z]{4,8}", ticker or "") or not name:
            continue
        op = num(rec.get("開盤價", "")); hi_v = num(rec.get("最高價", "")); lo_v = num(rec.get("最低價", "")); cl = num(rec.get("收盤價", ""))
        turn = num(rec.get("成交金額", "")); vol = num(rec.get("成交股數", ""))
        if cl is None:
            continue
        out[ticker] = {
            "ticker": ticker, "name": name, "open": op, "high": hi_v,
            "low": lo_v, "close": cl, "turnover": turn, "volume": vol,
        }
    return out


def parse_electronics_index(text: str):
    rows = list(csv.reader(io.StringIO(text)))
    preferred = [
        "電子類指數", "電子工業類指數",
        "電子類報酬指數", "電子工業類報酬指數",
    ]
    found = {}
    for row in rows:
        if not row:
            continue
        for idx, cell in enumerate(row):
            label = clean(cell)
            if label in preferred:
                value = None
                for c in row[idx + 1:]:
                    x = num(c)
                    if x is not None and x > 0:
                        value = x
                        break
                if value is not None:
                    found[label] = value
    for label in preferred:
        if label in found:
            return found[label], label
    return None, None


def fetch_day(d: date):
    try:
        t13 = decode(get(make_url(d, "13")))
        stocks = parse_stocks(t13)
        if not stocks:
            return d, None, None, None, "NO_DATA"
        idx, label = parse_electronics_index(t13)
        if idx is None:
            alltxt = decode(get(make_url(d, "ALLBUT0999")))
            idx, label = parse_electronics_index(alltxt)
        if idx is None:
            return d, stocks, None, None, "INDEX_NOT_FOUND"
        return d, stocks, idx, label, "PASS"
    except Exception as exc:
        return d, None, None, None, f"ERROR:{type(exc).__name__}:{str(exc)[:160]}"


def weekdays(a: date, b: date):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def cov_beta(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
    vy = sum((y - my) ** 2 for y in ys)
    if vy <= 1e-18:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vy


def stdev(xs):
    return statistics.stdev(xs) if len(xs) >= 2 else None


def pct_rank(values):
    """Ascending percentile ranks in [0,1], average rank for ties."""
    n = len(values)
    if n <= 1:
        return {k: 0.5 for k in values}
    pairs = sorted((v, k) for k, v in values.items())
    ranks = {}
    p = 0
    while p < n:
        q = p + 1
        while q < n and pairs[q][0] == pairs[p][0]:
            q += 1
        avg = ((p + q - 1) / 2) / (n - 1)
        for j in range(p, q):
            ranks[pairs[j][1]] = avg
        p = q
    return ranks


def main():
    candidates = list(weekdays(START, END))
    fetched = {}
    qa = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_day, d): d for d in candidates}
        for n, fut in enumerate(as_completed(futs), 1):
            d, stocks, idx, label, status = fut.result()
            qa.append({"date": d.isoformat(), "status": status, "stocks": len(stocks or {})})
            if status == "PASS":
                fetched[d] = (stocks, idx, label)
            if n % 50 == 0:
                print(f"FETCH {n}/{len(candidates)} pass={len(fetched)}", flush=True)

    bad_hard = [x for x in qa if x["status"].startswith("ERROR") or x["status"] == "INDEX_NOT_FOUND"]
    if bad_hard:
        print(json.dumps({"hard_fetch_failures": bad_hard[:20]}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)

    dates = sorted(fetched)
    if not dates or dates[-1] < date(2026, 10, 22):
        raise RuntimeError(f"insufficient trading coverage: {dates[-1] if dates else None}")

    rows = {d: fetched[d][0] for d in dates}
    idx_level = [fetched[d][1] for d in dates]
    idx_label_counts = {}
    for d in dates:
        lab = fetched[d][2]
        idx_label_counts[lab] = idx_label_counts.get(lab, 0) + 1
    idx_ret = [None]
    for i in range(1, len(dates)):
        idx_ret.append(idx_level[i] / idx_level[i - 1] - 1.0)

    features_by_i = {}
    for i, d in enumerate(dates):
        if d < SIGNAL_START or d.year != 2026 or i < 119:
            continue
        # only dates for which a full 10-session exit exists by END
        if i + HOLD >= len(dates):
            continue
        feat = {}
        current = rows[d]
        for ticker in current:
            # Need uninterrupted daily observations for beta/residual history.
            hist = []
            valid = True
            for k in range(i - 119, i + 1):
                r = rows[dates[k]].get(ticker)
                if r is None or r["close"] is None or r["close"] <= 0:
                    valid = False; break
                hist.append(r)
            if not valid:
                continue
            # turnover must be known/positive over current 20 sessions
            if any((x["turnover"] is None or x["turnover"] <= 0) for x in hist[-20:]):
                continue
            stock_rets = [None]
            for k in range(1, len(hist)):
                stock_rets.append(hist[k]["close"] / hist[k - 1]["close"] - 1.0)

            residuals = []
            beta_now = None
            # jloc 60..119 corresponds to global j = i-59 .. i
            for jloc in range(60, 120):
                g = i - 119 + jloc
                sx = stock_rets[jloc - 59:jloc + 1]
                my = idx_ret[g - 59:g + 1]
                if any(x is None for x in sx) or any(y is None for y in my):
                    valid = False; break
                beta = cov_beta(sx, my)
                if beta is None or not math.isfinite(beta):
                    valid = False; break
                stock5 = hist[jloc]["close"] / hist[jloc - 5]["close"] - 1.0
                market5 = idx_level[g] / idx_level[g - 5] - 1.0
                resid = stock5 - beta * market5
                residuals.append(resid)
                if jloc == 119:
                    beta_now = beta
            if not valid or len(residuals) != 60:
                continue
            sd = stdev(residuals)
            if sd is None or sd <= 1e-12:
                continue
            z = (residuals[-1] - (sum(residuals) / len(residuals))) / sd
            trend20 = hist[-1]["close"] / hist[-21]["close"] - 1.0
            trend60 = hist[-1]["close"] / hist[-61]["close"] - 1.0
            liq20 = sum(x["turnover"] for x in hist[-20:]) / 20.0
            v20 = stdev(stock_rets[-20:])
            if v20 is None:
                continue
            feat[ticker] = {
                "z": z, "beta60": beta_now, "trend20": trend20,
                "trend60": trend60, "liq20": liq20, "vol20": v20,
            }

        if not feat:
            features_by_i[i] = []
            continue
        r20 = pct_rank({t: x["trend20"] for t, x in feat.items()})
        r60 = pct_rank({t: x["trend60"] for t, x in feat.items()})
        rlq = pct_rank({t: x["liq20"] for t, x in feat.items()})
        rvl = pct_rank({t: x["vol20"] for t, x in feat.items()})
        out = []
        for t, x in feat.items():
            if not (x["z"] < -1.5 and x["trend20"] > 0 and x["trend60"] > 0 and rlq[t] >= 0.30):
                continue
            score = 0.45 * (-x["z"]) + 0.20 * r20[t] + 0.15 * r60[t] + 0.10 * rlq[t] - 0.10 * rvl[t]
            out.append((score, t, x, {"trend20": r20[t], "trend60": r60[t], "liquidity": rlq[t], "volatility": rvl[t]}))
        out.sort(reverse=True, key=lambda x: (x[0], x[1]))
        features_by_i[i] = out

    baskets = []
    next_allowed = 0
    for i, d in enumerate(dates):
        if d.year != 2026 or d < SIGNAL_START or i < next_allowed:
            continue
        ranked = features_by_i.get(i, [])
        if len(ranked) < TOP_N or i + HOLD >= len(dates):
            continue
        chosen = ranked[:TOP_N]
        entry_d = dates[i + 1]
        exit_d = dates[i + HOLD]
        legs = []
        ok = True
        for score, ticker, x, ranks in chosen:
            er = rows[entry_d].get(ticker); xr = rows[exit_d].get(ticker)
            if er is None or xr is None or er["open"] is None or er["open"] <= 0 or xr["close"] is None or xr["close"] <= 0:
                ok = False; break
            gross = xr["close"] / er["open"] - 1.0
            net = gross - COST
            legs.append({
                "ticker": ticker, "name": er["name"], "score": score,
                "z_resid5": x["z"], "beta60": x["beta60"],
                "entry_open": er["open"], "exit_close": xr["close"],
                "gross_return": gross, "net_return_1p2pct": net,
                "ranks": ranks,
            })
        if not ok:
            continue
        basket_net = sum(x["net_return_1p2pct"] for x in legs) / TOP_N
        baskets.append({
            "signal_date": d.isoformat(), "entry_date": entry_d.isoformat(),
            "exit_date": exit_d.isoformat(), "basket_net_return": basket_net,
            "legs": legs,
        })
        # May signal again on the exit close and enter the following session.
        next_allowed = i + HOLD

    nav = 1.0
    peak = 1.0
    max_dd = 0.0
    for b in baskets:
        nav *= 1.0 + b["basket_net_return"]
        peak = max(peak, nav)
        max_dd = min(max_dd, nav / peak - 1.0)
    wins = sum(b["basket_net_return"] > 0 for b in baskets)
    losses = sum(b["basket_net_return"] <= 0 for b in baskets)
    result = {
        "model": "HENGCE_RESIDUAL_REVERSAL_V1_FROZEN",
        "validation_period": ["2026-01-01", END.isoformat()],
        "data_source": "TWSE MI_INDEX official daily CSV; type=13 exact PIT electronics table; official electronics index",
        "electronics_index_labels": idx_label_counts,
        "execution": {
            "top_n": TOP_N, "entry": "next_session_open", "holding_sessions": HOLD,
            "exit": "close_on_signal_plus_10th_session", "non_overlapping_baskets": True,
            "round_trip_cost": COST, "equal_weight": True,
            "fill_assumption": "research next-open price; no queue/allocation claim",
        },
        "frozen_filters": {"z_resid5_lt": -1.5, "trend20_gt": 0, "trend60_gt": 0, "liquidity_rank_gte": 0.30},
        "score": "0.45*(-z_resid5)+0.20*rank_trend20+0.15*rank_trend60+0.10*rank_liquidity20-0.10*rank_volatility20",
        "trading_dates_available": len(dates),
        "first_trading_date": dates[0].isoformat(),
        "last_trading_date": dates[-1].isoformat(),
        "baskets": len(baskets),
        "stock_legs": len(baskets) * TOP_N,
        "wins": wins, "losses": losses,
        "win_rate": (wins / len(baskets)) if baskets else None,
        "compounded_after_cost_return": nav - 1.0,
        "max_drawdown_on_basket_nav": max_dd,
        "mean_basket_return": (sum(b["basket_net_return"] for b in baskets) / len(baskets)) if baskets else None,
        "basket_details": baskets,
        "authority": {"research_only": True, "capital_authority_twd": 0, "production_promotion": False},
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact = {k: result[k] for k in ["baskets", "stock_legs", "wins", "losses", "win_rate", "compounded_after_cost_return", "max_drawdown_on_basket_nav", "mean_basket_return"]}
    compact["first_entry"] = baskets[0]["entry_date"] if baskets else None
    compact["last_exit"] = baskets[-1]["exit_date"] if baskets else None
    print("FINAL_RESULT_JSON=" + json.dumps(compact, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
