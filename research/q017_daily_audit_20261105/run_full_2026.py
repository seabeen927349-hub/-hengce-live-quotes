#!/usr/bin/env python3
"""Retired Q017 original-formula EOD-open shadow for all observable 2026 sessions.

Research only. Full-day opening prices (often not yet observable at 09:01) are
not actual historical Q017 signals; this is a deliberately non-executable
counterfactual for identifying historical failure modes. Features are strictly
pre-signal; outcomes use later data. Never used to activate Q017.
"""
import csv
import json
import math
import statistics
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
from run_audit import ROOT, OUT, ARCH, HIST, SOX, DXY, rows, number, ratio, rnd, sumavg, before_date_market

ASOF="2026-11-04"
START="2026-01-01"
HORIZONS=(1,2,5,10,20)
PRICE_PCT_SCALE=100.0

def aggr(xs):
    return {"n":len(xs),"mean":rnd(sumavg(xs)) if xs else None,
            "median":rnd(statistics.median(xs)) if xs else None,
            "positive":sum(x>0 for x in xs),
            "win_rate":rnd(sum(x>0 for x in xs)/len(xs)) if xs else None}

def prices_by_date():
    by_day=defaultdict(dict)
    by_t=defaultdict(list)
    for x in rows(HIST):
        d=str(x.get("date") or "")
        t=str(x.get("ticker") or "")
        c=number(x.get("close"))
        if not START<=d<=ASOF or not (len(t)==4 and t.isdigit() and c and c>0):
            continue
        op=number(x.get("open"))
        high=number(x.get("high"))
        low=number(x.get("low"))
        row={"date":d,"ticker":t,"name":x.get("name",""),
             "open":op if op and op>0 else None,
             "close":c,"high":high,"low":low,
             "volume":number(x.get("volume_shares"))}
        by_day[d][t]=row
    for d,a in by_day.items():
        for t,row in a.items():
            by_t[t].append(row)
    for t in by_t:
        by_t[t].sort(key=lambda x:x["date"])
    return by_day,by_t

def macro(d,sox,dxy):
    s=before_date_market(sox,d)
    x=before_date_market(dxy,d)
    if not s or not x:
        return None
    src="HISTORICAL_CSV_REBUILT_NOT_SAVED_LIVE"
    path=ARCH/"data/macro_cache"/(d.replace("-","")+".json")
    # This preserves the contemporaneous point-in-time macro cache whenever
    # it was generated before market open, avoiding hindsight data revisions.
    if path.exists():
        obj=json.loads(path.read_text())
        produced=str(obj.get("generated_at_taipei") or "")
        if (obj.get("status")=="PASS" and obj.get("trade_date")==d
                and produced[:10]==d and produced[11:19]<"09:01:00"
                and str((obj.get("sox_features") or {}).get("session") or "")<d):
            sf=obj["sox_features"]
            dx=obj["dxy_status"]
            s={"one":sf["sox_1d"],"five":sf["sox_5d"],
               "latest_session":sf["session"]}
            x={"five":dx["dxy_5d"],
               "latest_session":dx["latest_session"]}
            src="SAVED_PREOPEN_MACRO_CACHE"
    checks={"SOX_ONE_NEGATIVE":s["one"]<=0,
            "SOX_FIVE_BELOW_MINUS_3PCT":s["five"]<=-.03,
            "DXY_FIVE_ABOVE_MINUS_0_5PCT":x["five"]>=-.005}
    return {"source":src,"sox_date":s["latest_session"],"dxy_date":x["latest_session"],
            "sox_1d":s["one"],"sox_5d":s["five"],"dxy_5d":x["five"],
            "checks":checks,"go":all(checks.values())}

