#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

POLICY_VERSION = 'HENGCE_Q017_V43_W1_RESONANCE_V2'
GRADE_ORDER = {'SS': 0, 'S': 1, 'A': 2, 'B': 3, 'C': 4}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def normalize(rows, score_keys):
    out=[]
    for i,row in enumerate(rows,1):
        if isinstance(row,str):
            row={'ticker':row}
        if not isinstance(row,dict):
            continue
        t=str(row.get('ticker') or row.get('symbol') or '').strip()
        if not t:
            continue
        score=None
        for k in score_keys:
            if row.get(k) is not None:
                try:
                    score=float(row[k])
                except (TypeError,ValueError):
                    score=None
                break
        rank=row.get('rank')
        try:
            rank=int(rank) if rank is not None else i
        except (TypeError,ValueError):
            rank=i
        out.append({'ticker':t,'name':row.get('name',''),'rank':rank,'score':score})
    out.sort(key=lambda r:(r['rank'],r['ticker']))
    n=len(out)
    for i,r in enumerate(out,1):
        # Percentile is intentionally within each lane's own eligible universe.
        r['rank']=i
        r['percentile']=1.0-(i-1)/max(1,n-1)
    return out


def extract_v43(obj: dict):
    screen=obj.get('screen',obj)
    rows=screen.get('ranked_universe') or obj.get('ranked_universe')
    if not rows:
        raise RuntimeError('V43_FULL_RANKING_REQUIRED: top3-only input cannot support soft resonance')
    return normalize(rows,('score','v43_score'))


def extract_w1(obj: dict):
    rows=(obj.get('latest_ranked_universe') or obj.get('ranked_universe') or
          (obj.get('screen') or {}).get('ranked_universe'))
    if not rows:
        raise RuntimeError('W1_FULL_RANKING_REQUIRED: top20-only input cannot support soft resonance')
    return normalize(rows,('tail_score','score','w1_score'))


def _ticker_set(value):
    if not isinstance(value,list):
        return set()
    out=set()
    for x in value:
        if isinstance(x,str):
            t=x.strip()
        elif isinstance(x,dict):
            t=str(x.get('ticker') or x.get('symbol') or '').strip()
        else:
            t=''
        if t:
            out.add(t)
    return out


def extract_q017(obj: dict):
    """Treat Q017 as canonical gate first, ranking signal second.

    CASH is authoritative even when research lanes have strong resonance. Q017 is
    only counted as a hard stock-selection vote when the producer explicitly emits
    selected/pick tickers. Membership in the 457-name universe is NOT a selection.
    """
    market_state=str(obj.get('market_state') or '').upper()
    binding_status=str(obj.get('binding_status') or obj.get('status') or '').upper()
    trade_date=obj.get('trade_date') or obj.get('signal_date')

    decision=obj.get('decision') if isinstance(obj.get('decision'),dict) else {}
    selection=set()
    for key in ('selected_tickers','selected','picks','top_picks'):
        selection |= _ticker_set(obj.get(key))
        selection |= _ticker_set(decision.get(key))
    # CASH always means no canonical stock selection for resonance promotion.
    if market_state == 'CASH':
        selection=set()

    ranking=None
    candidates=[
        obj.get('ranked_universe'),
        (obj.get('ranking') or {}).get('ranked_universe') if isinstance(obj.get('ranking'),dict) else None,
        (obj.get('screen') or {}).get('ranked_universe') if isinstance(obj.get('screen'),dict) else None,
        decision.get('ranked_universe'),
    ]
    for rows in candidates:
        if isinstance(rows,list) and rows:
            ranking=normalize(rows,('score','q017_score','rank_score'))
            break

    return {
        'trade_date':trade_date,
        'binding_status':binding_status,
        'market_state':market_state,
        'canonical_cash':market_state == 'CASH',
        'selected_tickers':selection,
        'ranking':ranking,
        'ranking_available':bool(ranking),
        'authority':obj.get('authority'),
    }


def vw_grade(v,w,v_top3:bool,w_top20:bool):
    if v_top3 and w_top20:
        return 'S'
    if v_top3 and w['percentile'] >= .85:
        return 'A'
    if w_top20 and v['percentile'] >= .85:
        return 'B'
    if v['percentile'] >= .85 and w['percentile'] >= .85:
        return 'C'
    return None


def final_grade(v,w,q,qrow,v_top3:bool,w_top20:bool,q_selected:bool):
    # Highest grade requires explicit three-lane stock agreement.
    if q_selected and v_top3 and w_top20:
        return 'SS','Q017_SELECTED_AND_V43_TOP3_AND_W1_TOP20'

    # Any two hard stock votes are S. Q017 CASH can never contribute a hard vote.
    hard_votes=int(v_top3)+int(w_top20)+int(q_selected)
    if hard_votes >= 2:
        return 'S','ANY_TWO_HARD_LANES'

    # Three-way near resonance is only allowed when Q017 exposes a real ranking.
    if qrow is not None:
        ps=(v['percentile'],w['percentile'],qrow['percentile'])
        if max(hard_votes,0) >= 1 and all(p >= .85 for p in ps):
            return 'A','ONE_HARD_AND_ALL_THREE_TOP15PCT'
        if all(p >= .85 for p in ps):
            return 'B','ALL_THREE_TOP15PCT'
        if all(p >= .80 for p in ps):
            return 'C','ALL_THREE_TOP20PCT'

    # If Q017 has no ranking, preserve the V43/W1 research grade but never pretend
    # it is three-line confirmation.
    g=vw_grade(v,w,v_top3,w_top20)
    if g:
        return g,'V43_W1_ONLY_Q017_RANKING_UNAVAILABLE'
    return None,None


