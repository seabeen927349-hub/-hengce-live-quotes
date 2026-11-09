#!/usr/bin/env python3
"""Research-only HENGCE S5 / Escape / RMS Top1-5 cooperation adapter.
Unverified evidence remains UNKNOWN. Never mutates governed HENGCE data or trading authority.
"""
import argparse
import json
from pathlib import Path

S5_ROLE = "DESCRIPTIVE_ONLY_NO_TRADING_AUTHORITY"
ESCAPE_LEVELS = {
    0:"L0_NORMAL",1:"L1_VULNERABLE",2:"L2_FIRST_SHOT",
    3:"L3_SECOND_SHOT_PROPAGATION",4:"L4_REGIME_CONFIRMATION",
    5:"L5_ABSOLUTE_WITHDRAWAL",6:"L6_PRICE_DAMAGE",
}

def advisory(s5:dict,escape:dict,rms:dict)->dict:
    s5_valid=(s5.get("status")=="PASS" and
        s5.get("state") in {"DIFFUSE_NORMAL","SYNCHRONIZED_STRESS"} and
        s5.get("authority")==S5_ROLE and s5.get("trading_effect")=="NONE" and
        bool(s5.get("market_event_date")))
    level=escape.get("escape_level")
    esc_valid=(escape.get("status")=="PASS_ADVISORY_ONLY" and
        escape.get("trading_authority")=="NONE" and
        escape.get("formal_flow_state_allowed") is True and
        escape.get("phase") in {"EOD_FORMAL","NEXT_DAY_RECONCILIATION","OWNERSHIP_WEEKLY"} and
        type(level) is int and level in ESCAPE_LEVELS and
        escape.get("escape_state")==ESCAPE_LEVELS.get(level) and
        bool(escape.get("trade_date")))
    ranks=rms.get("ranked_tickers")
    ranks_valid=(rms.get("status")=="RESEARCH_ONLY_NO_TRADING_AUTHORITY" and
        isinstance(ranks,list) and 1<=len(ranks)<=5 and
        len(ranks)==len(set(ranks)) and
        all(isinstance(t,str) and len(t)==4 and t.isdigit() for t in ranks) and
        bool(rms.get("features_asof")))
    problems=[]
    if not s5_valid:problems.append("S5_NOT_VERIFIED")
    if not esc_valid:problems.append("ESCAPE_FORMAL_NOT_VERIFIED")
    if not ranks_valid:problems.append("RMS_RESEARCH_RANKING_NOT_VERIFIED")
    if s5_valid and esc_valid and s5["market_event_date"]!=escape["trade_date"]:
        problems.append("S5_ESCAPE_DATE_MISMATCH")
        esc_valid=False
    if s5_valid and ranks_valid and s5["market_event_date"]!=rms["features_asof"]:
        problems.append("S5_RMS_DATE_MISMATCH")
        ranks_valid=False
    desc=("UNKNOWN_MARKET_STATE" if not s5_valid else
          "OBSERVED_SYNCHRONIZED_STRESS" if s5["state"]=="SYNCHRONIZED_STRESS" else
          "OBSERVED_DIFFUSE_NORMAL")
    if not s5_valid or not esc_valid:
        combined="UNVERIFIED_FOR_FORMAL_COLLABORATION"
    elif level>=3 and escape.get("regime_type")=="INTERNAL_ROTATION":
        combined="ROTATION_FLOW_WARNING_NOT_BROAD_EXIT"
    elif level>=3 and s5["state"]=="SYNCHRONIZED_STRESS":
        combined="CONCURRENT_S5_STRESS_AND_ESCALATED_ESCAPE"
    elif level>=2:
        combined="ESCAPE_WARNING_WITHOUT_S5_STRESS_CONFIRMATION"
    elif s5["state"]=="SYNCHRONIZED_STRESS":
        combined="S5_STRESS_ESCAPE_FLOW_UNCONFIRMED"
    else:
        combined="NO_CONFIRMED_DUAL_ESCALATION"
    return {"system":"HENGCE","artifact":"RESEARCH_MONITOR_COLLABORATION_V01",
      "status":"RESEARCH_DIAGNOSTIC_ONLY",
      "s5_state":desc,"s5_date":s5.get("market_event_date") if s5_valid else None,
      "escape_formal_valid":esc_valid,
      "escape_level":level if esc_valid else None,
      "rms_ranked_1_to_5":ranks if ranks_valid else [],
      "combined_diagnostic":combined,"missing_or_invalid_evidence":problems,
      "selection_authority":False,"signal_authority":False,
      "capital_authority":False,"trading_authority":False,
      "authorized_trade_action":"NONE",
      "note":"Original HENGCE blood vessels must independently verify source provenance."}

def main():
    p=argparse.ArgumentParser()
    for n in ("s5","escape","rms"):p.add_argument("--"+n,required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    def load(f):
        o=json.loads(f.read_text(encoding="utf8"))
        if not isinstance(o,dict):raise ValueError("Expected JSON object")
        return o
    out=advisory(load(a.s5),load(a.escape),load(a.rms))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(out,ensure_ascii=False))
if __name__=="__main__":main()
