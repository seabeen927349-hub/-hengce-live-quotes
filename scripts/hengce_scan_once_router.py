#!/usr/bin/env python3
"""HENGCE scan once: no active strategy and no order authority."""
import argparse,json,hashlib
from datetime import datetime,date
from pathlib import Path
from zoneinfo import ZoneInfo
try:
    from scripts.hengce_scan_consistency import consistency_snapshot
except ModuleNotFoundError:  # python scripts/hengce_scan_once_router.py
    from hengce_scan_consistency import consistency_snapshot
try:
    from scripts.hengce_v22_max5_atr_price_plan import build_price_plan
except ModuleNotFoundError:  # python scripts/hengce_scan_once_router.py
    from hengce_v22_max5_atr_price_plan import build_price_plan
TZ=ZoneInfo("Asia/Taipei")
ADVISORY_PATH="research/hba_surveillance/decision_latest.json"
def advisory(now, root=None):
    """Read ONLY the existing read-only HBA advisory; formal selector remains retired."""
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    info={"authority":"RESEARCH_ONLY_NO_BUY_SELL_OR_ORDER",
          "status":"NOT_AVAILABLE","path":ADVISORY_PATH,
          "observed_eod_date":None,"examples":[]}
    try:
        contract=json.loads((root/"hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json").read_text(encoding="utf-8"))
        if (contract.get("status")!="NO_ACTIVE_SELECTION_STRATEGY"
                or contract.get("active_strategy_count")!=0
                or contract.get("broker_order_execution") is not False):
            info["status"]="RETIREMENT_CONTRACT_UNVERIFIED"
            return info
        x=json.loads((root/ADVISORY_PATH).read_text(encoding="utf-8"))
        a=x.get("authority") or {}
        d=x.get("observed_eod_date")
        target=x.get("target_tw_date")
        if (x.get("schema")!="HENGCE_HBA_RESEARCH_DECISION_V1_20261110"
                or x.get("status")!="RESEARCH_ADVISORY_READY"
                or a.get("active_selection_strategy_count")!=0
                or a.get("formal_selection") is not False
                or a.get("trading") is not False
                or a.get("broker_execution") is not False
                or a.get("capital_twd")!=0
                or x.get("not_live_quotes") is not True
                or x.get("historical_alpha_validated") is not False
                or not isinstance(d,str) or not isinstance(target,str)
                or d>target):
            info["status"]="UNVERIFIED_RESEARCH_RECEIPT"
            return info
        age=(now.date()-date.fromisoformat(d)).days
        target_age=(now.date()-date.fromisoformat(target)).days
        if age<0 or age>5 or target_age<0 or target_age>5:
            info["status"]="STALE_OR_FUTURE_EOD"
            return info
        # The research document must match BOTH published evidence files.
        # A newer HBA or integrated receipt invalidates an old decision card.
        for short_name, source_path in (
                ("original_hba","research/hba_surveillance/latest.json"),
                ("integrated_hba","research/hba_surveillance/integrated_latest.json")):
            raw=(root/source_path).read_bytes()
            expected=(x.get("input_sha256") or {}).get(short_name)
            if expected!=hashlib.sha256(raw).hexdigest():
                info["status"]="RESEARCH_EVIDENCE_HASH_MISMATCH"
                return info
        items=x.get("human_review_examples") or []
        if not isinstance(items,list) or len(items)>12:
            info["status"]="INVALID_DISPLAY"
            return info
        info.update(status="RESEARCH_ADVISORY_READY",
                    observed_eod_date=d,
                    advisory_target_tw_date=target,
                    market_covered=(x.get("research_summary") or {}).get("market_covered"),
                    research_only=True,
                    examples=[{"ticker":k.get("ticker"),"name":k.get("name"),
                               "review_group":k.get("review_group"),"why":k.get("why"),
                               "risks":k.get("risks"),
                               "change_of_view":k.get("change_of_view")}
                              for k in items if isinstance(k,dict)])
    except (OSError,ValueError,TypeError):
        info["status"]="UNREADABLE_RESEARCH_RECEIPT"
    return info

