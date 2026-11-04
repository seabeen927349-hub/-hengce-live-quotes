#!/usr/bin/env python3
"""HENGCE scan once: no active strategy and no order authority."""
import argparse,json
from datetime import datetime
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Taipei")
def report(now=None):
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
          "active_strategy":None,"top10":[],"action_card":{"status":"NO_BUY","ticker":None}},
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
