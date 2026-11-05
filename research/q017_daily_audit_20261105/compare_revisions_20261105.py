#!/usr/bin/env python3
"""Q017 retired analytical AB test: raw vs precommitted R1; never trading authority.

Same frozen full-2026 EOD-open shadow and GO dates for all candidates.
Modified policy checks are compared on the identical research cohort.
Features are point-in-time at or before signal-day EOD. All entries on the
NEXT session OPEN; exits by predetermined signal session +9 CLOSE.
Returns account for conservative full broker fees/tax/slippage.
Live 09:01 replay is not possible except for preserved 10/21,10/22 snapshots.
"""
from __future__ import annotations
import json,math,statistics
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
from run_full_2026 import ROOT, OUT, ARCH, prices_by_date

DATA=OUT/"full_2026_counterfactual_20261105.json"
ASOF="2026-11-04"
BUY_COST=0.001425+0.001  # brokerage + buy slippage
SELL_COST=0.001425+0.003+0.001 # brokerage, sale tax, sell slippage
HORIZONS=(2,5,10)
# FIXED BEFORE EVALUATION:
# R1: 40% of tracked electronics > 20-day MA by prior close;
# stock prior close > its MA20; on signal-day close > open AND > previous close;
# enter next-day OPEN, time-exit at D10 signal-date CLOSE;
# if any earlier CLOSE falls >=8% below entry, exit following open.
MIN_MARKET_BREADTH=.40
STOP_PCT=.08
PRECOMMITTED_POLICIES={
    "BASE_NEXT_OPEN_NO_STOP":("ALL",None),
    "BASE_NEXT_OPEN_STOP8":("ALL",.08),
    "BREADTH40_NO_STOP":("BREADTH40",None),
    "PREV_ABOVE_MA20_NO_STOP":("PREV_ABOVE_MA20",None),
    "CONFIRM_EOD_NO_STOP":("CONFIRM_EOD",None),
    "CONFIRM_EOD_STOP8":("CONFIRM_EOD",.08),
    "BREADTH40_AND_CONFIRM_STOP8":("BREADTH40_AND_CONFIRM",.08),
    "TREND_AND_CONFIRM_STOP8":("TREND_AND_CONFIRM",.08),
    "R1_BREADTH_TREND_CONFIRM_STOP8":("R1",.08)
}
def pct(v):return None if v is None else round(100*v,3)
def ag(a):
    if not a:return {"n":0,"mean":None,"median":None,"positive":0,"win_rate":None,"worst":None,"best":None}
    a=sorted(a)
    return {"n":len(a),"mean":pct(sum(a)/len(a)),
            "median":pct(statistics.median(a)),
            "positive":sum(v>0 for v in a),
            "win_rate":round(sum(v>0 for v in a)/len(a),4),
            "worst":pct(a[0]),"best":pct(a[-1])}
def priced_net(entry,exit):
    return exit*(1-SELL_COST)/(entry*(1+BUY_COST))-1
def breadth_history(by_day,by_t):
    days=sorted(by_day)
    dates={t:[x["date"] for x in a] for t,a in by_t.items()}
    breadth={}
    for idx,d in enumerate(days):
        if idx==0:continue
        prior=days[idx-1]
        ok=total=0
        # All usable electronic members on prior completed date.
        for t in by_day[prior]:
            arr=by_t[t];j=bisect_left(dates[t],d)
            if j<20:continue
            if arr[j-1]["date"]!=prior:continue
            avg=sum(z["close"] for z in arr[j-20:j])/20
            if avg<=0:continue
            total+=1
            ok+=arr[j-1]["close"]>avg
        breadth[d]=ok/total if total else None
    return breadth
