#!/usr/bin/env python3
"""Validate user-requested TDCC retail headcount G2 amendment; no backtests."""
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
OLD=REPO/"research"/"behavior_atlas_sequence_20261107"
PARENT=REPO/"research"/"behavior_atlas_20261107"
def insist(condition,msg):
    if not condition:raise ValueError("G2_RETAIL_V2_FAIL_CLOSED: "+msg)
def load(path):return json.loads(Path(path).read_text("utf-8"))
def git_blob(path):
    return subprocess.check_output(["git","hash-object",str(path)],text=True,cwd=REPO).strip()
def check():
    lock=load(ROOT/"SOURCE_HASH_LOCK_RETAIL_V2.json")
    state=load(ROOT/"ACTIVE_STAGE_RETAIL_V2.json")
    g1=load(ROOT/"G1_RETAIL_COVERAGE_GATE.json")
    s=load(ROOT/"06_SPLIT_AND_BASELINES_RETAIL_V2.json")
    e=load(ROOT/"07_EXPERIMENT_BUDGET_RETAIL_V2.json")
    original_state=load(PARENT/"STAGE_GATE_STATE.json")
    insist(original_state.get("terminal_outcome")=="DESCRIPTIVE_ONLY","ORIGINAL_PARENT_STUDY_CHANGED")
    insist(original_state.get("research_phase")=="CLOSED_DESCRIPTIVE_ONLY","ORIGINAL_PARENT_STUDY_REOPENED")
    for key,name in [("protocol","05_PREREGISTRATION_LOCK.md"),("methods","06_SPLIT_AND_BASELINES.json"),("budget","07_EXPERIMENT_BUDGET.json")]:
        insist(git_blob(OLD/name)==lock["base_prereg_docs_git_blob_shas"][key],"IMMUTABLE_V1_"+key)
    insist(state["stage"] in ("G2","G3") and state["G2_status"]=="PASS_METHOD_LOCKED","V2_NOT_METHOD_LOCKED")
    insist(0<=state["G3_experiments_executed"]<=6,"G3_BUDGET_OVERRUN")
    insist(e["activated_primary_experiments"]==0,"BUDGET_ALREADY_USED")
    insist(e["experiment_count_cap"]==6 and e["number_of_primary_test_families"]==3,"BUDGET_CHANGED")
    insist(e["experiment_order"]==["S4A","S4B","S12A","S12B","S24A","S24B"],"WRONG_TEST_SEQUENCE")
    insist(e["permutation_count"]==999 and e["max_G4_replication_runs"]==1,"TEST_LIMITS_CHANGED")
    insist(e["primary_variable_counts"]=={"tdcc_holder_vectors":6,"institution_margin_vectors":4,"combinations_per_primary_test":24,"main_experiments_total":6},"24_PAIR_RETAIL_CONTRACT_CHANGED")
    insist(len(e["experiment_details"])==6 and all("24 predefined comparisons" in x["derived_variables"] for x in e["experiment_details"]),"24_PAIR_RECIPE_MISSING")
    insist(len(s["variables"]["tdcc_holder_vector"])==6 and len(s["variables"]["institution_margin_vector"])==4,"BAD_VARIABLE_COUNT")
    derived=s["variables"]["tdcc_retail_derived_definitions"]
    insist(derived[0]["levels"]==[1,2,3] and derived[1]["levels"]==[4,5,6,7,8],"RETAIL_TIER_BOUNDARIES_CHANGED")
    insist(derived[2]["status"].startswith("G1_QA_ONLY") and derived[3]["status"].startswith("G1_QA_ONLY"),"UNREGISTERED_EXTRA_HYPOTHESIS")
    insist(s["time_alignment"]["weekly_scale"]==[4,12,24] and s["time_alignment"]["sessions_per_scale"]==[20,60,120],"TIME_HORIZON_CHANGED")
    insist(e["underpowered_horizons"]==[24],"UNDERPOWERED_RESTRICTION_DROPPED")
    insist(s["sample_constraints"]["retail_15grade_coverage_gate"]=="BLOCKED_PENDING_MATCHED_ALL_PERIOD_SOURCE_QA","UNVERIFIED_SAMPLE_APPROVED")
    insist(s["time_alignment"]["PIT_for_prediction"] is False,"PIT_NOT_PROVEN")
    insist(g1["gate_status"] in ("BLOCKED","PASS"),"G1_UNKNOWN_STATUS")
    # Preserve the original G1 BLOCKED document's preregistered Git blob SHA.
    # An append-only PASS evidence receipt is the only way to authorize G3.
    new_gate=ROOT/"G1_RETAIL_COVERAGE_GATE_PASS_20261107.json"
    if new_gate.exists():
        passed=load(new_gate)
        ev=passed.get("evidence",{})
        insist(passed.get("pass_status")=="PASS_SCOPED_RETROSPECTIVE_BEHAVIOR_ONLY","BAD_G1_PASS_RECORD")
        insist(ev.get("original_G1_scoped_candidate_stockweeks")==443341 and ev.get("full_15_grade_original_people_matches")==443341,"SCOPE_COVERAGE_CHANGED")
        insist(ev.get("valid_account_holder_grade_stockweeks")==443207 and ev.get("invalid_local_grade_stockweeks")==134,"G1_RAW_GRADE_QA_CHANGED")
        insist(ev.get("aggregate_source_sha256")=="71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88","G1_RAW_SOURCE_HASH_CHANGED")
        insist(ev.get("raw_finmind_archive_weeks")==404 and ev.get("raw_official_2025_tail_2026_weeks")==53,"WEEK_SOURCE_MISSING")
        insist(state["G3_enabled"] is True and state["G1_new_retail_count_grade_source_status"].startswith("PASS"),"G1_PASS_BUT_G3_UNAUTHORIZED")
    else:
        insist(state["G3_enabled"] is False and state["G1_new_retail_count_grade_source_status"].startswith("BLOCKED"),"UNAUTHORIZED_G3_UNBLOCKED")
        insist(state["G3_experiments_executed"]==0,"UNAUTHORIZED_G3_EXECUTION")
    insist(g1["approved_v2_G3_for_expanded_variables"] is False,"ORIGINAL_BLOCKED_G1_DOCUMENT_MUTATED")
    insist(state["trading_authority"] is False and state["model_authority"] is False,"UNAUTHORIZED_MODEL_OR_TRADING")
    insist(len(lock["v2_docs"])==5,"MISSING_LOCK_DOCS")
    for d in lock["v2_docs"]:
        f=REPO/d["path"]
        insist(f.exists(),"MISSING_LOCKED_DOCUMENT_"+d["path"])
        insist(git_blob(f)==d["git_blob_sha"],"RETAIL_V2_DOC_MUTATED_"+d["path"])
    original_spec=load(OLD/"SOURCE_HASH_LOCK.json")
    insist(original_spec["original_study_must_remain_closed"] is True,"V1_SOURCE_LOCK_MISMATCH")
    insist(lock["new_15_level_source_status"].startswith("PARTIAL_"),"UNVERIFIED_FULL_COVERAGE_CLAIM")
    print("HENGCE_G2_RETAIL_HEADCOUNT_V2_VALID: 6 fixed tests; 24 pairings; G1 retail source pass=" + str(new_gate.exists()) + "; G3 completed=" + str(state["G3_experiments_executed"]))
if __name__=="__main__":
    try:check()
    except Exception as error:
        print(str(error),file=sys.stderr)
        sys.exit(2)