def selected_model_preference(root=None):
    """User-selected research version; legacy V2.2 remains separately verifiable."""
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    path=root/"hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json"
    result={"status":"PREFERENCE_UNAVAILABLE","model_id":None,
            "formal_selection_authority":False,"signal_authority":False,
            "capital_authority_twd":0,"broker_execution":False}
    try:
        x=json.loads(path.read_text(encoding="utf-8"))
        safety=(x.get("schema")=="HENGCE_SELECTION_MODEL_CHOICE_V1"
                and x.get("formal_selection_authority") is False
                and x.get("buy_sell_signal_authority") is False
                and type(x.get("capital_authority_twd")) is int
                and x.get("capital_authority_twd")==0
                and x.get("broker_execution") is False
                and type(x.get("authorized_lots")) is int
                and x.get("authorized_lots")==0)
        if not safety:
            result["status"]="PREFERENCE_INVALID_FAIL_CLOSED"
            return result
        if (x.get("model_package")=="HENGCE_SELECTION_MODEL_V2_2_D_DAILY_TOP5"
                and x.get("choice_status")=="PREFERRED_DAILY_RESEARCH_PENDING_PROSPECTIVE"):
            try:
                from scripts.hengce_v22d_daily_reader import selected_v22d
            except ModuleNotFoundError:
                from hengce_v22d_daily_reader import selected_v22d
            if not selected_v22d(root):
                result["status"]="PREFERENCE_INVALID_FAIL_CLOSED"
                return result
            result.update(status="PREFERRED_DAILY_RESEARCH_MODEL_NOT_LIVE",
                          model_id=x["model_id"],model_name=x["model_name"],
                          package_version=x["model_package"],
                          promotion_blockers=x.get("why_blocked"),
                          ranking="V22D_SCORE_ELIGIBILITY_TURNOVER_TOP5",
                          legacy_v22_role="BENCHMARK_ONLY_NOT_PRIMARY",
                          data_latest=x.get("reference_data_through"))
        elif (x.get("model_package")=="HENGCE_SELECTION_MODEL_V2_2_TOP5"
              and x.get("choice_status")=="PREFERRED_PENDING_PROMOTION"):
            result.update(status="PREFERRED_RESEARCH_MODEL_NOT_LIVE",
                          model_id=x.get("model_id"),
                          model_name=x.get("model_name"),
                          package_version=x.get("model_package"),
                          source_pull_request=x.get("source_pull_request"),
                          promotion_blockers=x.get("why_blocked"),
                          ranking="TOP5_MEDIAN_TURNOVER",
                          data_latest=x.get("reference_data_through"))
        else:
            result["status"]="PREFERENCE_INVALID_FAIL_CLOSED"
    except (OSError,ValueError,TypeError,KeyError):
        pass
    return result


V22_RESEARCH_PATH="research/retail_top5/v22_research_latest.json"


WEEKLY_V22_PATH="research/retail_top5/v22_weekly_latest.json"

