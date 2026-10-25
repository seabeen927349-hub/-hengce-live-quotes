#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

POLICY_VERSION = 'HENGCE_V43_W1_RESONANCE_V1'
GRADE_ORDER = {'S': 0, 'A': 1, 'B': 2, 'C': 3}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def normalize(rows, score_keys):
    out=[]
    for i,row in enumerate(rows,1):
        t=str(row.get('ticker') or row.get('symbol') or '').strip()
        if not t:
            continue
        score=None
        for k in score_keys:
            if row.get(k) is not None:
                score=float(row[k]); break
        out.append({'ticker':t,'name':row.get('name',''),'rank':i,'score':score})
    n=len(out)
    for r in out:
        r['percentile']=1.0-(r['rank']-1)/max(1,n-1)
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


def grade(v, w, v_top3: bool, w_top20: bool):
    # S: exact legacy hard resonance.
    if v_top3 and w_top20:
        return 'S'
    # A: V43 core pick with W1 broad top-15% support.
    if v_top3 and w['percentile'] >= .85:
        return 'A'
    # B: W1 core pick with V43 broad top-15% support.
    if w_top20 and v['percentile'] >= .85:
        return 'B'
    # C: both models independently place the name in their top 15%.
    if v['percentile'] >= .85 and w['percentile'] >= .85:
        return 'C'
    return None


def build(v43_obj: dict, w1_obj: dict) -> dict:
    vr=extract_v43(v43_obj); wr=extract_w1(w1_obj)
    vm={r['ticker']:r for r in vr}; wm={r['ticker']:r for r in wr}
    vtop={r['ticker'] for r in vr[:3]}; wtop={r['ticker'] for r in wr[:20]}
    rows=[]
    for t in sorted(set(vm)&set(wm)):
        v,w=vm[t],wm[t]
        g=grade(v,w,t in vtop,t in wtop)
        if not g:
            continue
        # Rank-based consensus only; not a third predictive model and not tuned to returns.
        consensus=(v['percentile']+w['percentile'])/2
        rows.append({
            'ticker':t,
            'name':v.get('name') or w.get('name') or '',
            'grade':g,
            'v43_rank':v['rank'],'v43_percentile':round(v['percentile'],8),'v43_score':v['score'],
            'w1_rank':w['rank'],'w1_percentile':round(w['percentile'],8),'w1_score':w['score'],
            'resonance_score':round(consensus,8),
        })
    rows.sort(key=lambda r:(GRADE_ORDER[r['grade']],-r['resonance_score'],r['v43_rank'],r['w1_rank'],r['ticker']))
    by_grade={g:[r for r in rows if r['grade']==g] for g in ('S','A','B','C')}
    return {
        'policy_version':POLICY_VERSION,
        'status':'PASS',
        'purpose':'report-layer resonance only; frozen V43/W1 model rules are unchanged',
        'definitions':{
            'S':'V43 Top3 AND W1 Top20',
            'A':'V43 Top3 AND W1 percentile >= 85%',
            'B':'W1 Top20 AND V43 percentile >= 85%',
            'C':'both V43 and W1 percentile >= 85% but not S/A/B',
        },
        'v43_universe_size':len(vr),'w1_universe_size':len(wr),
        'counts':{g:len(by_grade[g]) for g in ('S','A','B','C')},
        'rows':rows,
        'guards':[
            'No V43 or W1 weights, thresholds, holding periods, costs, or historical frontier metrics are changed.',
            'Resonance score is the simple mean of within-model rank percentiles and has no order authority.',
            'Fail closed when either lane exposes only truncated Top-K output; do not fabricate soft resonance from missing ranks.',
        ],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--v43-json',type=Path,required=True)
    ap.add_argument('--w1-json',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    res=build(read_json(args.v43_json),read_json(args.w1_json))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(res,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
