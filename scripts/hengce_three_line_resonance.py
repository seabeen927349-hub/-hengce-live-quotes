#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math
from datetime import date
from pathlib import Path

POLICY='HENGCE_Q017_V43_W1_RESONANCE_V2'
GRADE_ORDER={'SS':0,'S':1,'A':2,'B':3,'C':4}
Q017_SCHEMA5_MODULES={
 'Q017_SOX_ELECTRONICS_RADAR_LOCKED','Q017_SOX_ELECTRONICS_DECISION_LOCK','Q017_0901_OBSERVATION_LOCK'
}

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def iso(v):
    if not isinstance(v,str): return None
    try: return v if date.fromisoformat(v).isoformat()==v else None
    except ValueError: return None

def signal_day(obj,lane):
    v=iso(obj.get('signal_date'))
    if not v and isinstance(obj.get('screen'),dict): v=iso(obj['screen'].get('signal_date'))
    if v: return v,'EXPLICIT_SIGNAL_DATE'
    if lane=='Q017' and obj.get('module') in Q017_SCHEMA5_MODULES:
        td=iso(obj.get('trade_date'))
        lock=obj.get('decision_lock') or obj.get('observation_lock') or {}
        if td and lock.get('cutoff_label')=='09:01': return td,'Q017_SCHEMA5_0901_TRADE_DATE_AS_SIGNAL_SESSION'
    raise ValueError(f'{lane}_SIGNAL_DATE_REQUIRED')

def ticker_rows(value):
    if not isinstance(value,list): return []
    out=[]; seen=set()
    for i,x in enumerate(value,1):
        if isinstance(x,str): r={'ticker':x}
        elif isinstance(x,dict): r=dict(x)
        else: raise ValueError('INVALID_RANKING_ROW')
        t=str(r.get('ticker') or r.get('symbol') or '').strip()
        if not t or t in seen: raise ValueError('MISSING_OR_DUPLICATE_RANKING_TICKER')
        seen.add(t); r['ticker']=t; r.setdefault('rank',i); out.append(r)
    return out

def normalize(rows,score_keys):
    rows=ticker_rows(rows)
    if not rows: return None
    out=[]
    for i,r in enumerate(rows,1):
        rank=r.get('rank',i)
        if type(rank) is not int or rank<1: raise ValueError('INVALID_RANKING_RANK')
        score=None
        for k in score_keys:
            if r.get(k) is not None:
                score=float(r[k])
                if not math.isfinite(score): raise ValueError('NONFINITE_OR_INVALID_RANKING_SCORE')
                break
        out.append({'ticker':r['ticker'],'name':r.get('name',''),'rank':rank,'score':score})
    out.sort(key=lambda z:(z['rank'],z['ticker']))
    n=len(out)
    for i,r in enumerate(out,1): r['rank']=i; r['percentile']=1-(i-1)/max(1,n-1)
    return out

def selected_set(obj):
    d=obj.get('decision') if isinstance(obj.get('decision'),dict) else {}
    out=set()
    for k in ('selected_tickers','selected','picks','top_picks'):
        for src in (obj.get(k),d.get(k)):
            if isinstance(src,list):
                for x in src:
                    t=str(x if isinstance(x,str) else (x.get('ticker') if isinstance(x,dict) else '')).strip()
                    if t: out.add(t)
    return out

def extract_q017(obj):
    bs=str(obj.get('binding_status') or obj.get('status') or '').upper(); ms=str(obj.get('market_state') or '').upper()
    valid=bs=='PASS' and ms in {'GO','CASH'}
    sel=selected_set(obj) if valid and ms!='CASH' else set()
    d=obj.get('decision') if isinstance(obj.get('decision'),dict) else {}
    candidates=[obj.get('ranked_universe'), (obj.get('ranking') or {}).get('ranked_universe') if isinstance(obj.get('ranking'),dict) else None,
                (obj.get('screen') or {}).get('ranked_universe') if isinstance(obj.get('screen'),dict) else None,d.get('ranked_universe')]
    ranking=None
    if valid:
        for x in candidates:
            if isinstance(x,list) and x: ranking=normalize(x,('score','q017_score','rank_score')); break
    return {'binding_status':bs,'market_state':ms,'gate_valid':valid,'canonical_cash':ms=='CASH','selection':sel,'ranking':ranking,'authority':obj.get('authority'),'trade_date':obj.get('trade_date')}

def hard_v43(obj):
    s=obj.get('screen') if isinstance(obj.get('screen'),dict) else obj
    rows=s.get('top3') or obj.get('top3') or []
    return ticker_rows(rows)[:3]
def hard_w1(obj):
    rows=obj.get('top20') or obj.get('basket') or obj.get('tickers') or (obj.get('screen') or {}).get('top20') or []
    return ticker_rows(rows)[:20]
def full_v43(obj):
    s=obj.get('screen') if isinstance(obj.get('screen'),dict) else obj
    return normalize(s.get('ranked_universe') or obj.get('ranked_universe'),('score','v43_score'))