def calc_trade(signal,by_day,days,idx,stop,horizon):
    d=signal["entry_day"];t=signal["ticker"];j=idx[d]
    if j+horizon-1>=len(days) or j+1>=len(days):
        return {"state":"UNMATURED"}
    nextday=days[j+1];lastday=days[j+horizon-1]
    entry_row=by_day[nextday].get(t)
    last_row=by_day[lastday].get(t)
    if not entry_row or not last_row or not entry_row["open"] or not last_row["close"]:
        return {"state":"MISSING_PRICE"}
    p=entry_row["open"];limit=p*(1-stop) if stop is not None else None
    exit_row=last_row
    reason="TIME_EXIT_D"+str(horizon)
    if stop is not None:
        # Signal day is not in the exit check; next-day open is the actual
        # entry. Stop triggers at CLOSE and executes FOLLOWING OPEN.
        for k in range(j+1,j+horizon-1):
            row=by_day[days[k]].get(t)
            if not row or not row["close"]:return {"state":"MISSING_PRICE"}
            if row["close"]<=limit:
                follow=by_day[days[k+1]].get(t)
                if not follow or not follow["open"]:return {"state":"MISSING_NEXT_OPEN"}
                exit_row=follow
                reason="STOP_NEXT_OPEN"
                break
    q=exit_row["open"] if reason=="STOP_NEXT_OPEN" else exit_row["close"]
    return {"state":"MATURED","return":priced_net(p,q),
            "gross_return":q/p-1,"entry_price":p,"exit_price":q,
            "entry_session":nextday,
            "exit_session":exit_row["date"],"reason":reason,
            "holding_to_exit":list(days).index(exit_row["date"])-j}
def is_eligible(p,policy):
    a=p["metrics"]
    if policy=="ALL":return True
    broad=a["market_breadth_prior"]
    trend=(a["prev_above_ma20"] is True)
    conf=(a["signal_day_close_confirmation"] is True)
    if policy=="BREADTH40":return broad is not None and broad>=MIN_MARKET_BREADTH
    if policy=="PREV_ABOVE_MA20":return trend
    if policy=="CONFIRM_EOD":return conf
    if policy=="BREADTH40_AND_CONFIRM":return broad is not None and broad>=MIN_MARKET_BREADTH and conf
    if policy=="TREND_AND_CONFIRM":return trend and conf
    if policy=="R1":return broad is not None and broad>=MIN_MARKET_BREADTH and trend and conf
    raise ValueError(policy)
def load():
    j=json.loads(DATA.read_text())
    by_day,by_t=prices_by_date()
    days=sorted(by_day);idx={d:i for i,d in enumerate(days)}
    assert days[-1]==ASOF and len(days)>=200
    breadth=breadth_history(by_day,by_t)
    points=[]
    for p in j["signals"]:
        d=p["entry_day"];t=p["ticker"];row=by_day[d].get(t)
        if row is None:raise ValueError("NO_SIGNAL_DAY_PRICE "+d+" "+t)
        prevclose=p["open"]/(1+(p["residual"]+p["beta"]*next(x for x in j["daily"] if x["date"]==d)["sox1"])) if p["open"] else None
        # Strictly use record's pre_signal prior close rather than a derived estimate.
        x=p.get("prev5")
        metrics={
            "market_breadth_prior":breadth.get(d),
            "prev5":x,
            "prev_ma20_premium":p.get("below_ma20"),
            "prev_above_ma20":p.get("below_ma20") is not None and p["below_ma20"]>0,
            "signal_day_close_confirmation":row["close"]>row["open"] and
               (prevclose is None or row["close"]>prevclose),
            "signal_day_close":row["close"],
            "signal_day_open":row["open"],
            "score":p["score"]
        }
        points.append({"entry_day":d,"ticker":t,"name":p["name"],"rank":p["rank"],
                       "metrics":metrics})
    return j,days,idx,by_day,by_t,breadth,points