def weekly_v22_research_observation(now=None, root=None):
    """Read ONLY a committed weekly V2.2 result from existing HENGCE vessels.

    This is an informational research ranking and never a formal trading strategy.
    If no weekly file exists, the historical immutable 2026-11-06 report remains
    available under the old receipt path. An invalid weekly receipt is NOT
    silently replaced with older data.
    """
    import math
    now=now or datetime.now(TZ)
    now=(now if now.tzinfo else now.replace(tzinfo=TZ)).astimezone(TZ)
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    path=root/WEEKLY_V22_PATH
    if not path.exists():
        return None
    result={
        "status":"WEEKLY_RESEARCH_RECEIPT_UNVERIFIED",
        "research_only":True,"source_path":WEEKLY_V22_PATH,
        "top5":[],"qualified_count":0,"source_date":None,
        "current_selection":False,"formal_selection_authority":False,
        "ranking_authority":False,"buy_signal":False,"sell_signal":False,
        "authorized_lots":0,"capital_authority_twd":0,"broker_execution":False,
        "not_live_quotes":True,
    }
    if selected_model_preference(root).get("status") not in ("PREFERRED_RESEARCH_MODEL_NOT_LIVE","PREFERRED_DAILY_RESEARCH_MODEL_NOT_LIVE"):
        result["status"]="V22_PREFERENCE_UNVERIFIED"
        return result
    try:
        d=json.loads(path.read_text(encoding="utf-8"))
        decision=date.fromisoformat(d["decision_date"])
        if (d.get("schema")!="HENGCE_V22_WEEKLY_RESEARCH_SCREEN_V1"
            or d.get("mode")!="RESEARCH_TOP5_ONLY_NO_ORDER"
            or d.get("system")!="HENGCE"
            or d.get("original_screen_commit")!="4a0f98fd2bd2a65deb2ebaf61e15e77c6a7893d6"
            or d.get("research_only") is not True
            or d.get("fully_prospective_performance_verified") is not False
            or d.get("selection_authority") is not False
            or d.get("formal_strategy_promoted") is not False
            or d.get("buy_signal") is not False or d.get("sell_signal") is not False
            or d.get("broker_execution") is not False
            or d.get("authorized_lots")!=0 or d.get("capital_authority_twd")!=0
            or not isinstance(d.get("historical_asof_proof_missing"),bool)
            or decision.weekday()!=4 or decision<date(2026,11,6)
            or decision>now.date()):
            return result
        lineage=d.get("source_lineage")
        if not isinstance(lineage,dict):
            return result
        snaps=lineage.get("tdcc_snapshots")
        days=lineage.get("price_days")
        if (lineage.get("decision")!=d["decision_date"]
            or lineage.get("source_mode")!="HENGCE_ORIGINAL_EOD_PLUS_EXISTING_RESEARCH_MOTHER_AND_TDCC"
            or lineage.get("eod_research_mother_sha256")!="b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93"
            or lineage.get("tdcc_g1_457_week_mother_sha256")!="71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88"
            or not isinstance(days,list) or len(days)!=21
            or not isinstance(snaps,list) or len(snaps)!=3
            or len({x.get("date") for x in days if isinstance(x,dict)})!=21
            or days[-1].get("date")!=d["decision_date"]
            or any(z.get("source") not in
                   ("HENGCE_CANONICAL_EOD","HENGCE_VERIFIED_GAP_MOTHER_RETROSPECTIVE")
                   for z in days if isinstance(z,dict))):
            return result
        cutoff=date.fromisoformat(lineage["source_cutoff"])
        if cutoff!=(decision-__import__("datetime").timedelta(days=14)):
            return result
        snapdates=[date.fromisoformat(z["snapshot_date"][:4]+"-"+
                                       z["snapshot_date"][4:6]+"-"+
                                       z["snapshot_date"][6:8]) for z in snaps]
        if (snapdates!=sorted(snapdates) or snapdates[-1]>cutoff
            or (cutoff-snapdates[-1]).days>7
            or any((b-a).days<5 or (b-a).days>10
                   for a,b in zip(snapdates,snapdates[1:]))
            or any(z.get("source_type") not in (
                "HENGCE_EXISTING_G1_457_WEEK_RESEARCH_MOTHER",
                "CANONICAL_TDCC_FIRST_OBSERVED_STRICT",
                "CANONICAL_TDCC_FIRST_OBSERVED_RECONCILED_RESEARCH_ONLY")
                for z in snaps)):
            return result
        rows=d.get("all_qualified")
        top=d.get("top5")
        if (not isinstance(rows,list) or not isinstance(top,list)
            or len(top)!=min(5,len(rows)) or len(rows)!=d.get("qualified_count")
            or len(rows)>3000 or top!=rows[:len(top)]):
            return result
        seen=set(); prev_turnover=None
        for i,rr in enumerate(rows,1):
            if not isinstance(rr,dict):
                return result
            ticker=rr.get("ticker")
            if (not isinstance(ticker,str) or len(ticker)!=4 or not ticker.isdigit()
                or ticker.startswith("0") or ticker in seen or rr.get("rank")!=i
                or rr.get("authorized_lots")!=0
                or rr.get("chip_date")!=snapdates[-1].isoformat()):
                return result
            seen.add(ticker)
            for key in ("reference_close","r20_pct","r5_pct",
                        "retail_2week_pct","median_20d_turnover_twd"):
                n=rr.get(key)
                if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n):
                    return result
            if not (rr["reference_close"]>0 and rr["r20_pct"]>=5
                    and rr["r5_pct"]>=0 and rr["retail_2week_pct"]<=-1
                    and rr["median_20d_turnover_twd"]>=10_000_000):
                return result
            turn=rr["median_20d_turnover_twd"]
            if prev_turnover is not None and (turn>prev_turnover):
                return result
            prev_turnover=turn
        age=(now.date()-decision).days
        result.update(
            status=("NO_QUALIFIED_WEEKLY_RESEARCH_STOCKS" if not top
                    else ("WEEKLY_RESEARCH_TOP5_READY" if age<=14
                          else "STALE_WEEKLY_RESEARCH_TOP5")),
            source_date=decision.isoformat(),age_calendar_days=age,
            qualified_count=len(rows),top5=top,
            original_model_commit=d["original_screen_commit"],
            historical_asof_proof_missing=d["historical_asof_proof_missing"],
            research_not_trade=True,not_current_recommendations=True,
            source_kind="HENGCE_ORIGINAL_EOD_TDCC_RESEARCH_ONLY",
            current_selection=False,
        )
    except (OSError,KeyError,ValueError,TypeError,AttributeError):
        return result
    return result