def full_w1(obj):
    return normalize(obj.get('latest_ranked_universe') or obj.get('ranked_universe') or (obj.get('screen') or {}).get('ranked_universe'),('tail_score','score','w1_score'))

def vw_grade(v,w,vhard,whard):
    if vhard and whard:return 'S'
    if vhard and w['percentile']>=.85:return 'A'
    if whard and v['percentile']>=.85:return 'B'
    if v['percentile']>=.85 and w['percentile']>=.85:return 'C'

def build(qo,vo,wo):
    qd,qs=signal_day(qo,'Q017'); vd,vs=signal_day(vo,'V43'); wd,ws=signal_day(wo,'W1')
    if len({qd,vd,wd})!=1: raise ValueError('LANE_SIGNAL_DATE_MISMATCH')
    q=extract_q017(qo); vh=hard_v43(vo); wh=hard_w1(wo); vset={x['ticker'] for x in vh}; wset={x['ticker'] for x in wh}
    vr=full_v43(vo); wr=full_w1(wo); soft=bool(vr and wr); vm={x['ticker']:x for x in vr or []}; wm={x['ticker']:x for x in wr or []}; qm={x['ticker']:x for x in q['ranking'] or []}
    candidates=set(vset)&set(wset)
    if q['selection']: candidates|=(q['selection']&vset)|(q['selection']&wset)
    if soft: candidates|=set(vm)&set(wm)
    rows=[]
    for t in sorted(candidates):
        qsel=t in q['selection']; vhard=t in vset; whard=t in wset; grade=reason=None; resonance=None; basis='HARD_ONLY'
        if qsel and vhard and whard: grade,reason='SS','Q017_SELECTED_AND_V43_TOP3_AND_W1_TOP20'
        elif sum(map(int,(qsel,vhard,whard)))>=2: grade,reason='S','ANY_TWO_HARD_LANES'
        if soft and t in vm and t in wm and not grade:
            v,w=vm[t],wm[t]; qr=qm.get(t); hard=sum(map(int,(qsel,vhard,whard)))
            if qr:
                ps=(v['percentile'],w['percentile'],qr['percentile'])
                if hard>=1 and all(p>=.85 for p in ps): grade,reason='A','ONE_HARD_AND_ALL_THREE_TOP15PCT'
                elif all(p>=.85 for p in ps): grade,reason='B','ALL_THREE_TOP15PCT'
                elif all(p>=.80 for p in ps): grade,reason='C','ALL_THREE_TOP20PCT'
            else:
                g=vw_grade(v,w,vhard,whard)
                if g: grade,reason=g,'V43_W1_ONLY_Q017_RANKING_UNAVAILABLE'
            comps=[v['percentile'],w['percentile']]+([qr['percentile']] if qr else []); resonance=sum(comps)/len(comps); basis='Q017_V43_W1' if qr else 'V43_W1_ONLY'
        if grade:
            rows.append({'ticker':t,'grade':grade,'grade_reason':reason,'q017_selected':qsel,'v43_top3':vhard,'w1_top20':whard,
                         'resonance_score':round(resonance,8) if resonance is not None else None,'resonance_score_basis':basis,
                         'canonical_gate':'Q017_INVALID_BLOCKED' if not q['gate_valid'] else ('CASH_BLOCKED' if q['canonical_cash'] else ('Q017_SELECTED' if qsel else 'Q017_NO_EXPLICIT_SELECTION'))})
    rows.sort(key=lambda r:(GRADE_ORDER[r['grade']],-(r['resonance_score'] or -1),r['ticker']))
    counts={g:sum(r['grade']==g for r in rows) for g in GRADE_ORDER}
    return {'policy_version':POLICY,'status':'PASS','signal_date':qd,'signal_date_resolution':{'q017':qs,'v43':vs,'w1':ws},
            'authority':{'reporting_only':True,'capital_authority_twd':0,'broker_order_execution':False,'can_upgrade_entry_trigger':False},
            'q017_gate':{'binding_status':q['binding_status'],'market_state':q['market_state'],'gate_valid':q['gate_valid'],'canonical_cash':q['canonical_cash'],'explicit_selected_count':len(q['selection']),'ranking_available':bool(q['ranking']),'authority':q['authority']},
            'hard_overlap':{'v43_top3_x_w1_top20':sorted(vset&wset),'count':len(vset&wset)},
            'soft_resonance_status':'AVAILABLE' if soft else 'DATA_PENDING_FULL_RANKS','counts':counts,'rows':rows,
            'guards':['Q017 universe membership is never a selection vote.','CASH/invalid Q017 cannot be overridden.','Top-K inputs may support hard overlap only; A/B/C soft grades require full V43 and W1 rankings.','Reporting only; no model, order or capital authority.']}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--q017-json',type=Path,required=True);ap.add_argument('--v43-json',type=Path,required=True);ap.add_argument('--w1-json',type=Path,required=True);ap.add_argument('--out',type=Path);a=ap.parse_args()
    out=build(read(a.q017_json),read(a.v43_json),read(a.w1_json)); text=json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if a.out: a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(text,encoding='utf-8')
    print(text,end='')
if __name__=='__main__': main()
