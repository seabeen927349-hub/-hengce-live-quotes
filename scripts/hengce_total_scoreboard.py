#!/usr/bin/env python3
"""All HENGCE selection families retired; read-only empty live scoreboard."""
import argparse,json
from pathlib import Path
RETIRED_OPERATIONAL_FAMILIES={"Q017_CANONICAL_FAMILY","E2_PROFIT_MAX_FAMILY","V43_FAMILY","X_FAMILY","NEXTDAY_FAMILY"}
def build(*args,**kwargs):
    return {"schema_version":4,"system":"HENGCE","module":"HENGCE_TOTAL_SCOREBOARD",
       "status":"NO_ACTIVE_SELECTION_STRATEGY","active_strategy_count":0,
       "active_operational_families":[],"retired_operational_families":sorted(RETIRED_OPERATIONAL_FAMILIES),
       "attention_leader":None,"top10":[],"rows":[],
       "action_card":{"status":"NO_BUY","ticker":None,"buy_price":None,"sell_price":None},
       "authority":{"display_only_meta_analysis":True,"capital_authority_twd":0,"broker_order_execution":False}}
def main():
    p=argparse.ArgumentParser()
    for n in ("q017-json","e2-json","v43-json","w1-json","price-history","out"):
        p.add_argument("--"+n,type=Path)
    p.add_argument("--include-retired-research",action="store_true");a=p.parse_args()
    s=json.dumps(build(),ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(s,encoding="utf-8")
    print(s,end="")
if __name__=="__main__":main()
