#!/usr/bin/env python3
"""Patched runner for HENGCE TDCC Monster V1 targeted historical backfill.

The TDCC historical HTML table carries the holding-grade ordinal in column `序`.
The human-readable `持股/單位數分級` column contains ranges such as 1,000-5,000
and MUST NOT be parsed as the grade number.
"""
from __future__ import annotations

import re

import hengce_tdcc_monster_pit_backfill as m


def fixed_summarize_table(t):
    cols = list(t.columns)

    # Official historical table observed by existing HENGCE probe:
    # 序 | 持股/單位數分級 | 人數 | 股數/單位數 | 占集保庫存數比例 (%)
    ordinal_col = next((c for c in cols if str(c).strip() == "序"), None)
    if ordinal_col is None:
        raise RuntimeError(f"TDCC_HIST_ORDINAL_COL_NOT_FOUND:{cols}")

    holders_col = m.choose_col(cols, [lambda c: "人數" in c], "holders")
    shares_candidates = [
        c for c in cols
        if ("股數" in c or "單位數" in c)
        and "比例" not in c
        and "分級" not in c
        and str(c).strip() != "序"
    ]
    if not shares_candidates:
        raise RuntimeError(f"TDCC_HIST_COL_NOT_FOUND:shares:{cols}")
    shares_col = shares_candidates[0]

    pct_candidates = [c for c in cols if "比例" in c]
    if not pct_candidates:
        raise RuntimeError(f"TDCC_HIST_COL_NOT_FOUND:pct:{cols}")
    pct_col = pct_candidates[0]

    range_col = next((c for c in cols if "持股" in c or "分級" in c), None)

    grades = {}
    total_row = None
    for _, row in t.iterrows():
        raw_ord = str(row.get(ordinal_col, "")).strip()
        lvl = None
        mm = re.fullmatch(r"\s*(\d{1,2})(?:\.0)?\s*", raw_ord)
        if mm:
            n = int(mm.group(1))
            if 1 <= n <= 17:
                lvl = n

        rec = {
            "holders": m.clean_int(row.get(holders_col)),
            "shares": m.clean_int(row.get(shares_col)),
            "pct": m.clean_float(row.get(pct_col)),
            "raw_level": raw_ord,
        }
        range_text = str(row.get(range_col, "")) if range_col else ""
        if lvl is not None:
            grades[lvl] = rec
        elif (
            "合計" in raw_ord or "總計" in raw_ord
            or "合計" in range_text or "總計" in range_text
        ):
            total_row = rec

    need = {12, 13, 14, 15}
    if not need.issubset(grades):
        raise RuntimeError(f"TDCC_HIST_GRADES_INCOMPLETE:{sorted(grades)}")
    for g in need:
        if (
            grades[g]["holders"] is None
            or grades[g]["shares"] is None
            or grades[g]["pct"] is None
        ):
            raise RuntimeError(f"TDCC_HIST_GRADE_MISSING_VALUE:{g}:{grades[g]}")

    big400 = [grades[g] for g in (12, 13, 14, 15)]
    g15 = grades[15]
    return {
        "Big400Holders": sum(x["holders"] for x in big400),
        "Big400Shares": sum(x["shares"] for x in big400),
        "Big400Pct": round(sum(x["pct"] for x in big400), 6),
        "Big1000Holders": g15["holders"],
        "Big1000Shares": g15["shares"],
        "Big1000Pct": round(g15["pct"], 6),
        "TotalHolders": total_row["holders"] if total_row else None,
        "TotalShares": total_row["shares"] if total_row else None,
        "ParsedGrades": sorted(grades),
    }


m.summarize_table = fixed_summarize_table

if __name__ == "__main__":
    m.main()
