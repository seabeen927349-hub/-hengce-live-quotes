#!/usr/bin/env python3
import csv,json,math
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'rank_switch_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.0;COST=.004;HOLD=10;SHOCK=-.02;SOX5=-.04;RESMAX=.04

def f(x):
    try:return float(str(x).replace(',','').strip())
    except:return None
sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
    c=f(r['close']);
    if c is not None:sox.append((r['date'],c))
sox.sort();sd=[d for d,_ in sox];sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
    z=[u for u in sd if u<d];return z[-1] if z else None
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
    o=f(r['open']);c=f(r['close'])
    if o is None or c is None:continue
    x={'date':r['date'],'ticker':r['ticker'],'name':r['name'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
idx={t:{r['date']:i for i,r in enumerate(rs)} for t,rs in by_t.items()}
aligned={d:sret.get(prevus(d)) for d in by_d}
beta={};prevc={}
for t,rs in by_t.items():
    obs=[];pc=None
    for r in rs:
        prevc[(r['date'],t)]=pc
        if pc and aligned.get(r['date']) is not None:
            tr=r['close']/pc-1
            if len(obs)>=30:
                z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
                beta[(r['date'],t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
            obs.append((aligned[r['date']],tr))
        pc=r['close']
feat={}
for d in sorted(by_d):
    u=prevus(d);sh=aligned.get(d)
    if not u or sh is None:continue
    ui=sd.index(u);r5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None
    feat[d]={'shock':sh,'sox5':r5}

def candidates(d):
    ft=feat.get(d)
    if not ft or ft['shock']>SHOCK or ft['sox5'] is None or ft['sox5']>SOX5:return []
    out=[]
    for r in by_d[d]:
        b=beta.get((d,r['ticker']));pc=prevc.get((d,r['ticker']))
        if b is None or not pc:continue
        gap=r['open']/pc-1;exp=b*ft['shock'];res=gap-exp
        if res<=RESMAX:
            out.append({'ticker':r['ticker'],'name':r['name'],'beta':b,'resid':res,'gap':gap,'expected':exp,'open':r['open']})
    return out

def score(c,kind):
    if kind=='beta':return c['beta']
    if kind=='beta_resid_penalty':return c['beta']-5*max(c['resid'],0)
    if kind=='beta_resid_penalty10':return c['beta']-10*max(c['resid'],0)
    if kind=='beta_overshoot_bonus':return c['beta']+5*max(-c['resid'],0)
    if kind=='resid_low':return -c['resid']
    if kind=='beta_x_overshoot':return c['beta']*(1+5*max(-c['resid'],0))
    raise ValueError(kind)

def pick(d,kind):
    cs=candidates(d);return max(cs,key=lambda c:score(c,kind)) if cs else None

def fixed(kind):
    cap=START;busy='';ev=[]
    for d in sorted(by_d):
        if busy and d<=busy:continue
        c=pick(d,kind)
        if not c:continue
        i=idx[c['ticker']][d];j=i+HOLD-1
        if j>=len(by_t[c['ticker']]):continue
        ex=by_t[c['ticker']][j];ret=ex['close']/c['open']-1-COST;cap*=1+ret;busy=ex['date']
        ev.append({'entry':d,'exit':busy,'ticker':c['ticker'],'ret':ret,'capital':cap,'beta':c['beta'],'resid':c['resid']})
    return cap,ev

def switch(kind,ratio,min_age):
    # all-in one position; candidate at today's open can replace current at same open if sufficiently stronger
    cash=START;pos=None;ev=[];dates=sorted(by_d)
    for d in dates:
        if pos:
            rs=by_t[pos['ticker']];ii=idx[pos['ticker']].get(d)
            if ii is None:continue
            age=ii-pos['entry_idx']+1
            cand=pick(d,kind)
            if cand and age>=min_age and cand['ticker']!=pos['ticker'] and score(cand,kind)>=score(pos['entry_candidate'],kind)*ratio:
                px=rs[ii]['open'];ret=px/pos['entry_price']-1-COST;cash*=1+ret
                ev.append({'entry':pos['entry_date'],'exit':d,'ticker':pos['ticker'],'ret':ret,'capital':cash,'reason':'SWITCH'})
                newi=idx[cand['ticker']][d];pos={'ticker':cand['ticker'],'entry_date':d,'entry_idx':newi,'entry_price':cand['open'],'entry_candidate':cand}
                continue
            if age>=HOLD:
                px=rs[ii]['close'];ret=px/pos['entry_price']-1-COST;cash*=1+ret
                ev.append({'entry':pos['entry_date'],'exit':d,'ticker':pos['ticker'],'ret':ret,'capital':cash,'reason':'D10'})
                pos=None
        if pos is None:
            cand=pick(d,kind)
            if cand:
                ii=idx[cand['ticker']][d];pos={'ticker':cand['ticker'],'entry_date':d,'entry_idx':ii,'entry_price':cand['open'],'entry_candidate':cand}
    # value open position at last close with cost for comparability
    if pos:
        r=by_t[pos['ticker']][-1];ret=r['close']/pos['entry_price']-1-COST;cash*=1+ret;ev.append({'entry':pos['entry_date'],'exit':r['date'],'ticker':pos['ticker'],'ret':ret,'capital':cash,'reason':'END'})
    return cash,ev

kinds=['beta','beta_resid_penalty','beta_resid_penalty10','beta_overshoot_bonus','resid_low','beta_x_overshoot']
rows=[];details={}
for k in kinds:
    cap,ev=fixed(k);key=f'FIXED|{k}';rows.append({'mode':'FIXED','rank':k,'switch_ratio':'','min_age':'','final':cap,'ret':cap/START-1,'n':len(ev),'wins':sum(x['ret']>0 for x in ev)});details[key]=ev
    for ratio in (1.0,1.05,1.10,1.20,1.30):
      for ma in (1,3,5,7):
        cap,ev=switch(k,ratio,ma);key=f'SWITCH|{k}|{ratio}|{ma}';rows.append({'mode':'SWITCH','rank':k,'switch_ratio':ratio,'min_age':ma,'final':cap,'ret':cap/START-1,'n':len(ev),'wins':sum(x['ret']>0 for x in ev)});details[key]=ev
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0]
key=f"{best['mode']}|{best['rank']}" if best['mode']=='FIXED' else f"SWITCH|{best['rank']}|{best['switch_ratio']}|{best['min_age']}"
summary={'objective':'maximize 2026 final capital; fixed market gate; compare candidate rank and live-feasible switch policies','tested':len(rows),'best':best,'top20':rows[:20],'best_events':details[key]}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'grid.csv').open('w',newline='',encoding='utf-8') as f0:
    w=csv.DictWriter(f0,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