def research_top5_observation(now=None, root=None):
    """Show an independently reproduced V2.2 research Top5, NEVER a live signal.

    This deliberately reads only a checked-in, versioned research receipt.
    It neither runs the unmerged selection strategy nor reaches a broker.
    """
    current=weekly_v22_research_observation(now,root)
    if current is not None:
        return current
    import math
    now=now or datetime.now(TZ)
    now=(now if now.tzinfo else now.replace(tzinfo=TZ)).astimezone(TZ)
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    report={"status":"NOT_AVAILABLE","research_only":True,
            "current_selection":False,"source_date":None,
            "ranking_authority":False,"formal_selection_authority":False,
            "buy_signal":False,"sell_signal":False,"authorized_lots":0,
            "capital_authority_twd":0,"broker_execution":False,
            "top5":[],"source_path":V22_RESEARCH_PATH}
    if selected_model_preference(root).get("status") not in ("PREFERRED_RESEARCH_MODEL_NOT_LIVE","PREFERRED_DAILY_RESEARCH_MODEL_NOT_LIVE"):
        report["status"]="V22_PREFERENCE_UNVERIFIED"
        return report
    try:
        d=json.loads((root/V22_RESEARCH_PATH).read_text(encoding="utf-8"))
        decision=date.fromisoformat(d["decision_date"])
        chip_dates=[date.fromisoformat(x.replace("-","")[:4]+"-"+x.replace("-","")[4:6]+"-"+x.replace("-","")[6:8]) for x in d["tdcc_snapshot_dates"]]
        if not (d.get("schema")=="HENGCE_V22_RESEARCH_TOP5_SCAN_OBSERVATION_V1"
                and d.get("system")=="HENGCE"
                and d.get("status")=="RETROSPECTIVE_V22_TOP5_READY"
                and d.get("model_id")=="all_qualified_top5_v1"
                and d.get("original_v22_screen_pinned_commit")=="4a0f98fd2bd2a65deb2ebaf61e15e77c6a7893d6"
                and d.get("source_workflow_run")=="https://github.com/seabeen927349-hub/-hengce-live-quotes/actions/runs/42827400295"
                and d.get("source_artifact_id")==13769224243
                and d.get("source_parent_mother_sha256")=="b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93"
                and d.get("source_parent_tdcc_sha256")=="71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88"
                and d.get("research_only") is True
                and d.get("official_pit_certified") is False
                and d.get("model_literature_gate")=="NOT_PASSED"
                and d.get("clean_oos_or_live_validated") is False
                and d.get("formal_selection_authority") is False
                and d.get("buy_signal") is False and d.get("sell_signal") is False
                and d.get("broker_execution") is False
                and d.get("authorized_lots")==0 and d.get("capital_authority_twd")==0
                and d.get("not_live_quotes") is True
                and d.get("decision_is_current") is False
                and d.get("source_observed_date")==d.get("decision_date")
                and decision==date(2026,11,6) and decision<=now.date()
                and d.get("original_eod_days")==13 and d.get("mother_backfill_days")==8
                and d.get("price_input_rows")==22865 and d.get("tdcc_input_rows")==3248
                and len(chip_dates)==3
                and chip_dates==[date(2026,10,8),date(2026,10,16),date(2026,10,22)]
                and (decision-max(chip_dates)).days>=14
                and d.get("qualified_count")==7):
            report["status"]="RESEARCH_RECEIPT_NOT_VERIFIED"
            return report
        records=d.get("top5")
        if not isinstance(records,list) or len(records)!=5:
            report["status"]="RESEARCH_RANKING_INVALID"
            return report
        validated=[]; seen=set()
        for i,x in enumerate(records,1):
            ticker=x.get("ticker") if isinstance(x,dict) else None
            if not (isinstance(ticker,str) and len(ticker)==4 and ticker.isdigit()
                    and ticker not in seen and x.get("rank")==i
                    and x.get("authorized_lots")==0
                    and x.get("source")=="ORIGINAL_V22_SCREEN_P64_AT_PINNED_COMMIT"
                    and x.get("chip_date")=="2026-10-22"):
                report["status"]="RESEARCH_RANKING_INVALID"
                return report
            seen.add(ticker)
            for key in ("reference_close","r20_pct","r5_pct","retail_2week_pct","median_20d_turnover_twd"):
                value=x.get(key)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                    report["status"]="RESEARCH_METRICS_INVALID"
                    return report
            if not (x["reference_close"]>0 and x["r20_pct"]>=5
                    and x["r5_pct"]>=0 and x["retail_2week_pct"]<=-1
                    and x["median_20d_turnover_twd"]>=10_000_000):
                report["status"]="RESEARCH_METRICS_INVALID"
                return report
            validated.append({
                "rank":i,"ticker":ticker,"reference_close_on_decision":x["reference_close"],
                "r20_pct":x["r20_pct"],"r5_pct":x["r5_pct"],
                "retail_2week_pct":x["retail_2week_pct"],
                "median_20d_turnover_twd":x["median_20d_turnover_twd"],
                "research_only":True,"authorized_lots":0,
                "reference_price_is_not_live_quote":True})
        if any(validated[i]["median_20d_turnover_twd"]<validated[i+1]["median_20d_turnover_twd"]
               for i in range(4)):
            report["status"]="RESEARCH_RANKING_ORDER_INVALID"
            return report
        report.update(status="HISTORICAL_RESEARCH_TOP5_VERIFIED",
                      source_date=decision.isoformat(),
                      reconstructed_at="2026-11-10",
                      age_calendar_days=(now.date()-decision).days,
                      source_kind="EXISTING_HENGCE_MOTHER_RETROSPECTIVE",
                      model_original_commit=d["original_v22_screen_pinned_commit"],
                      source_workflow_run=d["source_workflow_run"],
                      qualified_count=d["qualified_count"],
                      retrospective_only=True,not_current_recommendations=True,
                      pit_evidence="HISTORICAL_FIRST_OBSERVED_UNVERIFIED",
                      top5=validated)
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        report["status"]="RESEARCH_RECEIPT_UNREADABLE"
    return report

