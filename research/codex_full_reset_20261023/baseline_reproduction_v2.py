#!/usr/bin/env python3
"""One preregistered pinned-function baseline diagnostic; no optimizer/promotion."""
import ast,csv,gzip,hashlib,json,math,statistics,subprocess,sys,types
from collections import defaultdict
from datetime import date
from pathlib import Path
from reset_ledger import TrialLedger,AUTHORITY
from stage_b_build_twse_year import ROOT,RESET,CORPUS_BASE,verify_pinned_file
from stage_c_rule_search import load_macro,prior_macro,finite_float,max_drawdown,product_return,validate_mother_receipt

RESULTS=RESET/'results'
def sha(data):return hashlib.sha256(data).hexdigest()
def load_pinned_functions(raw_rows):
    source=subprocess.check_output(['git','-C',str(ROOT),'show',CORPUS_BASE+':scripts/hengce_e2_live.py'])
    tree=ast.parse(source)
    wanted={'f','iso_date','tw_rows_through','prepare_features'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    if len(nodes)!=4:raise ValueError('PINNED_FUNCTION_SET_MISMATCH')
    scope={'math':math,'defaultdict':defaultdict,'median':statistics.median,
           'core':types.SimpleNamespace(load_tw_history=lambda:raw_rows)}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'LIQ20_MIN','BETA_WINDOW','BETA_MIN','RESID_MAX','K'}:
            scope[node.targets[0].id]=ast.literal_eval(node.value)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<PINNED_E2_PURE_FUNCTIONS>','exec'),scope)
    return scope,sha(source)

def main():
    plan_path=RESET/'BASELINE_REPRODUCTION_V2_PLAN.json';plan=json.loads(plan_path.read_text());identifier=plan['experiment_id']
    output=RESULTS/'BASELINE_REPRODUCTION_V2.json'
    if output.exists():raise ValueError('DIAGNOSTIC_ALREADY_RETAINED_NO_OVERWRITE')
    provenance={'study':'PINNED_E2_BASELINE_V2','code_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
                'diagnostic_code_sha256':sha(Path(__file__).read_bytes()),'plan_sha256':sha(plan_path.read_bytes()),'frozen_corpus_base':CORPUS_BASE}
    with TrialLedger(RESULTS/'stage_c/EXPERIMENT_LEDGER.jsonl',provenance) as ledger:
        ledger.append({'record_id':identifier+':STARTED','experiment_id':identifier,'status':'STARTED','record_type':'BASELINE_DIAGNOSTIC_V2'})
        try:
            mother=RESULTS/'stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
            receipt=validate_mother_receipt(mother,RESULTS/'stage_b/TWSE_MOTHER_RECEIPT.json')
            with gzip.open(mother,'rt') as stream:raw_rows=list(csv.DictReader(stream))
            by_key={(r['date'],r['ticker']):r for r in raw_rows};dates=sorted({r['date'] for r in raw_rows});indices={d:i for i,d in enumerate(dates)}
            funcs,source_sha=load_pinned_functions(raw_rows)
            captured={}
            def profile(frame,event,arg):
                if frame.f_code is funcs['prepare_features'].__code__ and event=='return':captured.update(frame.f_locals['market'])
            previous=sys.getprofile()
            try:
                sys.setprofile(profile)
                funcs['prepare_features'](funcs['tw_rows_through'](date.fromisoformat(dates[-1])),date.fromisoformat(dates[-1]))
            finally:sys.setprofile(previous)
            macro_path=ROOT/'research/e2_profit_max/macro/sox_daily_202212_202610.csv';verify_pinned_file(macro_path)
            sox=load_macro(macro_path);events=[];censored=[];blocked_exit='';signal_checks=0
            for d in sorted(captured):
                if d<=blocked_exit:continue
                m=captured[d];macro=prior_macro(sox,d)
                if not(m['m1'] is not None and m['m1']<0 and m['m5'] is not None and m['m5']<=-.02 and macro and macro['ret1'] is not None and macro['ret1']<=0 and macro['ret5'] is not None and macro['ret5']<=-.03):continue
                _,candidates,_=funcs['prepare_features'](funcs['tw_rows_through'](date.fromisoformat(d)),date.fromisoformat(d));signal_checks+=1
                if not candidates:continue
                top=candidates[0];entry_i=indices[d]+1;exit_i=entry_i+20
                if exit_i>=len(dates):continue
                entry,exit_date=dates[entry_i],dates[exit_i]
                op=finite_float(by_key.get((entry,top['ticker']),{}).get('open'))
                close=finite_float(by_key.get((exit_date,top['ticker']),{}).get('close'))
                blocked_exit=exit_date
                if op is None or close is None or op<=0 or close<=0:
                    censored.append({'signal_date':d,'ticker':top['ticker'],'reason':'MISSING_FIXED_TOP1_OUTCOME_NO_REPLACEMENT'});continue
                events.append({'signal_date':d,'entry_date':entry,'exit_date':exit_date,'ticker':top['ticker'],'net_return':close/op-1-.008})
                print('Pinned baseline signal '+d+' '+top['ticker'],flush=True)
            nets=[e['net_return'] for e in events];expected=json.loads((ROOT/'research/e2_profit_max/E2_PROFIT_MAX_CANDIDATE_B_FINAL_VALIDATION_20261019.json').read_text())['pit_2023_2025']
            metrics={'entries':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'return':product_return(nets),'trade_endpoint_max_drawdown':max_drawdown(nets)}
            match=not censored and metrics['entries']==expected['entries'] and metrics['wins']==expected['wins'] and math.isclose(metrics['return'],expected['return'],abs_tol=1e-10) and math.isclose(metrics['trade_endpoint_max_drawdown'],expected['maxdd'],abs_tol=1e-10)
            result={'experiment_id':identifier,'status':'AGGREGATE_MATCH_PINNED_FUNCTIONS' if match else 'BASELINE_STILL_DIFFERS_OR_INCOMPLETE',
                    'metrics':metrics,'expected_aggregate':expected,'events':events,'censored':censored,'gate_eligible_signal_checks':signal_checks,
                    'source_commit':CORPUS_BASE,'source_sha256':source_sha,'mother_sha256':receipt['mother_sha256'],'plan_sha256':sha(plan_path.read_bytes()),
                    'original_event_identity_proven':False,'stage_c_decision_unchanged':'NO_ROBUST_WINNER',
                    'caveat':'Aggregate agreement cannot authenticate corrupt original event payload. This diagnostic reuses old semantics, with no new family selection or promotion.', 'authority':AUTHORITY}
            output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
            ledger.append({'record_id':identifier+':RESULT','experiment_id':identifier,'status':'EVALUATED','record_type':'BASELINE_DIAGNOSTIC_V2','result_sha256':sha(output.read_bytes()),'metrics':metrics,'result':result['status']})
            print(json.dumps({'status':result['status'],'metrics':metrics},sort_keys=True))
        except BaseException as exc:
            ledger.append({'record_id':identifier+':FAILED','experiment_id':identifier,'status':'ABORTED' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'FAILED','error':str(exc)});raise
if __name__=='__main__':main()
