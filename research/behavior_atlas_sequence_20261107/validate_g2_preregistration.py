#!/usr/bin/env python3
"""G2 only: fail-closed mechanical pre-registration checks. No data or outcomes are analyzed."""
from pathlib import Path
import json, subprocess, sys
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'behavior_atlas_20261107'
P=ROOT/'SOURCE_HASH_LOCK.json'
EXPECTED=["S4A","S4B","S12A","S12B","S24A","S24B"]
def check(cond,msg):
    if not cond: raise ValueError("G2_PRE_REG_FAIL_CLOSED: "+msg)
def parse(name):return json.loads((ROOT/name).read_text(encoding="utf-8"))
def main():
    g=parse("LITERATURE_GATE.json")
    s=parse("06_SPLIT_AND_BASELINES.json")
    e=parse("07_EXPERIMENT_BUDGET.json")
    lock=parse("SOURCE_HASH_LOCK.json")
    state=parse("ACTIVE_STAGE.json")
    parent=json.loads((BASE/"STAGE_GATE_STATE.json").read_text(encoding="utf-8"))
    check(g.get("literature_status")=="PASS" and g.get("literature_review_complete") is True,"LITERATURE_G0_NOT_PASS")
    check(g.get("scope_definition","").startswith("STRICT SUBSET"),"GATE_SCOPE_BROADENED")
    check(parent.get("terminal_outcome")=="DESCRIPTIVE_ONLY" and parent.get("research_phase")=="CLOSED_DESCRIPTIVE_ONLY","PARENT_RESEARCH_REOPENED")
    check(parent.get("stages",[{}, {}, {}])[1].get("descriptive_research_gate")=="PASS_SCOPED_RETROSPECTIVE","G1_SCOPED_SOURCE_GATE_MISSING")
    check(parent.get("stages",[{}, {}, {}])[1].get("predictive_pit")=="BLOCKED","HISTORICAL_TDCC_PIT_FAKE_PASS")
    check(state.get("active_stage")=="G2","STAGE_NOT_G2")
    check(state.get("mode") in ("PREREGISTRATION_ONLY","G2_LOCKED_NO_EXECUTION"),"STAGE_MODE_NOT_G2")
    check(state.get("research_model_authority") is False and state.get("trading_authority") is False,"MODEL_OR_TRADE_AUTHORITY")
    check(s.get("G0")=="PASS_INHERITED_STRICT_SCOPE" and s.get("G1")=="PASS_RESTRICTED_RETROSPECTIVE_SCOPE_ONLY","BAD_SCOPED_STAGE_GATES")
    check(s.get("authorization",{}).get("G5_and_G6_authorized") is False,"G5_G6_FORBIDDEN")
    check(s.get("time_alignment",{}).get("reference_date_is_not_release_date") is True,"TDCC_PUBLISH_DATE_LOOKAHEAD")
    check(s.get("time_alignment",{}).get("PIT_for_prediction") is False,"PIT_FOR_PREDICTION")
    check(s.get("sample_constraints",{}).get("never_filter_by_present_day_listing",True) is True,"SURVIVORSHIP_RISK")
    check(s.get("experiment_budget",{}).get("registered_primary_experiments")==6,"NON_FROZEN_EXPERIMENT_COUNT")
    check(s.get("experiment_budget",{}).get("family_count")==3,"FAMILY_COUNT_NOT_THREE")
    check(e.get("experiment_count_cap")==6 and e.get("number_of_primary_test_families")==3 and e.get("tests_per_family")==2,"BUDGET_CHANGED")
    check(e.get("experiment_order")==EXPECTED,"EXPERIMENT_ORDER_CHANGED")
    check(e.get("activated_primary_experiments")==0,"EXPERIMENT_RUN_DURING_G2")
    check(len(e.get("experiment_details",[]))==6 and [x.get("id") for x in e["experiment_details"]]==EXPECTED,"RECIPE_SET_MISSING")
    check([x.get("horizon_weeks") for x in e["experiment_details"]]==[4,4,12,12,24,24],"WEEK_WINDOWS_CHANGED")
    check([x.get("finance_sessions") for x in e["experiment_details"]]==[20,20,60,60,120,120],"TRADING_DAY_WINDOWS_CHANGED")
    check(e.get("permutation_count")==999 and e.get("max_G4_replication_runs")==1,"INFERENCE_BUDGET_CHANGED")
    check(e.get("underpowered_horizons")==[24],"LONG_WINDOWS_CONSTRAINT_REMOVED")
    check(e.get("no_N2_model_authority") is True,"N2_AUTHORITY_CHANGED")
    check(e.get("G5_status","").startswith("BLOCKED") and e.get("G6_status","").startswith("BLOCKED"),"ILLEGAL_DOWNSTREAM_PASS")
    check(lock.get("total_usable_primary_experiments_budget")==6 and lock.get("already_seen_results_contamination") is True,"SOURCE_LOCK_CONFLICT")
    registered=lock.get("preregistered_files",[])
    check(len(registered)==4,"PREREG_FILES_NOT_FOUR")
    for v in registered:
        path=Path(v["path"])
        check(path.exists(),"MISSING_FILE_"+str(path))
        got=subprocess.check_output(["git","hash-object",str(path)],text=True).strip()
        check(got==v["git_blob_sha"],"BLOB_HASH_NOT_LOCKED_"+str(path))
    check((ROOT/"05_PREREGISTRATION_LOCK.md").exists(),"PROTOCOL_MISSING")
    check(lock.get("input_sources",[{}, {}, {}])[0].get("sha256")=="b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93","MOTHER_SOURCE_HASH_CHANGED")
    check(lock.get("input_sources",[{}, {}, {}])[1].get("internal_gzip_sha256")=="e78b967042bd0d9058c0eded1b7c2b80ae03cb9c0c7fbc1ca660844d0126f7a3","TDCC_SOURCE_HASH_CHANGED")
    check(lock.get("input_sources",[{}, {}, {}])[2].get("sha256")=="0d708990cafdc679a7f92ab0ca49363acbde93bf64490e446a81c2ffdb414cb6","G1_SCOPE_HASH_CHANGED")
    print("HENGCE_BEHAVIOR_SEQUENCE_G2_VALID_LOCKED: 6 recipes; 3 horizons; 0 executed; G5/G6 blocked")
if __name__=="__main__":
    try:main()
    except Exception as ex:
        print(str(ex),file=sys.stderr)
        sys.exit(2)