def report(now=None, root=None, *, holdings=None, journal=None, previous=None, vessel=None):
    """Read-only full scan: separate historical ranking from actual-account review."""
    now=now or datetime.now(TZ)
    now=(now if now.tzinfo else now.replace(tzinfo=TZ)).astimezone(TZ)
    v22=research_top5_observation(now,root)
    try:
        from scripts.hengce_v22d_daily_reader import observation as v22d_observation
    except ModuleNotFoundError:
        from hengce_v22d_daily_reader import observation as v22d_observation
    v22d=v22d_observation(now,root)
    try:
        from scripts.hengce_v22d_max5_operations import worklist as max5_worklist
    except ModuleNotFoundError:
        from hengce_v22d_max5_operations import worklist as max5_worklist
    account_review=max5_worklist(now,root,holdings=holdings,
                                 journal=journal,previous=previous,selection=v22d,vessel=vessel)
    return {
        "schema_version":3,"system":"HENGCE","module":"HENGCE_SCAN_ONCE_ROUTER",
        "generated_at_taipei":now.isoformat(),"trade_date":now.date().isoformat(),
        "status":"NO_ACTIVE_SELECTION_STRATEGY","binding_status":"FAIL_CLOSED",
        "active_strategy_count":0,"active_strategy":None,"selection_sources":[],
        "authority":"NO_SELECTION_OR_TRADING_AUTHORITY","can_create_new_entry":False,
        "buy_signal":False,"sell_signal":False,"rows":[],
        "ranking_authority":False,"signal_authority":False,
        "capital_authority_twd":0,"broker_order_execution":False,
        "reason":"ALL_SELECTION_FAMILIES_RETIRED",
        "reporting":{"status":"NO_ACTIVE_STRATEGY","active_strategy_count":0,
          "active_strategy":None,"top10":[],"action_card":{"status":"NO_BUY","ticker":None},
          "research_advisory":advisory(now,root),
          "selected_model_preference":selected_model_preference(root),
          "v22d_primary_research_top5":v22d,
          "v22d_max5_daily_account_worklist":account_review,
          "v22_research_top5":v22,
          "v22_legacy_benchmark_only":True,
          "v22_atr_max5_price_plan":build_price_plan(now,root,verified_v22=v22),
          "v22d_atr_max5_price_plan":build_price_plan(now,root,verified_v22=v22d),
          "consistency_evidence":consistency_snapshot(now,root)},
        "retirement_lock":"hengce/HENGCE_Q017_RETIREMENT_LOCK_20261105.json",
        "market_data_collectors":"SEPARATE_UNCHANGED"}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--now");parser.add_argument("--display-only",action="store_true")
    parser.add_argument("--account-holdings",help="private user-account holdings CSV")
    parser.add_argument("--account-journal",help="private actual trade journal CSV")
    parser.add_argument("--previous-worklist",help="previous research-only worklist JSON")
    parser.add_argument("--original-canonical-2026",help="existing SHA-pinned Library canonical mother CSV, local")
    parser.add_argument("--original-tdcc-781",help="existing SHA-pinned G1 457-week TDCC cohort, local")
    args=parser.parse_args()
    if bool(args.original_canonical_2026)!=bool(args.original_tdcc_781):
        parser.error("Both original canonical and G1 TDCC original files are required together.")
    try:
        try:
            from scripts.hengce_v22d_max5_operations import _load_csv, HOLDING_COLS, JOURNAL_COLS
        except ModuleNotFoundError:
            from hengce_v22d_max5_operations import _load_csv, HOLDING_COLS, JOURNAL_COLS
        holdings=(_load_csv(args.account_holdings,HOLDING_COLS[:4])
                  if args.account_holdings else None)
        journal=(_load_csv(args.account_journal,JOURNAL_COLS)
                 if args.account_journal else None)
        previous=(json.loads(Path(args.previous_worklist).read_text(encoding="utf-8"))
                  if args.previous_worklist else None)
        vessel=None
        if args.original_canonical_2026:
            try:
                from scripts.hengce_v22d_existing_canonical_atr import OriginalCanonicalMotherATR
            except ModuleNotFoundError:
                from hengce_v22d_existing_canonical_atr import OriginalCanonicalMotherATR
            vessel=OriginalCanonicalMotherATR(
                Path(args.original_canonical_2026),Path(args.original_tdcc_781))
        now=datetime.fromisoformat(args.now) if args.now else None
        result=report(now,holdings=holdings,journal=journal,
                      previous=previous,vessel=vessel)
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
        return 0
    except (OSError,ValueError,TypeError) as e:
        print(json.dumps({"status":"BLOCKED_INPUT_VALIDATION",
                          "reason":str(e),"broker_order_execution":False,
                          "buy_signal":False,"sell_signal":False},
                         ensure_ascii=False,allow_nan=False))
        return 2
if __name__=="__main__":raise SystemExit(main())
