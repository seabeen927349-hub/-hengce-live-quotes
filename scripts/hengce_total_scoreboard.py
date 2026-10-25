#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math
from collections import defaultdict
from pathlib import Path

CAP=25.0
FACT={'NATIVE_ENTRY_SIGNAL':1.0,'WATCH_ONLY':0.5,'ENTRY_BLOCKED':0.25,'INVALID_OR_MISSING':0.0}

def read(p): return json.loads(Path(p).read_text(encoding='utf-8')) if Path(p).is_file() else None

def latest_prices(path):
    by={}; maxd=None
    if not Path(path).is_file(): return {},None
    with open(path,encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            d=r.get('date'); t=r.get('ticker')
            if not d or not t: continue
            if maxd is None or d>maxd: maxd=d; by={}
            if d==maxd:
                try: px=float(r['close'].replace(',',''))
                except Exception: px=None
                by[t]={'name':r.get('name',''),'close':px}
    return by,maxd

def contribution(family,rank,state,ticker,name='',detail=None):
    return {'family':family,'rank':rank,'state':state,'points':CAP/math.sqrt(rank)*FACT[state],'ticker':ticker,'name':name,'detail':detail or {}}

def build(q,e,v,w,prices,price_date):
    cs=[]
    qok=isinstance(q,dict) and str(q.get('binding_status')).upper()=='PASS'
    qstate='ENTRY_BLOCKED' if qok else 'INVALID_OR_MISSING'
    for i,r in enumerate((q or {}).get('top3') or [],1):
        if isinstance(r,dict) and r.get('ticker'): cs.append(contribution('Q017_CANONICAL_FAMILY',i,qstate,str(r['ticker']),r.get('name',''),{'market_state':q.get('market_state'),'qualified':r.get('qualified')}))
    if isinstance(e,dict) and isinstance(e.get('top1'),dict) and e['top1'].get('ticker'):
        entry=str(e.get('engine_status')).upper()=='ON' and str(e.get('action')).upper() not in {'OFF','ABSTAIN',''}
        state='NATIVE_ENTRY_SIGNAL' if entry else ('ENTRY_BLOCKED' if str(e.get('binding_status')).upper()=='PASS' else 'INVALID_OR_MISSING')
        r=e['top1']; cs.append(contribution('E2_PROFIT_MAX_FAMILY',1,state,str(r['ticker']),r.get('name',''),{'engine_status':e.get('engine_status'),'action':e.get('action')}))
    if isinstance(v,dict):
        sched=v.get('schedule') if isinstance(v.get('schedule'),dict) else {}; active=bool(sched.get('today_is_frozen_schedule_signal'))
        state='NATIVE_ENTRY_SIGNAL' if active else ('WATCH_ONLY' if str(v.get('status')).upper()=='PASS' else 'INVALID_OR_MISSING')
        for i,r in enumerate(((v.get('screen') or {}).get('top3') or []),1):
            if isinstance(r,dict) and r.get('ticker'): cs.append(contribution('V43_FAMILY',i,state,str(r['ticker']),r.get('name',''),{'schedule_signal':active,'score':r.get('score')}))
    if isinstance(w,dict):
        gate=bool(((w.get('economic_gate_40bp') or {}).get('pass')))
        state='NATIVE_ENTRY_SIGNAL' if gate else ('ENTRY_BLOCKED' if str(w.get('status','')).startswith('PASS') else 'INVALID_OR_MISSING')
        for i,r in enumerate(w.get('top20') or [],1):
            if isinstance(r,dict) and r.get('ticker'): cs.append(contribution('NEXTDAY_FAMILY',i,state,str(r['ticker']),r.get('name',''),{'frontier':'W1','40bp_gate':gate}))
    agg=defaultdict(lambda:{'score':0.0,'families':[],'name':''})
    for c in cs:
        a=agg[c['ticker']]; a['score']+=c['points']; a['families'].append(c); a['name']=a['name'] or c['name'] or prices.get(c['ticker'],{}).get('name','')
    rows=[]
    for t,a in agg.items():
        active=[x for x in a['families'] if x['state']=='NATIVE_ENTRY_SIGNAL']
        rows.append({'ticker':t,'name':a['name'],'score':a['score'],'consensus_count':len(a['families']),'families':a['families'],
                     'reference_price':prices.get(t,{}).get('close'),'reference_price_date':price_date,
                     'native_entry_family':[x['family'] for x in active],
                     'action_state':'NATIVE_ENTRY_PRESENT_RESEARCH_OR_CANONICAL_LAYER_CHECK_REQUIRED' if active else 'NO_NATIVE_ENTRY_FROM_SCORED_FAMILIES'})
    rows.sort(key=lambda r:(-r['score'],-r['consensus_count'],r['ticker']))
    last=None; rank=0
    for i,r in enumerate(rows,1):
        key=round(r['score'],12)
        if last is None or key!=last: rank=i; last=key
        r['rank']=rank; r['score']=round(r['score'],4)
    leader=rows[0] if rows else None
    conditional={}
    if leader and leader['families']:
        fam=leader['families'][0]['family']
        conditional={
          'V43_FAMILY':{'buy_rule':'NEXT_TWSE_OPEN only if frozen H20 schedule selects the signal','hold_rule':'about 20 TWSE sessions under frozen H20 schedule','exit_rule':'native H20 schedule close; no fixed target price'},
          'NEXTDAY_FAMILY':{'buy_rule':'t+1 close after signal t close, only after registered 40bp gate/prospective requirements pass','hold_rule':'overnight from t+1 close to t+2 open','exit_rule':'t+2 open; no fixed target price'},
          'E2_PROFIT_MAX_FAMILY':{'buy_rule':'use E2_PROFIT_MAX native entry state only when engine/action is active','hold_rule':'native E2 successor holding rule from its active lock','exit_rule':'native E2 successor exit rule; no fabricated target'},
          'Q017_CANONICAL_FAMILY':{'buy_rule':'use formal applicable Q017/unified HENGCE action authority only','hold_rule':'use applicable Q017 contract only; scoreboard cannot choose between schema-v5 review and unified H20 semantics','exit_rule':'use formal applicable Q017/unified HENGCE exit rule only'},
        }.get(fam,{})
    action_card={'status':'NO_BUY' if not leader or not leader['native_entry_family'] else 'NATIVE_ENTRY_PRESENT_REQUIRES_FORMAL_ACTION_BOARD_CONFIRMATION',
                 'ticker':leader['ticker'] if leader else None,'name':leader['name'] if leader else None,
                 'reference_price':leader['reference_price'] if leader else None,'reference_price_date':price_date,
                 'buy_price':None,'sell_price':None,'buy_rule':None,'hold_rule':None,'exit_rule':None,
                 'conditional_if_native_lane_activates':conditional}
    lane_asof={'q017':(q or {}).get('trade_date'),'e2':(e or {}).get('signal_asof'),'v43':((v or {}).get('screen') or {}).get('signal_date'),'w1':(w or {}).get('signal_date')}
    dates={d for d in lane_asof.values() if d}
    return {'schema_version':2,'system':'HENGCE','module':'HENGCE_TOTAL_SCOREBOARD','score_policy':'HENGCE_ATTENTION_SCORE_V1','lane_asof':lane_asof,'asof_signal_date':next(iter(dates)) if len(dates)==1 else None,
            'authority':{'display_only_meta_analysis':True,'capital_authority_twd':0,'broker_order_execution':False,'can_upgrade_entry_trigger':False},
            'family_alias_resolution':{'NEXTDAY_FAMILY':'canonical family id','W1_NEXTDAY_FAMILY':'deprecated contract alias; never a second capacity'},
            'price_reference':{'date':price_date,'role':'REFERENCE_ONLY_NOT_AUTOMATIC_BUY_PRICE'},
            'attention_leader':leader,'action_card':action_card,'top10':rows[:10],'rows':rows,
            'guards':['Attention score is not trade authority.','Family capacity is never reallocated when a lane is missing.','Within NEXTDAY family a ticker can receive at most one 25-point family capacity; W1 is current registered frontier.','Resonance contributes zero points.','Buy/hold/exit must come from native active lane, never from attention score.']}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--q017-json',type=Path,required=True);ap.add_argument('--e2-json',type=Path,required=True);ap.add_argument('--v43-json',type=Path,required=True);ap.add_argument('--w1-json',type=Path,required=True);ap.add_argument('--price-history',type=Path,required=True);ap.add_argument('--out',type=Path)
    a=ap.parse_args(); prices,d=latest_prices(a.price_history); out=build(read(a.q017_json),read(a.e2_json),read(a.v43_json),read(a.w1_json),prices,d); text=json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(text,encoding='utf-8')
    print(text,end='')
if __name__=='__main__':main()
