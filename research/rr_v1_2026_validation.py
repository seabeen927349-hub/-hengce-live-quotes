#!/usr/bin/env python3
"""Frozen 2026-only validation for HENGCE Residual Reversal V1.

Research only. No production authority. No parameter tuning.
Model/execution rules were frozen before viewing the 2026 result.

Universe: exact daily TWSE electronics table from official MI_INDEX type=13.
Score:
    0.45*(-z_resid5) + 0.20*rank(trend20)
    + 0.15*rank(trend60) + 0.10*rank(liquidity20)
    - 0.10*rank(volatility20)
Filters: z_resid5 < -1.5; trend20 > 0; trend60 > 0;
         liquidity percentile >= 0.30.
Portfolio: top 5 EW; next-session open; exit close after 10 sessions;
           non-overlapping baskets; 1.2% aggregate round-trip cost.

This version only replaces repeated nested rolling recomputation with an equivalent
single-pass state update. Signal formula, filters, dates, costs and execution are
unchanged from the preregistered first implementation.
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

START = date(2025, 5, 1)
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
    s = clean(s).replace(",", "").replace("=", "").replace('"', "")
    if s in {"", "--", "---", "----", "除權息", "除息", "除權"}:
        return None
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
    raw = list(csv.reader(io.StringIO(text)))
    header_idx = None
    for i, row in enumerate(raw):
        joined = "|".join(row)
        if "證券代號" in joined and "證券名稱" in joined and "收盤價" in joined and "開盤價" in joined:
            header_idx = i
            break
    if header_idx is None:
        return {}
    headers = [clean(x) for x in raw[header_idx]]
    out = {}
    for row in raw[header_idx + 1:]:
        if not row:
            continue
        row = row + [""] * max(0, len(headers) - len(row))
        rec = {headers[k]: clean(row[k]) for k in range(len(headers))}
        ticker = clean(rec.get("證券代號", "")).replace("=", "").replace('"', "")
        name = clean(rec.get("證券名稱", ""))
        if not re.fullmatch(r"[0-9A-Za-z]{4,8}", ticker or "") or not name:
            continue
        op = num(rec.get("開盤價", "")); cl = num(rec.get("收盤價", ""))
        hi = num(rec.get("最高價", "")); lo = num(rec.get("最低價", ""))
        turn = num(rec.get("成交金額", "")); vol = num(rec.get("成交股數", ""))
        if cl is None or cl <= 0:
            continue
        out[ticker] = {"ticker": ticker, "name": name, "open": op, "high": hi,
                       "low": lo, "close": cl, "turnover": turn, "volume": vol}
    return out


def parse_electronics_index(text: str):
    raw = list(csv.reader(io.StringIO(text)))
    preferred = ["電子類指數", "電子工業類指數", "電子類報酬指數", "電子工業類報酬指數"]
    found = {}
    for row in raw:
        for j, cell in enumerate(row):
            label = clean(cell)
            if label not in preferred:
                continue
            for c in row[j + 1:]:
                x = num(c)
                if x is not None and x > 0:
                    found[label] = x
                    break
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
            allt = decode(get(make_url(d, "ALLBUT0999")))
            idx, label = parse_electronics_index(allt)
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


def beta60(xs, ys):
    if len(xs) != 60 or len(ys) != 60 or any(x is None for x in xs) or any(y is None for y in ys):
        return None
    mx = sum(xs) / 60.0; my = sum(ys) / 60.0
    vy = sum((y - my) ** 2 for y in ys)
    if vy <= 1e-18:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vy


def stdev(xs):
    return statistics.stdev(xs) if len(xs) >= 2 else None


def pct_rank(values):
    n = len(values)
    if n <= 1:
        return {k: 0.5 for k in values}
    pairs = sorted((v, k) for k, v in values.items())
    ranks = {}; p = 0
    while p < n:
        q = p + 1
        while q < n and pairs[q][0] == pairs[p][0]:
            q += 1
        avg = ((p + q - 1) / 2.0) / (n - 1)
        for j in range(p, q):
            ranks[pairs[j][1]] = avg
        p = q
    return ranks


def main():
    candidate_dates = list(weekdays(START, END))
    fetched = {}; qa = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_day, d): d for d in candidate_dates}
        for n, fut in enumerate(as_completed(futs), 1):
            d, stocks, idx, label, status = fut.result()
            qa.append({"date": d.isoformat(), "status": status, "stocks": len(stocks or {})})
            if status == "PASS":
                fetched[d] = (stocks, idx, label)
            if n % 50 == 0:
                print(f"FETCH {n}/{len(candidate_dates)} pass={len(fetched)}", flush=True)

    hard = [x for x in qa if x["status"].startswith("ERROR") or x["status"] == "INDEX_NOT_FOUND"]
    if hard:
        print(json.dumps({"hard_fetch_failures": hard[:20]}, ensure_ascii=False), file=sys.stderr)
        return 2

    dates = sorted(fetched)
    if not dates or dates[-1] < date(2026, 10, 22):
        raise RuntimeError(f"insufficient trading coverage: {dates[-1] if dates else None}")
    rows = {d: fetched[d][0] for d in dates}
    idx_level = [fetched[d][1] for d in dates]
    idx_ret = [None] + [idx_level[i] / idx_level[i - 1] - 1.0 for i in range(1, len(dates))]
    idx_labels = {}
    for d in dates:
        lab = fetched[d][2]; idx_labels[lab] = idx_labels.get(lab, 0) + 1

    # Per-ticker single-pass state. A missing day resets continuity, exactly matching
    # the original requirement for 120 uninterrupted PIT-electronics observations.
    states = {}
    features_by_i = {}
    for i, d in enumerate(dates):
        current = rows[d]
        feat = {}
        present = set(current)
        # No need to mutate absent states; last_i check forces reset on reappearance.
        for ticker, rec in current.items():
            s = states.get(ticker)
            if s is None or s["last_i"] != i - 1:
                s = {"last_i": i, "closes": [rec["close"]], "turns": [rec["turnover"]],
                     "rets": [], "residuals": []}
                states[ticker] = s
                continue
            prev = s["closes"][-1]
            r = rec["close"] / prev - 1.0
            s["last_i"] = i
            s["closes"].append(rec["close"]); s["turns"].append(rec["turnover"]); s["rets"].append(r)
            # Bound memory but preserve enough for 120 closes/119 returns/60 residuals.
            if len(s["closes"]) > 125:
                s["closes"] = s["closes"][-125:]; s["turns"] = s["turns"][-125:]
            if len(s["rets"]) > 124:
                s["rets"] = s["rets"][-124:]

            if len(s["rets"]) >= 60 and i >= 59:
                b = beta60(s["rets"][-60:], idx_ret[i - 59:i + 1])
                if b is not None and len(s["closes"]) >= 6:
                    resid5 = s["closes"][-1] / s["closes"][-6] - 1.0 - b * (idx_level[i] / idx_level[i - 5] - 1.0)
                    s["residuals"].append((i, resid5, b))
                    if len(s["residuals"]) > 65:
                        s["residuals"] = s["residuals"][-65:]

            if d < SIGNAL_START or d.year != 2026 or i + HOLD >= len(dates):
                continue
            if len(s["closes"]) < 120 or len(s["rets"]) < 119 or len(s["residuals"]) < 60:
                continue
            last60 = s["residuals"][-60:]
            if last60[-1][0] != i or last60[0][0] != i - 59 or any(last60[j][0] != i - 59 + j for j in range(60)):
                continue
            residual_vals = [x[1] for x in last60]
            sd = stdev(residual_vals)
            if sd is None or sd <= 1e-12:
                continue
            z = (residual_vals[-1] - sum(residual_vals) / 60.0) / sd
            trend20 = s["closes"][-1] / s["closes"][-21] - 1.0
            trend60 = s["closes"][-1] / s["closes"][-61] - 1.0
            turns20 = s["turns"][-20:]
            if len(turns20) < 20 or any(x is None or x <= 0 for x in turns20):
                continue
            liq20 = sum(turns20) / 20.0
            v20 = stdev(s["rets"][-20:])
            if v20 is None:
                continue
            feat[ticker] = {"z": z, "beta60": last60[-1][2], "trend20": trend20,
                            "trend60": trend60, "liq20": liq20, "vol20": v20}

        if d < SIGNAL_START or d.year != 2026 or i + HOLD >= len(dates):
            continue
        if not feat:
            features_by_i[i] = []
            continue
        r20 = pct_rank({t: x["trend20"] for t, x in feat.items()})
        r60 = pct_rank({t: x["trend60"] for t, x in feat.items()})
        rlq = pct_rank({t: x["liq20"] for t, x in feat.items()})
        rvl = pct_rank({t: x["vol20"] for t, x in feat.items()})
        ranked = []
        for t, x in feat.items():
            if not (x["z"] < -1.5 and x["trend20"] > 0 and x["trend60"] > 0 and rlq[t] >= 0.30):
                continue
            score = 0.45*(-x["z"]) + 0.20*r20[t] + 0.15*r60[t] + 0.10*rlq[t] - 0.10*rvl[t]
            ranked.append((score, t, x, {"trend20": r20[t], "trend60": r60[t], "liquidity": rlq[t], "volatility": rvl[t]}))
        ranked.sort(reverse=True, key=lambda x: (x[0], x[1]))
        features_by_i[i] = ranked

    baskets = []; next_allowed = 0
    for i, d in enumerate(dates):
        if d.year != 2026 or d < SIGNAL_START or i < next_allowed:
            continue
        ranked = features_by_i.get(i, [])
        if len(ranked) < TOP_N or i + HOLD >= len(dates):
            continue
        chosen = ranked[:TOP_N]
        entry_d, exit_d = dates[i + 1], dates[i + HOLD]
        legs = []; ok = True
        for score, ticker, x, ranks in chosen:
            er = rows[entry_d].get(ticker); xr = rows[exit_d].get(ticker)
            if er is None or xr is None or er["open"] is None or er["open"] <= 0 or xr["close"] is None or xr["close"] <= 0:
                ok = False; break
            gross = xr["close"] / er["open"] - 1.0
            legs.append({"ticker": ticker, "name": er["name"], "score": score,
                         "z_resid5": x["z"], "beta60": x["beta60"],
                         "entry_open": er["open"], "exit_close": xr["close"],
                         "gross_return": gross, "net_return_1p2pct": gross - COST,
                         "ranks": ranks})
        if not ok:
            continue
        basket_net = sum(x["net_return_1p2pct"] for x in legs) / TOP_N
        baskets.append({"signal_date": d.isoformat(), "entry_date": entry_d.isoformat(),
                        "exit_date": exit_d.isoformat(), "basket_net_return": basket_net, "legs": legs})
        next_allowed = i + HOLD

    nav = 1.0; peak = 1.0; max_dd = 0.0
    for b in baskets:
        nav *= 1.0 + b["basket_net_return"]
        peak = max(peak, nav); max_dd = min(max_dd, nav / peak - 1.0)
    wins = sum(b["basket_net_return"] > 0 for b in baskets)
    result = {
        "model": "HENGCE_RESIDUAL_REVERSAL_V1_FROZEN",
        "validation_period": ["2026-01-01", END.isoformat()],
        "data_source": "TWSE MI_INDEX official daily CSV; type=13 exact PIT electronics table; official electronics index",
        "electronics_index_labels": idx_labels,
        "implementation_note": "rolling computation optimized after preregistration; model/execution unchanged; no 2026 outcome was viewed before this run",
        "execution": {"top_n": TOP_N, "entry": "next_session_open", "holding_sessions": HOLD,
                      "exit": "close_on_signal_plus_10th_session", "non_overlapping_baskets": True,
                      "round_trip_cost": COST, "equal_weight": True,
                      "fill_assumption": "research next-open price; no queue/allocation claim"},
        "frozen_filters": {"z_resid5_lt": -1.5, "trend20_gt": 0, "trend60_gt": 0, "liquidity_rank_gte": 0.30},
        "score": "0.45*(-z_resid5)+0.20*rank_trend20+0.15*rank_trend60+0.10*rank_liquidity20-0.10*rank_volatility20",
        "trading_dates_available": len(dates), "first_trading_date": dates[0].isoformat(), "last_trading_date": dates[-1].isoformat(),
        "baskets": len(baskets), "stock_legs": len(baskets)*TOP_N,
        "wins": wins, "losses": len(baskets)-wins,
        "win_rate": wins/len(baskets) if baskets else None,
        "compounded_after_cost_return": nav-1.0,
        "max_drawdown_on_basket_nav": max_dd,
        "mean_basket_return": sum(b["basket_net_return"] for b in baskets)/len(baskets) if baskets else None,
        "basket_details": baskets,
        "authority": {"research_only": True, "capital_authority_twd": 0, "production_promotion": False},
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    compact = {k: result[k] for k in ["baskets","stock_legs","wins","losses","win_rate","compounded_after_cost_return","max_drawdown_on_basket_nav","mean_basket_return"]}
    compact["first_entry"] = baskets[0]["entry_date"] if baskets else None
    compact["last_exit"] = baskets[-1]["exit_date"] if baskets else None
    print("FINAL_RESULT_JSON="+json.dumps(compact, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
