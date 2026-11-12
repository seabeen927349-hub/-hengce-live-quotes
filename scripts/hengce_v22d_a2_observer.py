#!/usr/bin/env python3
"""A2 display-only price/chip observer; never replaces V2.2D Top5 or authorizes trades."""
from __future__ import annotations
import csv
import gzip
import hashlib
import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

TDCC_SHA = "71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88"
OK_REPLAY = "PRIVATE_V22D_ORIGINAL_REPLAY_VERIFIED_RESEARCH_ONLY"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def number(value):
    try:
        v = float(value)
        return v if math.isfinite(v) and v > 0 else None
    except (TypeError, ValueError):
        return None


def repeat_lift(history):
    """A heuristic price pattern, NOT proof of washing or other intent."""
    h = history[-100:]
    prices = [r["close"] for r in h]
    impulses = []
    for i in range(3, len(prices)):
        if prices[i] / prices[i-3] >= 1.05 and (not impulses or i-impulses[-1] >= 5):
            impulses.append(i)
    pairs = []
    for a, b in zip(impulses, impulses[1:]):
        if (b-a <= 25 and b >= len(h)-25 and
                min(prices[a:b+1]) / prices[a] <= .97):
            pairs.append({"first": h[a]["date"], "second": h[b]["date"],
                          "gap_sessions": b-a})
    return {"candidate": bool(pairs), "pair_count": len(pairs),
            "last_pair": pairs[-1] if pairs else None,
            "price_rule": "THREE_DAY_5PCT_DIP_3PCT_SECOND_LIFT_25_SESSIONS",
            "manipulation_or_operator_inference": False}


def tdcc_asof(path, desired, decision):
    first = {}
    weekly = defaultdict(dict)
    cutoff = (decision-timedelta(days=14)).strftime("%Y%m%d")
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        rd = csv.DictReader(stream)
        required = {"Ticker","SnapshotDate","TierStatus","Big400Pct",
                    "HolderLe10Lots","RetailPeopleValid"}
        if not required.issubset(rd.fieldnames or ()):
            raise ValueError("A2_TDCC_FIELDS_NOT_VERIFIED")
        for r in rd:
            ticker, ds = r["Ticker"], r["SnapshotDate"]
            if not (len(ticker)==4 and ticker.isdigit() and len(ds)==8 and ds.isdigit()):
                continue
            if ds.startswith("2018") and r["TierStatus"]=="VALID":
                if ticker not in first or ds < first[ticker][0]:
                    first[ticker] = (ds, number(r["Big400Pct"]))
            if ticker in desired and ds<=cutoff:
                n=number(r["HolderLe10Lots"])
                if n is not None and r["RetailPeopleValid"].lower() in ("true","1"):
                    weekly[ticker][ds]=n
    cohort={t for t, (_, share) in first.items() if share is not None and share>=50}
    if len(cohort)!=781 or not desired.issubset(cohort):
        raise ValueError("A2_ORIGINAL_2018_781_COHORT_NOT_VERIFIED")
    return cohort, weekly


def price_history(path, cohort, decision):
    first_day=(decision-timedelta(days=170)).isoformat()
    day_counts=defaultdict(int)
    indexed=defaultdict(dict)
    max_day=None
    with Path(path).open("r",encoding="utf-8-sig",newline="") as stream:
        rd=csv.DictReader(stream)
        mandatory={"Date","Ticker","Name","Open","High","Low","Close","Volume"}
        if not mandatory.issubset(rd.fieldnames or ()):
            raise ValueError("A2_CANONICAL_FIELDS_NOT_VERIFIED")
        for r in rd:
            ds=r["Date"]
            if len(ds)!=10:
                continue
            max_day=max(max_day or ds,ds)
            if not first_day<=ds<=decision.isoformat():
                continue
            day_counts[ds]+=1
            ticker=r["Ticker"]
            if ticker not in cohort:
                continue
            if ticker in indexed[ds]:
                raise ValueError("A2_CANONICAL_DUPLICATE_KEY")
            c,h,l,v=(number(r[k]) for k in ("Close","High","Low","Volume"))
            if not all((c,h,l,v)) or not l<=c<=h:
                continue
            indexed[ds][ticker]={"date":ds,"close":c,"high":h,
                                 "low":l,"volume":v,"name":r["Name"]}
    if max_day!=decision.isoformat():
        raise ValueError("A2_CANONICAL_DATE_DOES_NOT_MATCH_REPLAY")
    days=sorted(x for x,count in day_counts.items() if count>=900)
    if len(days)<21 or days[-1]!=decision.isoformat():
        raise ValueError("A2_OFFICIAL_21_SESSION_COVERAGE_GAP")
    h=defaultdict(list)
    for ds in days:
        for t,row in indexed[ds].items():
            h[t].append(row)
    expected=days[-21:]
    rets=[(v[-1]["close"]/v[-21]["close"]-1)*100 for v in h.values()
          if len(v)>=21 and [x["date"] for x in v[-21:]]==expected]
    if len(rets)<600:
        raise ValueError("A2_781_BREADTH_EVIDENCE_INSUFFICIENT")
    return h,expected,statistics.median(rets),len(rets)


