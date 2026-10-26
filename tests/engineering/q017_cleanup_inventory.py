"""Reproducible static inventory; unknown reachability never means dead code."""
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/q017_codex_cleanup_20261026/results'
BASE='780e8a225de637c32b42da0d28f5aa1428e49e20'


def write(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    paths=sorted(set(subprocess.check_output(['git','-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard'],text=True).splitlines()))
    sources=[p for p in paths if Path(p).suffix in {'.py','.sh','.yml','.yaml'} and not p.startswith('research/q017_codex_cleanup_20261026/results/')]
    texts={p:(ROOT/p).read_text() for p in sources}
    modules={Path(p).stem:p for p in sources if p.startswith('scripts/') and p.endswith('.py')}
    records=[];duplicates=defaultdict(list)
    for path,text in texts.items():
        imports=[];functions=[];references=[]
        if path.endswith('.py'):
            tree=ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):imports.extend(x.name for x in node.names)
                if isinstance(node,ast.ImportFrom):imports.append(node.module or '')
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    functions.append({'name':node.name,'line':node.lineno})
                    if path.startswith('scripts/') and not Path(path).name.startswith('test_'):
                        signature=ast.dump(ast.Module(body=node.body,type_ignores=[]),include_attributes=False)
                        if len(signature)>80:
                            duplicates[hashlib.sha256(signature.encode()).hexdigest()].append({'path':path,'function':node.name,'line':node.lineno})
        references=sorted(set(re.findall(r'(?:scripts/[A-Za-z0-9_.-]+\.(?:py|sh)|hengce/[A-Za-z0-9_/.*-]+\.(?:json|csv|jsonl))',text)))
        role=('OFFLINE_TEST_OR_AUDIT' if path.startswith('tests/') or Path(path).name.startswith('test_') else
              'WORKFLOW' if path.startswith('.github/') else
              'Q017_RUNTIME_OR_BOUNDARY' if 'q017' in path else
              'LEGACY_DATA_LIBRARY_RETAINED' if path=='scripts/hengce_daily_command_center_core_legacy.py' else
              'FORMAL_OUTPUT_SURFACE' if Path(path).stem in {'hengce_scan_once_router','hengce_unified_scan_display','hengce_dual_engine_display','RUN_INTRADAY_ACTION_BOARD'} else
              'OTHER_RUNTIME_RESEARCH_OR_INFRASTRUCTURE')
        records.append({'path':path,'role':role,'sha256':hashlib.sha256(text.encode()).hexdigest(),
                        'local_imports':sorted(set(modules[x] for x in imports if x in modules)),
                        'artifact_or_script_literals':references,'functions':functions,
                        'has_main_entrypoint':"__main__" in text,'reachability':'STATIC_REFERENCES_ONLY_DYNAMIC_OPERATOR_INVOCATION_POSSIBLE'})
    groups=[{'body_ast_sha256':key,'candidates':value,'disposition':'RETAIN_NOT_PROVEN_BEHAVIORALLY_INTERCHANGEABLE'} for key,value in duplicates.items() if len(value)>1]
    write('SOURCE_INVENTORY.json',{'baseline_commit':BASE,'method':'All tracked and new code/workflows; AST local imports, function definitions and literal references; no claim of complete dynamic call-graph proof',
                                  'source_count':len(records),'sources':records})
    write('DUPLICATE_AND_DEAD_CODE_MAP.json',{
        'exact_ast_body_duplicate_candidates':groups,
        'centralized':[{'symbol':'Q017_ONLY_POLICY','owner':'scripts/hengce_q017_formal_output.py','consumers':['scripts/hengce_q017_only_runner.py','scripts/hengce_scan_once_router.py']}],
        'retained_semantic_boundaries':[
            {'paths':['scripts/hengce_q017_decision_lock.py','scripts/hengce_q017_decision_lock_v4.py','scripts/hengce_q017_observation_lock_v5.py'],
             'reason':'v5 imports v4 which imports legacy helpers. Older capture/monitor CLIs are compatibility/research paths, never a substitute schema-5 source.'},
            {'paths':['scripts/hengce_q017_premarket_snapshot_v1.py','scripts/hengce_q017_observer_supervisor_v2.py'],
             'reason':'Local history/cache preparation overlaps; unchanged because prewarm/fallback timing and tuple contracts differ.'},
            {'paths':['scripts/hengce_q017_canonical_producer.py','scripts/hengce_unified_candidate_adapter.py'],
             'reason':'Daily top1/H20/no-DXY and schema-5 top3/H10/DXY are distinct contracts. Never deduplicate formula/ranking across them.'}],
        'quarantined_by_output_validation':['schema1/schema3/schema4 radar outputs','daily canonical artifacts without schema5 observation/decision binding','LEGACY-only mixed candidate publications','retired E2/NOVA/V43/W1/Q1/M1 artifacts'],
        'deleted_files':[],'proven_dead_code':[],'unknown_reachability_policy':'Keep historical code/evidence; a missing static incoming reference is not proof of deadness.'})
    write('Q017_AUTHORITY_ROUTE_MAP.json',{
        'formal_hengce_stock_output_engine':'Q017','formal_schema':5,'baseline_commit':BASE,
        'canonical_pipeline':[
            {'stage':'premarket','code':['hengce_q017_macro_cache_v1','hengce_q017_premarket_snapshot_v1'],'authority':'ZERO_SIGNAL_AUTHORITY'},
            {'stage':'capture','code':['hengce_q017_observer_supervisor_v2','hengce_q017_observer_supervisor_v1','hengce_q017_observation_lock_v5.collect_observation'],'source':'TWSE_MIS only in authorized 09:01 quote lane; morning macro/cache unchanged'},
            {'stage':'observation','artifact':'hengce/q017_radar/observations/YYYYMMDD_0901_observation.json','validation':'validate_observation; 100% eligible quote rows; immutable minute; universe/hash'},
            {'stage':'compute_and_ranking','code':'hengce_q017_observation_lock_v5.build_decision_from_observation','policy':'Frozen bytes; positive beta; frozen residual/gate/score; stable existing ranking; top3'},
            {'stage':'decision','artifact':'hengce/q017_radar/decision/YYYYMMDD_0901.json','validation':'hengce_q017_authority_guard_v5.validate_decision_payload; deterministic exact recompute'},
            {'stage':'recovery','code':'hengce_q017_recovery_compute_v5','policy':'Canonical wins; backup promoted only if missing; no late quote fetch'},
            {'stage':'formal_display_boundary','code':'hengce_q017_formal_output.current_decision','policy':'Current dated immutable file; never latest fallback; reject future computation'},
            {'stage':'display','code':['hengce_dual_engine_display.build','hengce_scan_once_router.build_reporting'],'policy':'Q017 schema5 current dated decision; E2/other retained lanes explicitly research/retired'},
            {'stage':'action_publication','code':['hengce_scan_once_router._current_q017_action','hengce_unified_scan_display.main'],
             'policy':'Complete transaction hashes and freshness, Q017-only provenance and frozen order/scores, schema5 hash binding; current daily bridge lacks binding and therefore fails closed'}],
        'artifact_owners':{
            'latest.json':'Root quote transport only; no stock-ranking authority',
            'live/active.json':'Quote transport only; no candidate/model authority',
            'hengce/q017_radar/observation_latest.json':'Convenience pointer; dated immutable observation is authority',
            'hengce/q017_radar/decision_latest.json':'Convenience pointer; dated immutable decision is authority',
            'hengce/q017_radar/latest.json':'Monitor/failure projection; cannot override dated authority',
            'hengce/q017_canonical/latest.json':'Distinct daily candidate contract; research/bridge input only; not schema5 evidence',
            'hengce/dual_engine/latest.json':'Compatibility display artifact; Q017 formal, E2 research only',
            'hengce/unified/latest.json':'Gated public CLI projection; no legacy-only formal fallback',
            'work_output/intraday_action_board/*':'Local transactional artifacts; receipt alone cannot certify Q017-only formal output',
            'hengce/health/latest.json':'Observability only; removed router input dependency',
            'hengce/e2_live/*, hengce/v43_daily/*, research/*':'Research/audit only'},
        'public_commands':[
            {'command':'python scripts/hengce_scan_once_router.py','gate':'Full bundle plus Q017 schema5; reporting schema5 validated separately'},
            {'command':'python scripts/hengce_unified_scan_display.py','gate':'Full bundle plus Q017 schema5'},
            {'command':'bash scripts/RUN_INTRADAY_ACTION_BOARD.sh','gate':'Q017-only candidate runner; formal display still requires schema5 binding'},
            {'command':'python scripts/hengce_dual_engine_display.py','gate':'Current dated schema5 decision; E2 research explicitly non-formal'},
            {'command':'python scripts/hengce_daily_command_center.py --mode radar','gate':'Permanent legacy kill switch'},
            {'command':'legacy v3/v4 direct producer/guard CLIs','gate':'Retained for audit; schema5 public boundary rejects old outputs'},
            {'command':'canonical producer / unified generic runner / scoreboard / retired screen CLIs','gate':'Research/internal artifact generation; public formal output boundary rejects missing schema5 bindings and legacy rows'}],
        'all_workflow_and_command_source_references':'SOURCE_INVENTORY.json',
        'workflows':[{'path':r['path'],'scripts_and_artifacts':r['artifact_or_script_literals'],
                      'publication':'repository artifact writer' if 'hengce_publish.py' in texts[r['path']] else 'CI/research/transport; inspect literals',
                      'formal_authority':'ONLY_VALID_SCHEMA5_Q017_AT_PUBLIC_OUTPUT_BOUNDARY'} for r in records if r['role']=='WORKFLOW'],
        'limitations':['Static inventory does not prohibit arbitrary future code or administrator edits. Regression gates enforce the current reviewed formal surfaces.',
                       'Historical files are preserved in place; no new training, input acquisition or 2026 outcome-based tuning.']})
    overview=['# Q017 inventory\n',f'Baseline: `{BASE}`. Scanned {len(records)} code/workflow files; full definitions, local imports, source hashes and artifact literals are in `SOURCE_INVENTORY.json`.\n',
              'Read `Q017_AUTHORITY_ROUTE_MAP.json` for every inventoried workflow and the capture → observation → validation → compute/rank → decision → display/output path. `DUPLICATE_AND_DEAD_CODE_MAP.json` records duplicate candidates and every deliberate non-refactor.\n',
              '## Formal schema-5 path\n',
              'Morning macro cache and prewarm snapshot → independent primary/backup supervisors → original v5 observation collector using v4/legacy transport helpers → immutable dated observation → frozen v5 decision builder → immutable dated decision → deterministic v5 guard → current-session formal output boundary → compatibility display/router. Recovery can promote an already preserved valid backup; it cannot fetch replacement quotes.\n',
              'The 09:01 lane still uses the existing TWSE MIS contract and retry window. No model/cache/transport/capture/recovery mathematics changed. Positive-beta eligible quote rows require 100% completeness. A row without an opening price is causal unopened-market state, not permission to backfill.\n',
              '## Distinct daily candidate bridge\n',
              'The daily canonical producer uses top1, daily electronics residuals, no DXY and H20; schema-5 uses top3, immutable opening evidence, the frozen DXY gate and H10 research horizon. These are not interchangeable. Legacy geometry is not a candidate source. A daily bridge without exact schema-5 observation/decision bindings cannot produce formal action; it remains available internally for research.\n',
              '## Coupling and legacy state\n',
              'v5 → v4 → legacy decision helpers → public command-center data helpers → retained legacy core. This is live dependency reuse, so old filenames are not dead-code evidence. Former v3/v4 guard aliases and old radar outputs cannot satisfy the schema-5 output gate. The legacy public radar kill switch stays enabled. E2/NOVA/V43/W1/Q1/M1 and other retained experiment files remain audit/research only.\n',
              'Router health reads were an observability dependency rejected by the existing producer audit; the formal router now emits an observability-only placeholder. Health output does not select or authorize stocks.\n',
              '## Ownership and replay risks\n',
              'Root `latest.json` and `live/active.json` are quote transport. Radar `latest.json`, `observation_latest.json` and `decision_latest.json` are projections/pointers. Current dated observation/decision files and their bound hashes control authority. Stale pointers cannot select a prior session or override a current valid decision. Publication receipts must bind the complete transaction and its freshness.\n',
              'Monitor payloads previously could retain ticker order while changing scores or market state; the guard now checks all immutable decision fields. The frozen builder is shared by deterministic replay and production; profiling observes its full candidate list rather than implementing a second ranking formula.\n',
              '## Files by role\n','| Path | Role |\n|---|---|']
    overview.extend(f"| `{r['path']}` | {r['role']} |" for r in records)
    (OUT/'INVENTORY.md').write_text('\n'.join(overview)+'\n')
    print(json.dumps({'sources':len(records),'duplicate_candidate_groups':len(groups),'workflows':sum(r['role']=='WORKFLOW' for r in records)}))


if __name__=='__main__': main()
