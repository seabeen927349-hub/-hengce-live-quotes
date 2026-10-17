#!/usr/bin/env python3
import csv,json,math
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics'); ARC=ROOT/'archive_2026'; OUT=ROOT/'residual_gate_2026'; OUT.mkdir(parents=True,exist_ok=True)
START_CAP=2_000_000.0; COST=.004

def f(x):
    try:return float(str(x).replace(',','').strip())
    except:return None
# SOX
sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
    c=f(r['close']);
    if c is not None:sox.append((r['date'],c))
sox.sort(); sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}; sdates=[d for d,_ in sox]
def prevus(d):
    z=[x for x in sdates if x<d];return z[-1] if z else None
# stocks
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
    o=f(r['open']);c=f(r['close'])
    if o is None or c is None:continue
    x={'date':r['date'],'ticker':r['ticker'],'name':r['name'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
aligned={d:sret.get(prevus(d)) for d in by_d}
# prior beta and prior close
beta={}; prevclose={}; idx={}
for t,rs in by_t.items():
    idx[t]={r['date']:i for i,r in enumerate(rs)}; obs=[];pc=None
    for r in rs:
        prevclose[(r['date'],t)]=pc
        if pc and aligned.get(r['date']) is not None:
            tr=r['close']/pc-1
            if len(obs)>=30:
                z=obs[-60:];mx=sum(x for x,y in z)/len(z);my=sum(y for x,y in z)/len(z);vv=sum((x-mx)**2 for x,y in z)
                beta[(r['date'],t)]=sum((x-mx)*(y-my) for x,y in z)/vv if vv else 0
            obs.append((aligned[r['date']],tr))
        pc=r['close']
# baseline event candidates fixed: DOWN <= -3%, top5 beta, hold3 nonoverlap
E=[];busy=''
for d in sorted(by_d):
    if busy and d<=busy:continue
    shock=aligned.get(d)
    if shock is None or shock>-.03:continue
    cand=[]
    for r in by_d[d]:
        b=beta.get((d,r['ticker']));pc=prevclose.get((d,r['ticker']))
        if b is None or not pc:continue
        gap=r['open']/pc-1; expected=b*shock; residual=gap-expected
        cand.append((b,r,gap,expected,residual))
    cand=sorted(cand,key=lambda x:x[0],reverse=True)[:5]
    rr=[];exits=[]
    for b,r,g,e,res in cand:
        i=idx[r['ticker']][d];j=i+2
        if j>=len(by_t[r['ticker']]):continue
        ex=by_t[r['ticker']][j];rr.append(ex['close']/r['open']-1-COST);exits.append(ex['date'])
    if not rr:continue
    # external path features known at TW open
    ui=sdates.index(prevus(d)); current=sret.get(sdates[ui]); prev1=sret.get(sdates[ui-1]) if ui>=1 else None
    ret3=sox[ui][1]/sox[max(0,ui-3)][1]-1 if ui>=3 else None
    ret5=sox[ui][1]/sox[max(0,ui-5)][1]-1 if ui>=5 else None
    high20=max(v for _,v in sox[max(0,ui-19):ui+1]); dd20=sox[ui][1]/high20-1
    E.append({'entry':d,'exit':max(exits),'ret':sum(rr)/len(rr),'shock':shock,'sox_prevret':prev1,'sox_ret3':ret3,'sox_ret5':ret5,'sox_dd20':dd20,'beta_mean':sum(x[0] for x in cand)/len(cand),'gap_mean':sum(x[2] for x in cand)/len(cand),'expected_gap_mean':sum(x[3] for x in cand)/len(cand),'residual_mean':sum(x[4] for x in cand)/len(cand),'residual_min':min(x[4] for x in cand),'residual_max':max(x[4] for x in cand)})
    busy=max(exits)

def equity(rows):
    c=START_CAP;pk=c;dd=0;wins=0
    for e in rows:c*=1+e['ret'];pk=max(pk,c);dd=min(dd,c/pk-1);wins+=e['ret']>0
    return {'n':len(rows),'wins':wins,'win_rate':wins/len(rows) if rows else 0,'final':c,'return':c/START_CAP-1,'mdd':dd}
base=equity(E)
# Test only simple one-variable gates around observable values. Each threshold family reported in full; no cherry-picked hidden search.
gates=[]
features=['residual_mean','gap_mean','sox_ret3','sox_ret5','sox_dd20']
for feat in features:
    vals=sorted(e[feat] for e in E if e[feat] is not None)
    # empirical quartiles as diagnostics; both directions
    for q in (.25,.5,.75):
        th=vals[min(len(vals)-1,int((len(vals)-1)*q))]
        for op in ('<=','>='):
            rows=[e for e in E if e[feat] is not None and (e[feat]<=th if op=='<=' else e[feat]>=th)]
            z=equity(rows);gates.append({'feature':feat,'op':op,'threshold':th,**z})
# leave-out winner stress baseline
rets=sorted([e['ret'] for e in E],reverse=True)
def remove_top(k):
    rem=list(E)
    for v in rets[:k]:
        for i,e in enumerate(rem):
            if e['ret']==v:rem.pop(i);break
    return equity(rem)
# costs stress: recompute event return by subtracting incremental cost from fixed .4%
costs={}
for cost in (.004,.006,.008,.01):
    rows=[dict(e,ret=e['ret']-(cost-COST)) for e in E];costs[str(cost)]=equity(rows)
# feature win/loss comparison
comp={}
for feat in ['shock','sox_prevret','sox_ret3','sox_ret5','sox_dd20','beta_mean','gap_mean','expected_gap_mean','residual_mean']:
    w=[e[feat] for e in E if e['ret']>0 and e[feat] is not None];l=[e[feat] for e in E if e['ret']<=0 and e[feat] is not None]
    comp[feat]={'win_mean':sum(w)/len(w) if w else None,'loss_mean':sum(l)/len(l) if l else None}
summary={'baseline':base,'events':E,'win_loss_feature_means':comp,'simple_gates_sorted':sorted(gates,key=lambda x:x['return'],reverse=True),'remove_best':{'top1':remove_top(1),'top3':remove_top(3)},'cost_stress':costs}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'events.csv').open('w',newline='',encoding='utf-8') as f0:
    w=csv.DictWriter(f0,fieldnames=list(E[0].keys()));w.writeheader();w.writerows(E)
print(json.dumps({'baseline':base,'win_loss_feature_means':comp,'top_gates':summary['simple_gates_sorted'][:12],'remove_best':summary['remove_best'],'cost_stress':costs},ensure_ascii=False,indent=2))