def observe_a2(replay, original_canonical=None, original_tdcc=None, now=None):
    now=now or datetime.now().astimezone()
    out={"model":"HENGCE_V22D_A2_SHADOW_RESEARCH_V1",
         "status":"A2_WAITING_FOR_VERIFIED_ORIGINAL_REPLAY",
         "research_only":True,"ranking_authority":False,
         "formal_selection_authority":False,"buy_signal":False,
         "sell_signal":False,"broker_execution":False,
         "authorized_lots":0,"capital_authority_twd":0,
         "original_top5_preserved":True,"top5_observations":[],
         "limitations":["NO_OUTSIDE_TOP5_RERANKING","NO_TDCC_FIRST_PUBLICATION_PIT_CERTIFICATION",
                        "PRICE_PATTERN_NOT_PROOF_OF_INTENT","NO_PREDICTED_RETURN_OR_ENTRY_PRICE"]}
    if replay.get("status")!=OK_REPLAY:
        out["blocker"]=replay.get("status")
        return out
    out["decision_date"]=replay["source_date"]
    out["original_top5"]=[x["ticker"] for x in replay["top5"]]
    out["qualified_count"]=replay["qualified_count"]
    out["not_current_recommendations"]=True
    if original_canonical is None or original_tdcc is None:
        out["status"]="A2_WAITING_FOR_PRIVATE_CANONICAL_AND_TDCC"
        return out
    try:
        decision=date.fromisoformat(out["decision_date"])
        if decision>now.date():
            raise ValueError("A2_FUTURE_DECISION_FORBIDDEN")
        expected_sha=replay.get("source_2026_canonical_sha256")
        if not isinstance(expected_sha,str) or len(expected_sha)!=64:
            raise ValueError("A2_CANONICAL_SOURCE_PIN_MISSING")
        if digest(original_canonical)!=expected_sha:
            raise ValueError("A2_CANONICAL_SHA_MISMATCH")
        if digest(original_tdcc)!=TDCC_SHA:
            raise ValueError("A2_TDCC_SHA_MISMATCH")
        cohort,weekly=tdcc_asof(original_tdcc,set(out["original_top5"]),decision)
        histories,sessions,market_median,market_coverage=price_history(
            original_canonical,cohort,decision)
        rows=[]
        for source in replay["top5"]:
            t=source["ticker"]
            hist=histories.get(t,[])
            row={"ticker":t,"original_rank":source["rank"],
                 "original_v22d_score":source["daily_decline_score"],
                 "tdcc_known_date":source["last_assumed_available_tdcc_date"],
                 "research_only":True,"buy_signal":False}
            if len(hist)<21 or [r["date"] for r in hist[-21:]]!=sessions:
                row.update(status="A2_MISSING_21_OFFICIAL_SESSIONS")
                rows.append(row)
                continue
            closes=[r["close"] for r in hist]
            gain20=closes[-1]/closes[-21]-1
            if (not math.isclose(closes[-1],source["last_verified_close"],abs_tol=.011)
                    or not math.isclose(gain20,source["return_20d"],abs_tol=.002)):
                row.update(status="A2_MODEL_CANONICAL_PRICE_DISAGREEMENT")
                rows.append(row)
                continue
            r20=[(v["high"]-v["low"])/v["close"] for v in hist[-20:]]
            r5=statistics.mean(r20[-5:])
            avg20=statistics.mean(r20)
            squeeze=r5/avg20 if avg20>0 else None
            v20=sum(v["volume"] for v in hist[-20:])/20
            v5=sum(v["volume"] for v in hist[-5:])/5
            last_known=source["last_assumed_available_tdcc_date"]
            snapshots=sorted((d,n) for d,n in weekly[t].items() if d<=last_known)
            change=None
            if len(snapshots)>=4 and snapshots[-1][0]==last_known:
                prior=snapshots[-4:]
                dates=[date(int(d[:4]),int(d[4:6]),int(d[6:])) for d,_ in prior]
                if all(5<=(b-a).days<=10 for a,b in zip(dates,dates[1:])):
                    change=(prior[-1][1]/prior[0][1]-1)*100
            notes=[]
            if change is None:
                notes.append("RETAIL_THREE_WEEK_ASOF_GAP")
            elif change>0:
                notes.append("KNOWN_SMALL_HOLDER_COUNT_INCREASED")
            if len(closes)>=6 and closes[-1]/closes[-6]-1>=.20:
                notes.append("FIVE_SESSION_GAIN_GE20_CHASE_RISK")
            row.update(status="A2_OBSERVED_PRICE_ONLY_RESEARCH",
                       name=hist[-1]["name"],last_close=closes[-1],
                       known_retail_three_week_change_pct=round(change,3) if change is not None else None,
                       known_retail_decline_confirmed=change is not None and change<=-1,
                       return20_pct=round(gain20*100,3),
                       relative_strength20_vs_781_median_pp=round(gain20*100-market_median,3),
                       squeeze5_20=round(squeeze,4) if squeeze is not None else None,
                       range_contraction_candidate=squeeze is not None and squeeze<=.85,
                       volume_ratio5_20=round(v5/v20,3) if v20 else None,
                       pullback_from_20d_peak_pct=round((closes[-1]/max(closes[-20:])-1)*100,3),
                       repeat_lift=repeat_lift(hist),risk_notes=notes)
            rows.append(row)
        out.update(status="A2_RESEARCH_OBSERVATIONS_READY",top5_observations=rows,
                   source_canonical_sha256=expected_sha,
                   source_tdcc_sha256=TDCC_SHA,
                   price_session_date=sessions[-1],
                   cohort_market20_median_pct=round(market_median,3),
                   cohort_price20_coverage=market_coverage,
                   is_current_session=decision==now.date(),
                   only_uses_data_at_or_before_decision=True)
    except (OSError,UnicodeError,ValueError,TypeError,OverflowError) as exc:
        out["status"]="A2_SOURCE_BLOCKED"
        out["blocker"]=str(exc)
        out["top5_observations"]=[]
    return out
