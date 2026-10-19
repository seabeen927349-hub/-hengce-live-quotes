#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, math
from datetime import datetime
from pathlib import Path

import hengce_q017_decision_lock_v4 as v4

core=v4.core
ROOT=Path(__file__).resolve().parents[1]
SHADOW=ROOT/'shadow'/'full_market_latest.json'
OUTDIR=ROOT/'receipts'
OUTDIR.mkdir(parents=True,exist_ok=True)

def sha(o):
    return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def f(x):
    try:
        y=float(x)
        return y if math.isfinite(y) else None
    except Exception:
        return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--date',default='2026-10-19')
    args=ap.parse_args()
    td=datetime.strptime(args.date,'%Y-%m-%d').date()

    hist=core.load_tw_history()
    srows=core.read_sox()
    sf=core.sox_features(td)
    betas,prev,names,hist_date,universe=core.current_betas(hist,srows)
    members=set(str(x) for x in universe)
    eligible=[t for t in sorted(members) if betas.get(t) is not None and betas.get(t)>0 and prev.get(t)]
    if not eligible:
        raise RuntimeError('NO_Q017_ELIGIBLE_ELECTRONICS')

    dxy=v4.refresh_dxy(td)
    gate_go,checks=v4.evaluate_market_gate(sf,dxy)

    sh=json.loads(SHADOW.read_text(encoding='utf-8'))
    if sh.get('authority')!='SHADOW_CONTEXT_ONLY_NO_CAPITAL_AUTHORITY':
        raise RuntimeError('SOURCE_SHADOW_AUTHORITY_DRIFT')
    qrows=sh.get('quotes') or []
    qmap={str(q.get('ticker')):q for q in qrows if q.get('ticker') is not None}

    candidates=[]
    quote_seen=0
    open_seen=0
    missing_quote=[]
    no_open=[]
    ref_mismatch=[]
    for t in eligible:
        q=qmap.get(t)
        if not q:
            missing_quote.append(t)
            continue
        quote_seen+=1
        op=f(q.get('open'))
        if op is None:
            no_open.append(t)
            continue
        pc_q=f(q.get('reference_close'))
        pc_hist=f(prev.get(t))
        pc=pc_q if pc_q not in (None,0) else pc_hist
        if pc in (None,0):
            no_open.append(t)
            continue
        open_seen+=1
        if pc_q not in (None,0) and pc_hist not in (None,0) and abs(pc_q-pc_hist)>1e-8:
            ref_mismatch.append({'ticker':t,'quote_reference_close':pc_q,'history_previous_close':pc_hist})
        b=float(betas[t])
        gap=op/pc-1.0
        expected=b*float(sf['sox_1d'])
        residual=gap-expected
        if residual>0.04:
            continue
        score=b*(1.0+25.0*max(-residual,0.0))
        candidates.append({
            'ticker':t,
            'name':q.get('name') or names.get(t,''),
            'beta60':b,
            'open':op,
            'reference_close':pc,
            'gap':gap,
            'expected_gap':expected,
            'residual':residual,
            'score':score,
            'model_qualified_if_observable_at_0901':bool(gate_go),
            'source_quote_fetched_at_taipei':q.get('fetched_at_taipei'),
            'source_trade_time':q.get('trade_time'),
        })
    candidates.sort(key=lambda x:(-x['score'],x['ticker']))

    e2_path=ROOT/'hengce'/'e2_live'/'state_latest.json'
    e2=json.loads(e2_path.read_text(encoding='utf-8')) if e2_path.exists() else None
    out={
        'schema_version':2,
        'system':'HENGCE',
        'module':'Q017_HYPOTHETICAL_OPEN_RECONSTRUCTION',
        'trade_date':td.isoformat(),
        'generated_at_taipei':core.now_tw().isoformat(),
        'authority':'HYPOTHETICAL_ONLY_ZERO_CAPITAL_AUTHORITY',
        'formal_buy_count':0,
        'formal_q017_today_unchanged':'NO_FORMAL_SIGNAL_WITHOUT_SCHEMA5_0901_OBSERVATION',
        'purpose':'Counterfactual: what Q017 ranking would have looked like if these actual session-open fields had been observed and immutably sealed during 09:01.',
        'causality_warning':{
            'actual_0901_observation_file_used':False,
            'late_snapshot_open_field_used':True,
            'open_price_is_session_open_but_0901_observability_cannot_be_proven':True,
            'must_not_be_promoted_to_formal_signal':True
        },
        'source':{
            'file':'shadow/full_market_latest.json',
            'snapshot_id':sh.get('snapshot_id'),
            'generated_at_taipei':sh.get('generated_at_taipei'),
            'source_authority':sh.get('authority'),
            'universe_count':sh.get('universe_count'),
            'provider_covered_count':sh.get('provider_covered_count')
        },
        'q017_universe_lock':{
            'scope':'TWSE_LISTED_ELECTRONICS_ONLY',
            'history_latest_date':hist_date,
            'universe_count':len(members),
            'eligible_positive_beta_count':len(eligible),
            'eligible_quote_row_count':quote_seen,
            'eligible_quote_row_coverage':quote_seen/len(eligible) if eligible else 0,
            'eligible_with_open_field_count':open_seen,
            'opened_coverage':open_seen/len(eligible) if eligible else 0,
            'missing_quote_count':len(missing_quote),
            'missing_quote_tickers':missing_quote,
            'quote_present_but_no_open_count':len(no_open),
            'quote_present_but_no_open_tickers':no_open,
            'coverage_interpretation':'Provider quote-row coverage and opened-trade coverage are different. A quote row with no open can be a causal not-yet-opened state and is not automatically a provider failure.',
            'non_electronics_allowed':False
        },
        'market_gate':{
            'gate_go':gate_go,
            'checks':checks,
            'sox_1d':sf['sox_1d'],
            'sox_5d':sf['sox_5d'],
            'dxy_5d':dxy['dxy_5d'],
            'dxy_latest_session':dxy.get('latest_session')
        },
        'model_rules':{
            'residual_max':0.04,
            'score':'beta*(1+25*max(-residual,0))',
            'top_n':3
        },
        'hypothetical_top3':candidates[:3],
        'hypothetical_top10':candidates[:10],
        'qualified_candidate_count':len(candidates),
        'reference_close_mismatch_count':len(ref_mismatch),
        'reference_close_mismatch_sample':ref_mismatch[:20],
        'e2_context':None if not e2 else {
            'signal_asof':e2.get('signal_asof'),
            'market_regime':e2.get('market_regime'),
            'strict_engine_status':(e2.get('strict') or {}).get('engine_status'),
            'strict_buy_count':(e2.get('strict') or {}).get('buy_count')
        }
    }
    out['receipt_sha256']=sha({k:v for k,v in out.items() if k!='receipt_sha256'})
    path=OUTDIR/f'HENGCE_Q017_HYPOTHETICAL_OPEN_RECONSTRUCTION_{td.strftime("%Y%m%d")}.json'
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
