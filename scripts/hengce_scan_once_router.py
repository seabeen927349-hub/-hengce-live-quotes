#!/usr/bin/env python3
"""HENGCE scan once: no active strategy and no order authority."""
import argparse,json,hashlib
from datetime import datetime,date
from pathlib import Path
from zoneinfo import ZoneInfo
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

def report(now=None, root=None):
    now=now or datetime.now(TZ)
    now=(now if now.tzinfo else now.replace(tzinfo=TZ)).astimezone(TZ)
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
          "research_advisory":advisory(now,root)},
        "retirement_lock":"hengce/HENGCE_Q017_RETIREMENT_LOCK_20261105.json",
        "market_data_collectors":"SEPARATE_UNCHANGED"}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--now");parser.add_argument("--display-only",action="store_true")
    args=parser.parse_args()
    now=datetime.fromisoformat(args.now) if args.now else None
    print(json.dumps(report(now),ensure_ascii=False,indent=2,allow_nan=False))
    return 0
if __name__=="__main__":raise SystemExit(main())
