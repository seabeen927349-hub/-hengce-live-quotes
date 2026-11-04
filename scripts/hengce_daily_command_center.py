#!/usr/bin/env python3
"""Retired legacy command center, independent original EOD workflow unaffected."""
import argparse,json
from datetime import datetime
from zoneinfo import ZoneInfo
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["self-test","premarket","radar","postclose"],required=True)
    p.add_argument("--date");a=p.parse_args()
    d={"system":"HENGCE","module":"LEGACY_DAILY_COMMAND_CENTER","mode":a.mode,
       "status":"RETIRED_NO_SELECTION_OR_LEGACY_DATA_WRITES",
       "generated_at_taipei":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
       "ranking_authority":False,"signal_authority":False,"broker_order_execution":False,"rows":[],
       "original_eod_workflow":"hengce-original-eod-ingest.yml"}
    print(json.dumps(d,ensure_ascii=False,indent=2))
    return 0 if a.mode=="self-test" else 2
if __name__=="__main__":raise SystemExit(main())