def analyze(j,days,idx,by_day,breadth,signals):
    report={"system":"HENGCE","artifact":"Q017_RETIRED_REVISION_ABLATION_20261105",
            "asof":ASOF,"status":"COMPLETED_EXPLORATORY_SHADOW_ONLY",
            "costs":{"buy_rate":BUY_COST,"sell_rate":SELL_COST},
            "baseline":"All candidates from frozen 2026 EOD-open proxy, same GO days; all variants enter NEXT trading day OPEN.",
            "lag":"Signal-day CLOSE confirmation then NEXT day OPEN entry; no close-to-open price lookahead.",
            "entry_caveat":"Original 09:01 Q017 ranking NOT reproducible with later full-day OPEN. This compares shadow variants, not valid live Q017.",
            "hypothesis_not_independent_test":"R1 policy hypotheses motivated partly by observed 2026 October failures. 2026 is exploratory, NOT clean held-out OOS.",
            "new_policy":{"prior_electronics_MA20_breadth_min":MIN_MARKET_BREADTH,
                          "stock_prior_close_above_MA20":True,
                          "signal_day_close_higher_than_open_and_prior_close":True,
                          "buy":"NEXT_SESSION_OPEN","stop":"8% BELOW ENTRY ON CLOSE => FOLLOWING OPEN","time_exit":"D10_CLOSE"},
            "date_span":{"first":days[0],"last":days[-1]},
            "fixed_policy_keys":list(PRECOMMITTED_POLICIES),
            "summary":[],"matched_daily":[],"individual":[],
            "go_signal_count":len(signals),"go_days":len(set(x["entry_day"] for x in signals)),
            "post_selection_data_revisions_possible":True,
            "retired_strategy_unchanged":True,
            "formal_original_evidence":"See research/retired_q017_20261105/hengce/q017_radar/decision/20261021_0901.json"}
    dates=sorted(set(x["entry_day"] for x in signals))
    for name,(rule,stop) in PRECOMMITTED_POLICIES.items():
        trades=[]
        for p in signals:
            chosen=is_eligible(p,rule)
            row={"policy":name,"date":p["entry_day"],"ticker":p["ticker"],"rank":p["rank"],
                 "chosen":chosen,**p["metrics"]}
            for h in HORIZONS:
                out=calc_trade(p,by_day,days,idx,stop,h) if chosen else {"state":"SKIPPED"}
                row["h"+str(h)]=out
            trades.append(row)
            report["individual"].append(row)
        months=lambda a,b:[x for x in trades if a<=x["date"]<=b]
        partitions=[
            ("FULL_2026","2026-01-01","2026-11-04"),
            ("MARCH_JUNE","2026-03-01","2026-06-30"),
            ("JULY_NOV","2026-07-01","2026-11-04"),
            ("OCTOBER_ONLY","2026-10-01","2026-10-31"),
            ("SEPT_NOV","2026-09-01","2026-11-04")
        ]
        for pname,a,b in partitions:
            sub=months(a,b)
            row={"policy":name,"period":pname,"candidates":len(sub),
                 "kept":sum(x["chosen"] for x in sub),
                 "kept_pct":round(sum(x["chosen"] for x in sub)/len(sub),4) if sub else None,
                 "days_with_signal":len(set(x["date"] for x in sub if x["chosen"]))}
            for h in HORIZONS:
                res=[x["h"+str(h)]["return"] for x in sub if x["h"+str(h)]["state"]=="MATURED"]
                matured=sum(x["h"+str(h)]["state"]=="MATURED" for x in sub if x["chosen"])
                stop_trades=sum(x["h"+str(h)].get("reason")=="STOP_NEXT_OPEN" for x in sub)
                n_eligible_matured=sum(
                    calc_trade(p,by_day,days,idx,stop,h)["state"]=="MATURED"
                    for p in signals if a<=p["entry_day"]<=b
                )
                # For CASH/SKIPPED, zero allocation vs baseline of 3 equal slots,
                # but do not imply this is a viable overlapping portfolio.
                row["h"+str(h)]={"selected":ag(res),"stop_exit_count":stop_trades,
                    "mature_candidate_denominator":n_eligible_matured,
                    "slot_cash_adjusted_mean_pct":round(sum(res)*100/n_eligible_matured,3) if n_eligible_matured else None}
            report["summary"].append(row)
    # Non-lookahead pre-signal / post-close states for each recommendation day.
    for d in dates:
        s=[z for z in signals if z["entry_day"]==d]
        assert len(s)==3
        report["matched_daily"].append({
            "date":d,
            "breadth":breadth.get(d),
            "original_tickers":[p["ticker"] for p in s],
            "original_pre5_drop10":sum(p["metrics"]["prev5"]<=-.10 for p in s if p["metrics"]["prev5"] is not None),
            "original_below_ma20":sum(not p["metrics"]["prev_above_ma20"] for p in s),
            "signal_day_confirmed":sum(p["metrics"]["signal_day_close_confirmation"] for p in s),
            "R1_kept":sum(is_eligible(p,"R1") for p in s),
            "baseline_D10_net":[calc_trade(p,by_day,days,idx,None,10).get("return") for p in s],
            "R1_D10_net":[calc_trade(p,by_day,days,idx,.08,10).get("return") if is_eligible(p,"R1") else None for p in s],
        })
    return report