def build(q017_obj:dict,v43_obj:dict,w1_obj:dict) -> dict:
    q=extract_q017(q017_obj)
    vr=extract_v43(v43_obj); wr=extract_w1(w1_obj)
    vm={r['ticker']:r for r in vr}; wm={r['ticker']:r for r in wr}
    qm={r['ticker']:r for r in (q['ranking'] or [])}
    vtop={r['ticker'] for r in vr[:3]}; wtop={r['ticker'] for r in wr[:20]}

    rows=[]
    for t in sorted(set(vm)&set(wm)):
        v,w=vm[t],wm[t]
        qrow=qm.get(t)
        q_selected=t in q['selected_tickers']
        grade,reason=final_grade(v,w,q,qrow,t in vtop,t in wtop,q_selected)
        if not grade:
            continue

        components=[v['percentile'],w['percentile']]
        score_basis='V43_W1_ONLY'
        if qrow is not None:
            components.append(qrow['percentile'])
            score_basis='Q017_V43_W1'
        resonance=sum(components)/len(components)

        if q['canonical_cash']:
            canonical_gate='CASH_BLOCKED'
        elif q_selected:
            canonical_gate='Q017_SELECTED'
        else:
            canonical_gate='Q017_NO_EXPLICIT_SELECTION'

        rows.append({
            'ticker':t,
            'name':v.get('name') or w.get('name') or (qrow or {}).get('name') or '',
            'grade':grade,
            'grade_reason':reason,
            'q017_selected':q_selected,
            'q017_rank':qrow['rank'] if qrow else None,
            'q017_percentile':round(qrow['percentile'],8) if qrow else None,
            'q017_score':qrow['score'] if qrow else None,
            'v43_rank':v['rank'],'v43_percentile':round(v['percentile'],8),'v43_score':v['score'],
            'w1_rank':w['rank'],'w1_percentile':round(w['percentile'],8),'w1_score':w['score'],
            'resonance_score':round(resonance,8),
            'resonance_score_basis':score_basis,
            'canonical_gate':canonical_gate,
        })

    rows.sort(key=lambda r:(GRADE_ORDER[r['grade']],-r['resonance_score'],r['v43_rank'],r['w1_rank'],r['ticker']))
    by_grade={g:[r for r in rows if r['grade']==g] for g in ('SS','S','A','B','C')}

    return {
        'policy_version':POLICY_VERSION,
        'status':'PASS',
        'purpose':'three-lane report-layer resonance; Q017 remains canonical gate while V43/W1 remain independent research signals',
        'q017_gate':{
            'trade_date':q['trade_date'],
            'binding_status':q['binding_status'],
            'market_state':q['market_state'],
            'canonical_cash':q['canonical_cash'],
            'ranking_available':q['ranking_available'],
            'explicit_selected_count':len(q['selected_tickers']),
            'authority':q['authority'],
        },
        'definitions':{
            'SS':'Q017 explicit selection AND V43 Top3 AND W1 Top20',
            'S':'any two hard lanes agree',
            'A':'with Q017 ranking: one hard lane and all three >=85%; otherwise preserved V43/W1 A-grade only',
            'B':'with Q017 ranking: all three >=85%; otherwise preserved V43/W1 B-grade only',
            'C':'with Q017 ranking: all three >=80%; otherwise preserved V43/W1 C-grade only',
            'canonical_rule':'Q017 market_state=CASH blocks canonical action regardless of research resonance grade',
        },
        'v43_universe_size':len(vr),'w1_universe_size':len(wr),'q017_ranked_universe_size':len(q['ranking'] or []),
        'counts':{g:len(by_grade[g]) for g in ('SS','S','A','B','C')},
        'rows':rows,
        'guards':[
            'Q017 universe membership is never treated as a stock-selection vote.',
            'Q017 CASH is authoritative for canonical action and cannot be overridden by V43/W1 resonance.',
            'Q017 contributes percentile/rank only when its producer explicitly exposes a ranked universe.',
            'No Q017, V43, or W1 model weights, thresholds, holding periods, costs, or frontier metrics are changed.',
            'Resonance is reporting-only and has zero broker/order/capital authority.',
            'V43/W1 soft resonance still fails closed when either lane exposes only truncated Top-K output.',
        ],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--q017-json',type=Path,required=True)
    ap.add_argument('--v43-json',type=Path,required=True)
    ap.add_argument('--w1-json',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    res=build(read_json(args.q017_json),read_json(args.v43_json),read_json(args.w1_json))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(res,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
