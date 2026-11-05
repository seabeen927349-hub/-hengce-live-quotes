#!/usr/bin/env python3
"""Read-only retired Q017 daily counterfactual through 2026-11-04.

Historical reconstruction never executes/activates Q017. 09:01 rankings are
treated as formal *only* where original immutable snapshots are preserved.
Later EOD-open rankings are diagnostic alternatives, NOT actual recommendations.
No future prices are used in feature or gate calculation.
"""
from __future__ import annotations
import csv
import json
import math
import statistics
from collections import defaultdict
from bisect import bisect_left
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ARCH = ROOT / "research/retired_q017_20261105/hengce/q017_radar"
HIST = ARCH / "data/twse_electronics_history_2026.csv"
SOX = ARCH / "data/sox_2026.csv"
DXY = ARCH / "data/dxy_2026.csv"
FORMAL = ARCH / "decision"
LAST_DAY = "2026-11-04"
FIRST_DAY = "2026-10-21"

def rows(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def number(x):
    try:
        y = float(str(x).replace(",", "").strip())
        return y if math.isfinite(y) else None
    except (TypeError, ValueError):
        return None

def ratio(a,b):
    return None if a is None or b in (None,0) else a/b-1

def rnd(x,n=6):
    return None if x is None else round(x,n)

def sumavg(a):
    return sum(a)/len(a) if a else None

def before_date_market(series, ds):
    datelist = [x["date"] for x in series]
    n = bisect_left(datelist,ds)
    prior = series[:n]
    if len(prior)<6:
        return None
    return dict(latest_session=prior[-1]["date"],
                one=ratio(prior[-1]["close"],prior[-2]["close"]),
                five=ratio(prior[-1]["close"],prior[-6]["close"]))

def valid_eod():
    days={}
    for p in sorted((ROOT/"eod").iterdir()):
        if not p.is_dir() or len(p.name)!=8 or not p.name.isdigit():
            continue
        d=f"{p.name[:4]}-{p.name[4:6]}-{p.name[6:]}"
        if not FIRST_DAY<=d<=LAST_DAY:
            continue
        sp=p/"status.json"
        if not sp.exists():
            continue
        s=json.loads(sp.read_text())
        if s.get("target_date")!=d or s.get("price_status")!="COMPLETE":
            continue
        pr={}
        for f in sorted(p.glob("price_*.csv")):
            for a in rows(f):
                if a.get("Date")!=d:
                    continue
                t=str(a.get("Ticker","")).strip()
                op=number(a.get("Open"));cl=number(a.get("Close"))
                if len(t)==4 and t.isdigit() and op and cl:
                    pr[t]={
                        "open":op,"close":cl,"high":number(a.get("High")),
                        "low":number(a.get("Low")),
                        "volume_shares":number(a.get("VolumeShares")),
                        "source":str(f.relative_to(ROOT)),
                    }
        if pr:
            days[d]=dict(prices=pr,three_leg_complete=s.get("three_leg_complete"),
                         mother_status=s.get("mother_status"),status_path=str(sp.relative_to(ROOT)))
    return days

def main():
    assert HIST.exists() and SOX.exists() and DXY.exists(), "ARCHIVED_Q017_SOURCE_NOT_FOUND"
    eod=valid_eod()
    days=sorted(eod)
    assert days and days[0]==FIRST_DAY and days[-1]==LAST_DAY, ("EOD_DATES_MISSING",days)
    sox=[{"date":a["date"],"close":number(a.get("close"))} for a in rows(SOX)]
    dxy=[{"date":a["date"],"close":number(a.get("close"))} for a in rows(DXY)]
    sox=[a for a in sox if a["close"] and a["close"]>0]
    dxy=[a for a in dxy if a["close"] and a["close"]>0]
    sox.sort(key=lambda z:z["date"]); dxy.sort(key=lambda z:z["date"])
    sd=[x["date"] for x in sox]
    sret={sox[i]["date"]: ratio(sox[i]["close"],sox[i-1]["close"]) for i in range(1,len(sox))}
    # One stock-date row, preferred source for past corporate price history.
    unique={}
    for a in rows(HIST):
        d=str(a.get("date") or "").strip()
        t=str(a.get("ticker") or "").strip()
        c=number(a.get("close"))
        if d<=LAST_DAY and c and c>0 and t.isdigit() and len(t)==4:
            unique[(d,t)] = {
                "date":d,"ticker":t,"name":str(a.get("name") or ""),
                "open":number(a.get("open")),"high":number(a.get("high")),
                "low":number(a.get("low")),"close":c,
                "volume_shares":number(a.get("volume_shares")),
            }
    hist_latest=max(d for d,t in unique)
    mismatches=[]
    for d,day in eod.items():
        for t,pr in day["prices"].items():
            key=(d,t)
            old=unique.get(key)
            if old and abs(old["close"]-pr["close"])>0.00001:
                mismatches.append({"date":d,"ticker":t,"archived_close":old["close"],"eod_close":pr["close"]})
            if old:
                # Prefer final, audited EOD data on overlapping dates.
                old.update({k:pr[k] for k in ("open","high","low","close","volume_shares")})
            else:
                # Add only securities belonging to archive's electronics series universe.
                # For the missing-electronics-history case, do NOT add outsiders.
                pass
    by_t=defaultdict(list)
    for a in unique.values():
        by_t[a["ticker"]].append(a)
    for rs in by_t.values():
        rs.sort(key=lambda z:z["date"])

    reports=[]
    picks=[]
    formal_days=[]
    macrodiff=[]
    for d in days:
        sx=before_date_market(sox,d); dx=before_date_market(dxy,d)
        assert sx and dx, ("INSUFFICIENT_MACRO",d)
        checks={"sox_1d_lte_0":sx["one"]<=0,
                "sox_5d_lte_minus_3pct":sx["five"]<=-.03,
                "dxy_5d_gte_minus_0_5pct":dx["five"]>=-.005}
        go=all(checks.values())
        # Only historical observations with date < target date enter beta and
        # rolling pre-signal momentum calculations.
        prior_date=max(x["date"] for x in unique.values() if x["date"]<d)
        universe=set(t for day,t in unique if day==prior_date)
        betas={}; previous={}; metrics={}; last40={}
        for t in universe:
            hist=[a for a in by_t[t] if a["date"]<d]
            if not hist or hist[-1]["date"]!=prior_date:
                continue
            last=hist[-1]
            c=[a["close"] for a in hist]
            pc=last["close"]
            obs=[]
            for i in range(1,len(hist)):
                si=bisect_left(sd,hist[i]["date"])-1
                if si>=1 and sret.get(sd[si]) is not None:
                    obs.append((sret[sd[si]],ratio(hist[i]["close"],hist[i-1]["close"])))
            if len(obs)<30:
                continue
            z=obs[-60:];xm=sum(a for a,b in z)/len(z);ym=sum(b for a,b in z)/len(z)
            var=sum((a-xm)**2 for a,b in z)
            beta=sum((a-xm)*(b-ym) for a,b in z)/var if var else 0
            if not beta>0 or not math.isfinite(beta):
                continue
            betas[t]=beta;previous[t]=pc
            avg20=sumavg(c[-20:]) if len(c)>=20 else None
            vs=[v["volume_shares"] for v in hist[-20:] if v["volume_shares"] is not None]
            metrics[t]={
                "prior_close":pc,
                "prior_5_return":ratio(c[-1],c[-6]) if len(c)>=6 else None,
                "prior_10_return":ratio(c[-1],c[-11]) if len(c)>=11 else None,
                "prior_20_return":ratio(c[-1],c[-21]) if len(c)>=21 else None,
                "prior_close_over_ma20":ratio(pc,avg20),
                "prior_vol_ratio20":ratio(last["volume_shares"],sumavg(vs)) if len(vs)==20 else None,
                "beta_obs_count":len(obs),
            }
        proxy=[]
        for t in sorted(betas):
            pr=eod[d]["prices"].get(t)
            if not pr or not pr["open"]:
                continue
            op=pr["open"];pc=previous[t]
            gap=ratio(op,pc)
            expected=betas[t]*sx["one"]
            residual=gap-expected
            if residual>.04:
                continue
            score=betas[t]*(1+25*max(-residual,0))
            proxy.append({"ticker":t,"open":op,"previous_close":pc,
                          "beta":betas[t],"gap":gap,"expected_gap":expected,
                          "residual":residual,"score":score,"qualified":go})
        proxy.sort(key=lambda x:(-x["score"],x["ticker"]))
        formal_path=FORMAL/(d.replace("-","")+"_0901.json")
        actual=None
        if formal_path.exists():
            actual=json.loads(formal_path.read_text(encoding="utf-8"))
            assert actual["trade_date"]==d
            m=actual.get("market_gate",{})
            macro_diffs={k:rnd(abs(m.get(k,0)-v),8) for k,v in
                         [("sox_1d",sx["one"]),("sox_5d",sx["five"]),("dxy_5d",dx["five"])]}
            if any(diff is not None and diff>0.00015 for diff in macro_diffs.values()):
                macrodiff.append({"date":d,"computed":sx,"recorded":m,"differences":macro_diffs})
            go=(m.get("gate_go") is True)
            formal_days.append(d)
            active=[dict(x) for x in actual.get("top3",[]) if x.get("qualified") is True and go]
            source="FORMAL_SAVED_0901"
            visible=list(actual.get("top3",[]))
        else:
            active=proxy[:3] if go else []
            source="RETROSPECTIVE_EOD_OPEN_PROXY_NOT_REAL_0901"
            visible=proxy[:3]
        dayreport={
            "date":d,"mode":source,
            "market_gate":"GO" if go else ("WATCH" if sum(checks.values()) else "CASH"),
            "go":go,"macro_asof":{"sox_session":sx["latest_session"],"sox1":sx["one"],
                "sox5":sx["five"],"dxy_session":dx["latest_session"],"dxy5":dx["five"],
                "checks":checks},
            "prior_tw_date":prior_date,"universe_n":len(universe),
            "eligible_beta_n":len(betas),
            "eod_open_proxy_n":len(proxy),
            "original_0901_opened_n":actual.get("data_status",{}).get("opened_by_decision_count") if actual else None,
            "original_gate":actual.get("market_state") if actual else None,
            "visible_top3":[{"ticker":x["ticker"],"score":rnd(x["score"]),"qualified":x.get("qualified",False)} for x in visible],
            "proxy_top3":[{"ticker":x["ticker"],"score":rnd(x["score"])} for x in proxy[:3]],
            "active_n":len(active),
            "price_status":"COMPLETE",
            "eod_three_leg_complete":eod[d]["three_leg_complete"],
            "eod_mother_status":eod[d]["mother_status"],
        }
        reports.append(dayreport)
        for rank,x in enumerate(active,1):
            t=x["ticker"];entry=x["open"];a=metrics.get(t,{})
            actual_days=[(dt,eod[dt]["prices"].get(t)) for dt in days if dt>=d]
            outcome=[]
            for d2,q in actual_days:
                if not q:
                    outcome.append({"date":d2,"status":"NO_EOD_PRICE"})
                else:
                    outcome.append({"date":d2,"close":q["close"],"open":q["open"],
                        "high":q["high"],"low":q["low"],
                        "close_return_vs_0901_reference":ratio(q["close"],entry)})
            valid=[v for v in outcome if "close" in v]
            nextopen=actual_days[1][1]["open"] if len(actual_days)>1 and actual_days[1][1] else None
            first_below5=next((i for i,o in enumerate(valid) if o["close_return_vs_0901_reference"]<=-.05),None)
            nextopen_stop=None
            if first_below5 is not None and first_below5+1<len(valid):
                v=valid[first_below5+1]
                nextopen_stop={"exit_date":v["date"],"exit_price":v["open"],
                    "return_vs_0901_reference":ratio(v["open"],entry)}
            picks.append({
                "signal_date":d,"ticker":t,"rank":rank,"mode":source,
                "market_go":go,"reference_entry_open":entry,"beta":x["beta"],
                "residual":x["residual"],"score":x["score"],
                "pre_signal":a,
                "available_sessions":len(outcome),
                "d1_return":valid[0]["close_return_vs_0901_reference"] if valid else None,
                "d2_return":valid[1]["close_return_vs_0901_reference"] if len(valid)>=2 else None,
                "d5_return":valid[4]["close_return_vs_0901_reference"] if len(valid)>=5 else None,
                "d10_return":valid[9]["close_return_vs_0901_reference"] if len(valid)>=10 else None,
                "end_date":valid[-1]["date"] if valid else None,
                "end_close_return":valid[-1]["close_return_vs_0901_reference"] if valid else None,
                "worst_intraday_low_return":min((ratio(v["low"],entry) for v in valid if v["low"]),default=None),
                "stop5_next_open_retro":nextopen_stop,
                "next_session_open":nextopen,
                "outcomes":outcome
            })
    original=[p for p in picks if p["mode"]=="FORMAL_SAVED_0901"]
    shadow=[p for p in picks if p["mode"].startswith("RETROSPECTIVE")]
    def aggreg(a):
        out={"count":len(a)}
        for k in ("d1_return","d2_return","d5_return","d10_return","end_close_return"):
            z=[x[k] for x in a if x[k] is not None]
            out[k]={"n":len(z),"mean":sumavg(z),"positive":sum(v>0 for v in z)}
        for k in ("prior_5_return","prior_close_over_ma20","prior_vol_ratio20"):
            vals=[x["pre_signal"].get(k) for x in a if x["pre_signal"].get(k) is not None]
            out[k]={"n":len(vals),"mean":sumavg(vals),"negative":sum(v<0 for v in vals)}
        out["pre_5_below_minus_10pct"]=sum(x["pre_signal"].get("prior_5_return") is not None and x["pre_signal"]["prior_5_return"]<=-.1 for x in a)
        out["pre_close_below_ma20"]=sum(x["pre_signal"].get("prior_close_over_ma20") is not None and x["pre_signal"]["prior_close_over_ma20"]<0 for x in a)
        out["pre_volume_under_half_ma20"]=sum(x["pre_signal"].get("prior_vol_ratio20") is not None and x["pre_signal"]["prior_vol_ratio20"]<-.5 for x in a)
        return out
    out={
        "system":"HENGCE","study":"Q017_RETIRED_DAILY_POINT_IN_TIME_DIAGNOSTIC",
        "generated_using":"read-only GitHub Actions historical analysis, no model activation",
        "as_of_complete_eod":LAST_DAY,
        "intraday_2026_11_05_excluded":"Session incomplete at user request (12:07 Taipei)",
        "source_root":str(HIST.relative_to(ROOT)),
        "universe_history_latest":hist_latest,
        "source_history_rows":len(unique),
        "eod_sessions":days,
        "formal_snapshot_dates":formal_days,
        "macro_reconstruction_discrepancy":macrodiff,
        "archive_vs_eod_price_discrepancies_total":len(mismatches),
        "archive_vs_eod_price_discrepancy_examples":mismatches[:10],
        "critical_limitation":"Retrospective daily EOD open price reveals stocks not opened by 09:01. On dates without saved 09:01 snapshot, this is NOT actual Q017 selection; no causal 09:01 rank or executable open return can be established.",
        "historical_model_status":"RETIRED_NO_TRADING_OR_SELECTION_AUTHORITY",
        "daily":reports,
        "picks":picks,
        "summary":{
            "sessions":len(days),
            "go_days":[r["date"] for r in reports if r["go"]],
            "non_go_days":[r["date"] for r in reports if not r["go"]],
            "formal":aggreg(original),
            "proxy":aggreg(shadow),
            "all":aggreg(picks),
        },
        "unchanged":True
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"daily_diagnostic_20261105.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    md=[
        "# HENGCE retired Q017: daily audit through 2026-11-04",
        "",
        "As of: 2026-11-04 completed EOD; 2026-11-05 intraday is excluded.",
        "This is **diagnostic research** only. Historical Q017 remains retired; 09:01 quotes are unavailable except preserved formal snapshots on 10/21 and 10/22.",
        "",
        "## Daily gate and ranked candidates",
        "",
        "| Date | Gate | Source of Top3 | Displayed Top3 | Qualified picks |",
        "|---|---|---|---|---:|",
    ]
    for z in reports:
        md.append("| {} | {} | {} | {} | {} |".format(
            z["date"],z["market_gate"],"ACTUAL_0901" if z["mode"].startswith("FORMAL") else "EOD_OPEN_PROXY",
            ", ".join(a["ticker"] for a in z["visible_top3"]) or "—",z["active_n"]))
    md.extend(["","## All eligible picks (GO days only)","","| Date | Mode | Ticker | Rank | Pre 5D | Pre vs MA20 | D1 | D2 | D5 | To 11/04 (different holding lengths) |",
               "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"])
    def fmt(x):return "—" if x is None else f"{x*100:+.2f}%"
    for p in picks:
        md.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            p["signal_date"],"REAL" if p["mode"].startswith("FORMAL") else "PROXY",p["ticker"],p["rank"],
            fmt(p["pre_signal"].get("prior_5_return")),fmt(p["pre_signal"].get("prior_close_over_ma20")),
            fmt(p["d1_return"]),fmt(p["d2_return"]),fmt(p["d5_return"]),fmt(p["end_close_return"])))
    md.extend(["","## Diagnostics",
        "",
        f"Total EOD sessions: {len(days)}; GO: {len(out['summary']['go_days'])}; no GO: {len(out['summary']['non_go_days'])}.",
        f"Formal 09:01 days: {', '.join(formal_days)}.",
        f"Formal picks: {len(original)}; EOD-open proxy picks: {len(shadow)}.",
        f"Pre-5D <= -10%: formal {out['summary']['formal']['pre_5_below_minus_10pct']}/{len(original)}, proxy {out['summary']['proxy']['pre_5_below_minus_10pct']}/{len(shadow)}.",
        f"Prior close < MA20: formal {out['summary']['formal']['pre_close_below_ma20']}/{len(original)}, proxy {out['summary']['proxy']['pre_close_below_ma20']}/{len(shadow)}.",
        "",
        "## Guardrails",
        "",
        "- A formal Top3 displayed under CASH/WATCH is **not** a buy recommendation.",
        "- EOD-open proxy selection can include stocks not opened by 09:01. It **cannot** establish true Q017 ranking or a fill at that day's open.",
        "- Feature windows use prior completed sessions only. The future outcomes are diagnostic and never enter selection.",
        "- D10 has no mature cohort if fewer than 10 observed sessions; an unavailable or censored outcome is not zero return.",
        "- No surviving original 09:01 snapshots after 10/22; do not fabricate them.",
        "- Existing retired code remains archived; no strategy or order authority is activated.",
        "- Macro features from archived SOX/DXY CSV can reflect later data revisions; preserved original decision market gate is authoritative on 10/21-10/22.",
        "",
        "Source files: research/retired_q017_20261105/hengce/q017_radar/{decision,data}; eod/YYYYMMDD/price_*.csv.",
        "Machine-readable details: daily_diagnostic_20261105.json.",
        "",
    ])
    (OUT/"REPORT_20261105.md").write_text("\n".join(md),encoding="utf-8")
    print(json.dumps({"status":"PASS","eod_days":days,"go_days":out["summary"]["go_days"],
        "daily":[{"date":z["date"],"gate":z["market_gate"],"source":z["mode"],"top3":[x["ticker"] for x in z["visible_top3"]],"qualified":z["active_n"]} for z in reports],
        "summary":out["summary"],"formal_picks":[{"ticker":z["ticker"],"d2":z["d2_return"],"end":z["end_close_return"],"pre5":z["pre_signal"].get("prior_5_return")} for z in original],
        "mismatches":len(mismatches),"macro_diffs":macrodiff},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