def main():
    j,days,idx,by_day,by_t,breadth,points=load()
    result=analyze(j,days,idx,by_day,breadth,points)
    OUT.mkdir(parents=True,exist_ok=True)
    dest=OUT/"Q017_REVISION_ABLATION_20261105.json"
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    sel={(r["policy"],r["period"]):r for r in result["summary"]}
    lines=["# 退役 Q017 修正版與原版比較（2026-11-05）","",
        "**只讀歷史研究：** 原 Q017 未重新啟用，沒有交易訊號或資本授權。","",
        "**嚴格限制：** 原選股名單使用全日 EOD OPEN 代理，並非當時 09:01 可見股票集合。這份數字不能稱為可執行回測；除權息、每日個股流動性、限價漲跌停、買入容量與多檔重疊尚未完整建模。","",
        "進場一律訊號次交易日開盤；退出到訊號第 10 個交易日收盤（或收盤跌破 -8% 後次日開盤）。成本假設買入 0.2425%、賣出 0.5425%，含佣金、賣出稅及每邊 0.1% 滑價。","",
        "## 相同候選池的消融實驗","",
        "| 版本 | GO 候選數 | 留下數 | D10 成熟數 | 成熟交易平均淨報酬 | 全候選檔位空手視為 0 | 10月成熟交易平均淨報酬 | 10月檔位空手均值 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    def f(x):return "—" if x is None else f"{x:+.2f}%"
    for p in PRECOMMITTED_POLICIES:
        allr=sel[p,"FULL_2026"];octo=sel[p,"OCTOBER_ONLY"];a=allr["h10"];o=octo["h10"]
        lines.append(f"| {p} | {allr['candidates']} | {allr['kept']} | {a['selected']['n']} | {f(a['selected']['mean'])} | {f(a['slot_cash_adjusted_mean_pct'])} | {f(o['selected']['mean'])} | {f(o['slot_cash_adjusted_mean_pct'])} |")
    lines+=["","## 固定基準與期間","",
        "### 上半年 vs 七月以後","",
        "| 版本 | 3–6 月 D10 均值 | 7–11 月 D10 均值 | 7–11 月檔位空手均值 |",
        "|---|---:|---:|---:|"]
    for p in PRECOMMITTED_POLICIES:
        a=sel[p,"MARCH_JUNE"]["h10"];b=sel[p,"JULY_NOV"]["h10"]
        lines.append(f"| {p} | {f(a['selected']['mean'])} | {f(b['selected']['mean'])} | {f(b['slot_cash_adjusted_mean_pct'])} |")
    lines+=["","## 控制條件","",
        "- R1 限定：前日電子股 20 日均線以上比率 >=40%；個股前日高於 MA20；訊號日收盤高於當日開盤及前一日收盤；隔日開盤進場；虧損收盤超過 8% 次交易日開盤退出。",
        "- 子策略全部在同一時期內比較，但因 10 月失敗案例已被看見，這些不是獨立樣本外檢驗。",
        "- 候選未成熟者從 D10 分母排除；空手分數標示為研究用固定等權檔位，非重疊持倉投資組合績效。",
        "- 規則差異應跨 GO 日期做統計分析，不能把同一天三檔視為三個獨立交易日。",
        "- 若 R1 比基準差，保留失敗結果，不調整參數去迎合歷史資料。",
        "",
        "完整交易與逐日診斷：Q017_REVISION_ABLATION_20261105.json。",
    ]
    destmd=OUT/"Q017_REVISION_ABLATION_REPORT_20261105.md"
    destmd.write_text("\n".join(lines)+"\n")
    print(json.dumps({"status":"PASS","full_days":len(days),
        "go_days":result["go_days"],"candidates":len(points),
        "baseline":sel["BASE_NEXT_OPEN_NO_STOP","FULL_2026"],
        "revised":sel["R1_BREADTH_TREND_CONFIRM_STOP8","FULL_2026"],
        "oct_baseline":sel["BASE_NEXT_OPEN_NO_STOP","OCTOBER_ONLY"],
        "oct_revised":sel["R1_BREADTH_TREND_CONFIRM_STOP8","OCTOBER_ONLY"]},ensure_ascii=False))

if __name__=="__main__":
    main()