def main():
    by_day,by_t=prices_by_date()
    days=sorted(by_day)
    assert len(days)>120 and days[-1]==ASOF,(len(days),days[-1])
    sx=[{"date":z["date"],"close":number(z.get("close"))} for z in rows(SOX)]
    dx=[{"date":z["date"],"close":number(z.get("close"))} for z in rows(DXY)]
    sx=sorted([z for z in sx if z["close"] and z["close"]>0],key=lambda z:z["date"])
    dx=sorted([z for z in dx if z["close"] and z["close"]>0],key=lambda z:z["date"])
    soxdates=[z["date"] for z in sx]
    soxreturn={sx[i]["date"]:ratio(sx[i]["close"],sx[i-1]["close"])
               for i in range(1,len(sx))}
    observations={}
    observation_dates={}
    for ticker,rs in by_t.items():
        a=[]
        prev=None
        for row in rs:
            if prev:
                n=bisect_left(soxdates,row["date"])-1
                if n>=0 and soxreturn.get(soxdates[n]) is not None:
                    a.append((row["date"],soxreturn[soxdates[n]],
                              ratio(row["close"],prev["close"])))
            prev=row
        observations[ticker]=a
        observation_dates[ticker]=[z[0] for z in a]
    # prev-date histories are prepared before we ever examine today's OHLC.
    by_t_dates={t:[x["date"] for x in rs] for t,rs in by_t.items()}
    date_to_idx={d:i for i,d in enumerate(days)}
    prepared={}
    daily=[]
    signal=[]
    sector_baseline={}
    completed_sessions=0
    formal_dates=["2026-10-21","2026-10-22"]
    for i in range(1,len(days)):
        d=days[i];prior=days[i-1]
        gate=macro(d,sx,dx)
        if gate is None:
            continue
        eligible=[]
        prev_set=set(by_day[prior])
        for t in prev_set:
            hist=by_t[t]
            h=bisect_left(by_t_dates[t],d)
            if h<=0 or hist[h-1]["date"]!=prior:
                continue
            n=bisect_left(observation_dates[t],d)
            z=observations[t][max(0,n-60):n]
            if len(z)<30:
                continue
            avgx=sum(x for dd,x,y in z)/len(z)
            avgy=sum(y for dd,x,y in z)/len(z)
            var=sum((x-avgx)**2 for dd,x,y in z)
            beta=sum((x-avgx)*(y-avgy) for dd,x,y in z)/var if var else None
            if beta is None or not math.isfinite(beta) or beta<=0:
                continue
            p_today=by_day[d].get(t)
            if not p_today or p_today["open"] is None:
                continue
            pc=hist[h-1]["close"]
            gap=ratio(p_today["open"],pc)
            residual=gap-beta*gate["sox_1d"]
            if residual>.04:
                continue
            past=hist[:h]
            closes=[v["close"] for v in past]
            ma20=sumavg(closes[-20:]) if len(closes)>=20 else None
            v20=[v["volume"] for v in past[-20:]]
            avgvol=sumavg(v20) if len(v20)==20 and all(v is not None for v in v20) else None
            eligible.append({
                "ticker":t,"name":p_today["name"],
                "entry_day":d,"open":p_today["open"],
                "score":beta*(1+25*max(-residual,0)),
                "beta":beta,"residual":residual,
                "prev5":ratio(pc,closes[-6]) if len(closes)>=6 else None,
                "prev10":ratio(pc,closes[-11]) if len(closes)>=11 else None,
                "below_ma20":ratio(pc,ma20) if ma20 else None,
                "volume_ratio20":ratio(past[-1]["volume"],avgvol) if avgvol else None,
            })
        if not eligible:
            continue
        eligible.sort(key=lambda x:(-x["score"],x["ticker"]))
        top=eligible[:3]
        drec={"date":d,"macro_source":gate["source"],"go":gate["go"],
              "status":"GO" if gate["go"] else "NO_GO",
              "sox1":rnd(gate["sox_1d"]),"sox5":rnd(gate["sox_5d"]),
              "dxy5":rnd(gate["dxy_5d"]), "checked":gate["checks"],
              "eligible":len(eligible),"ranked":[z["ticker"] for z in top],
              "cohort_count":len(top) if gate["go"] else 0,
              "formal_0901_source_exists":d in formal_dates,
              "is_actual_0901":False,
              "note":"This is full-day open shadow, never the 09:01 ranking."}
        daily.append(drec)
        if not gate["go"]:
            continue
        completed_sessions+=1
        # Reuse sector comparison for same date and same horizon. Use exactly
        # the same population qualified by beta/open/residual, without future data.
        base_by_k=defaultdict(list)
        for v in eligible:
            t=v["ticker"];j=date_to_idx[d]
            for k in HORIZONS:
                if j+k-1>=len(days):
                    continue
                outcome=by_day[days[j+k-1]].get(t)
                if outcome:
                    base_by_k[k].append(ratio(outcome["close"],v["open"]))
        sector_baseline[d]={str(k):aggr(z) for k,z in base_by_k.items()}
        for rank,x in enumerate(top,1):
            t=x["ticker"];entry=x["open"]
            info={z:x[z] for z in ("ticker","name","entry_day","open","score","beta","residual","prev5","prev10","below_ma20","volume_ratio20")}
            info["rank"]=rank
            info["entry_model"]="SAME_DAY_FULL_EOD_OPEN_ONLY_NOT_TRADEABLE_Q017"
            info["asof_version"]=ASOF
            for k in HORIZONS:
                date_idx=date_to_idx[d]+k-1
                if date_idx>=len(days):
                    info["d"+str(k)]=None
                    continue
                close=by_day[days[date_idx]].get(t)
                info["d"+str(k)]=ratio(close["close"],entry) if close else None
                info["d"+str(k)+"_sector_baseline"]=sector_baseline[d].get(str(k),{}).get("mean")
            # A realistic *entry proxy* could use NEXT session OPEN, but it
            # cannot be considered a Q017 reference trade at 09:01.
            j=date_to_idx[d]
            next_session=days[j+1] if j+1<len(days) else None
            nxt=by_day[next_session].get(t) if next_session else None
            info["next_session"]=next_session
            info["next_open"]=nxt["open"] if nxt else None
            for k in (5,10):
                future_idx=j+k-1
                if nxt and info["next_open"] and future_idx<len(days):
                    row=by_day[days[future_idx]].get(t)
                    info[f"next_open_to_day{k}"]=ratio(row["close"],info["next_open"]) if row else None
                else:
                    info[f"next_open_to_day{k}"]=None
            signal.append(info)
    def subset(label,pred):
        a=[z for z in signal if pred(z)]
        out={"name":label,"signals":len(a),"distinct_dates":len(set(z["entry_day"] for z in a))}
        for k in HORIZONS:
            q=[z[f"d{k}"] for z in a if z.get(f"d{k}") is not None]
            out[f"d{k}"]=aggr(q)
            alpha=[z[f"d{k}"]-z[f"d{k}_sector_baseline"] for z in a if z.get(f"d{k}") is not None and z.get(f"d{k}_sector_baseline") is not None]
            out[f"d{k}_minus_same_day_eligible_mean"]=aggr(alpha)
        for k in (5,10):
            q=[z[f"next_open_to_day{k}"] for z in a if z.get(f"next_open_to_day{k}") is not None]
            out[f"next_open_to_d{k}"]=aggr(q)
        return out
    groups=[
        subset("ALL_GO",lambda z:True),
        subset("GO_AFTER_2026_07_01",lambda z:z["entry_day"]>="2026-07-01"),
        subset("GO_BEFORE_2026_07_01",lambda z:z["entry_day"]<"2026-07-01"),
        subset("PRE5_BELOW_MINUS_10",lambda z:z["prev5"] is not None and z["prev5"]<=-.10),
        subset("PRE5_ABOVE_MINUS_10",lambda z:z["prev5"] is not None and z["prev5"]>-.10),
        subset("PREVIOUS_CLOSE_BELOW_MA20",lambda z:z["below_ma20"] is not None and z["below_ma20"]<0),
        subset("PREVIOUS_CLOSE_ABOVE_MA20",lambda z:z["below_ma20"] is not None and z["below_ma20"]>=0),
        subset("LOW_VOLUME_BELOW_HALF20",lambda z:z["volume_ratio20"] is not None and z["volume_ratio20"]<-.5),
        subset("HIGH_VOLUME_AT_LEAST_HALF20",lambda z:z["volume_ratio20"] is not None and z["volume_ratio20"]>=-.5),
        subset("BETA_TOP1_ONLY",lambda z:z["rank"]==1)
    ]
    masks=[z for z in signal if z["entry_day"]=="2026-10-21"]
    formal=json.loads((ARCH/"decision/20261021_0901.json").read_text())
    compare={"actual_0901_top3":[x["ticker"] for x in formal["top3"]],
        "eod_open_reconstructed_top3":[x["ticker"] for x in masks],
        "same_rank": [x["ticker"] for x in formal["top3"]]==[x["ticker"] for x in masks],
        "comment":"Formal and EOD-open proxy differ because of 09:01 observability; never conflate."}
    output={
        "system":"HENGCE","artifact":"RETIRED_Q017_FULL_2026_EOD_OPEN_COUNTERFACTUAL",
        "status":"RESEARCH_ONLY_NO_AUTHORITY",
        "as_of":ASOF,"source":"retired Q017 archived TWSE electronics history, SOX, DXY; preserved pre-open cache used when available",
        "longitudinal_source_sessions":len(days),"first_archived_session":days[0],"last_archived_session":days[-1],
        "evaluated_days":len(daily),
        "macro_source_counts":{k:sum(x["macro_source"]==k for x in daily) for k in sorted(set(x["macro_source"] for x in daily))},
        "go_count":completed_sessions,
        "not_go_count":len(daily)-completed_sessions,
        "reconstructed_signals":len(signal),
        "saved_0901_snapshot_dates":formal_dates,
        "signal_semantics":"Counterfactual full-session open; includes stocks not opened by 09:01. No reconstruction of actual Q017 selection, true entry execution, or provider observability.",
        "production_q017_retired":True,"capital_authority":False,
        "registered_observation_comparison_20261021":compare,
        "macro_revisions":"For dates without saved valid pre-open macro caches, later archive SOX/DXY history is a reconstructed source, not guaranteed original point-in-time read.",
        "groups":groups,
        "daily":daily,
        "signals":signal,
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"full_2026_counterfactual_20261105.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=["# 衡策｜退役 Q017 全年逐日回推研究（截至 2026-11-04）","",
        f"回推資料涵蓋 {len(days)} 個交易日，實際可分析 {len(daily)} 日，符合宏觀 GO 的日期 {completed_sessions} 日，候選 {len(signal)} 檔次。",
        "",
        "**絕非正式 09:01 Q017 推薦績效：** 除保存的 10/21 與 10/22 原始決策外，全年開盤代理法會納入 09:01 尚未開盤的股票，亦無當時即時報價或可成交證據。本表是用原公式進行的研究重建，不是可執行回測。",
        "",
        "## 固定持有期與同期候選池比較","",
        "| 群組 | 檔次 | GO 日 | D1 均值 | D2 均值 | D5 均值 | D10 均值 | D10 相同日候選池差值 | D10 完整樣本 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    def fp(x):return "—" if x is None else f"{x*100:+.2f}%"
    for x in groups:
        md.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(x["name"],x["signals"],x["distinct_dates"],fp(x["d1"]["mean"]),fp(x["d2"]["mean"]),fp(x["d5"]["mean"]),fp(x["d10"]["mean"]),fp(x["d10_minus_same_day_eligible_mean"]["mean"]),x["d10"]["n"]))
    md.extend(["","## 每日市場閘門／Top3","",
        "| 日期 | GO | 宏觀證據 | Top3（即使 NO_GO 也顯示研究排名） |",
        "|---|---|---|---|"])
    for x in daily:
        md.append(f"| {x['date']} | {'GO' if x['go'] else 'NO_GO'} | {x['macro_source']} | {', '.join(x['ranked'])} |")
    md.extend(["","## 研究限制","",
        "- 多個候選重複選股／相同日期高度相關，檔次不是獨立觀察。應以日期分群估計不確定性。",
        "- 2026/11/04 尚未成熟的 D10、D20 不得當零；同日開盤與正式 09:01 報價不可互換。",
        "- 2026/11/05 中午盤中不是完整 EOD，故僅使用 11/04 以前完整收盤資料。",
        "- 事後依 10/21 失敗挑的閾值存在過度擬合風險；表格僅是事後分組，不宣稱修正後勝率。",
        "- 歷史價格未還原，除權息可能影響個別年初至年末報酬；與同期候選池僅為同口徑近似比較。",
        "- 保留 Q017 退役狀態；無正式策略、交易權限、下單或恢復排程。",
        "",
        "完整逐日候選、評分、來源、資料期間及各檔未成熟報酬在 full_2026_counterfactual_20261105.json。",
        ])
    (OUT/"FULL_2026_COUNTERFACTUAL_REPORT_20261105.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","days":len(days),"evaluated_days":len(daily),"go_days":completed_sessions,"signal_count":len(signal),"groups":groups,"compare":compare},ensure_ascii=False))

if __name__=="__main__":
    main()
