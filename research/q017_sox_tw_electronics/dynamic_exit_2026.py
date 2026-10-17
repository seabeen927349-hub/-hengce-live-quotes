#!/usr/bin/env python3
import csv,json,math
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics')
ARC=ROOT/'archive_2026'; OUT=ROOT/'dynamic_exit_2026'; OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.0; COST=.004

def f(x):
    try:return float(str(x).replace(',','').strip())
    except:return None

# SOX
sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
    c=f(r['close'])
    if c is not None:sox.append((r['date'],c))
sox.sort(); sd=[d for d,_ in sox]
sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
    z=[u for u in sd if u<d];return z[-1] if z else None

# TW electronics panel
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
    o=f(r['open']);c=f(r['close'])
    if o is None or c is None:continue
    x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c}
    by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
aligned={d:sret.get(prevus(d)) for d in by_d}

# PIT beta
beta={};prevc={};idx={}
for t,rs in by_t.items():
    idx[t]={r['date']:i for i,r in enumerate(rs)};obs=[];pc=None
    for r in rs:
        prevc[(r['date'],t)]=pc
        if pc and aligned.get(r['date']) is not None:
            tr=r['close']/pc-1
            if len(obs)>=30:
                z=obs[-60:];mx=sum(x for x,y in z)/len(z);my=sum(y for x,y in z)/len(z);vv=sum((x-mx)**2 for x,y in z)
                beta[(r['date'],t)]=sum((x-mx)*(y-my) for x,y in z)/vv if vv else 0
            obs.append((aligned[r['date']],tr))
        pc=r['close']

feat={}
for d in sorted(by_d):
    u=prevus(d);sh=aligned.get(d)
    if not u or sh is None:continue
    ui=sd.index(u);r5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None
    feat[d]={'shock':sh,'sox5':r5}

# fixed strongest entry family from prior screen
SHOCK_MAX=-.02; SOX5_MAX=-.04; RESID_MAX=.04

def pick(d):
    ft=feat.get(d)
    if not ft or ft['shock']>SHOCK_MAX or ft['sox5'] is None or ft['sox5']>SOX5_MAX:return None
    cs=[]
    for r in by_d[d]:
        b=beta.get((d,r['ticker']));pc=prevc.get((d,r['ticker']))
        if b is None or not pc:continue
        res=r['open']/pc-1-b*ft['shock']
        if res<=RESID_MAX:cs.append((b,res,r))
    return max(cs,key=lambda x:x[0]) if cs else None

def exit_trade(ticker,entry_date,rule):
    rs=by_t[ticker];i=idx[ticker][entry_date];entry=rs[i]['open']
    max_close=rs[i]['close']
    # inspect end-of-day information; if triggered, execute next day's open. max_hold exits on that day's close.
    for age in range(1, min(rule['max_hold'],len(rs)-i)):
        j=i+age-1; row=rs[j]; c=row['close'];max_close=max(max_close,c)
        days=age
        # SOX recovery is known at that TW open; can exit same-day open once min_day met
        if days>=rule['min_day'] and rule['sox_recover'] is not None:
            ft=feat.get(row['date'])
            if ft and ft['sox5'] is not None and ft['sox5']>=rule['sox_recover']:
                ret=row['open']/entry-1-COST
                return row['date'],ret,'SOX_RECOVER'
        # close-based rules -> next open
        trigger=None
        if days>=rule['min_day']:
            if rule['trail'] is not None and c/max_close-1<=-rule['trail']:trigger='TRAIL'
            if rule['mom3'] and j-i>=2:
                c3=rs[j-2]['close']
                if c/c3-1<0:trigger=trigger or 'MOM3_NEG'
            if rule['sma3'] and j-i>=2:
                sma=sum(rs[k]['close'] for k in range(j-2,j+1))/3
                if c<sma:trigger=trigger or 'BELOW_SMA3'
            if rule['take'] is not None and c/entry-1>=rule['take']:trigger=trigger or 'TAKE_PROFIT'
        if trigger and j+1<len(rs):
            ret=rs[j+1]['open']/entry-1-COST
            return rs[j+1]['date'],ret,trigger
        if days>=rule['max_hold']:
            ret=c/entry-1-COST
            return row['date'],ret,'MAX_HOLD'
    # fallback last available close
    row=rs[-1];return row['date'],row['close']/entry-1-COST,'END_DATA'

def run(rule):
    cap=START;busy='';ev=[]
    for d in sorted(by_d):
        if busy and d<=busy:continue
        p=pick(d)
        if not p:continue
        b,res,r=p;xd,ret,reason=exit_trade(r['ticker'],d,rule);cap*=1+ret;busy=xd
        ev.append({'entry':d,'exit':xd,'ticker':r['ticker'],'ret':ret,'capital':cap,'reason':reason,'beta':b,'resid':res,'shock':feat[d]['shock'],'sox5':feat[d]['sox5']})
    return {'final':cap,'ret':cap/START-1,'n':len(ev),'wins':sum(e['ret']>0 for e in ev),'events':ev}

rules=[]
# fixed controls 7..15
for h in range(7,16):
    rules.append({'name':f'FIXED_{h}','min_day':h,'max_hold':h,'trail':None,'mom3':False,'sma3':False,'take':None,'sox_recover':None})
# dynamic families: finite interpretable grid
for min_day in (5,7,9):
 for max_hold in (10,12,15,20):
  for trail in (None,.05,.08,.10,.12):
   for mom3 in (False,True):
    for take in (None,.15,.20,.25,.30):
     rules.append({'name':'DYN','min_day':min_day,'max_hold':max_hold,'trail':trail,'mom3':mom3,'sma3':False,'take':take,'sox_recover':None})
# external recovery exits, independent family
for min_day in (5,7,9):
 for max_hold in (10,12,15,20):
  for sr in (-.02,-.01,0,.01):
   rules.append({'name':'SOXREC','min_day':min_day,'max_hold':max_hold,'trail':None,'mom3':False,'sma3':False,'take':None,'sox_recover':sr})

rows=[];detail={}
for n,rule in enumerate(rules):
    r=run(rule);rid=n
    row={**rule,'rule_id':rid,'final':r['final'],'ret':r['ret'],'n':r['n'],'wins':r['wins'],'win_rate':r['wins']/r['n'] if r['n'] else 0}
    rows.append(row);detail[rid]=r['events']
rows.sort(key=lambda x:x['final'],reverse=True)
best=rows[0]
summary={'objective':'maximize 2026 final capital; dynamic exits use only info known by execution time','tested':len(rows),'best':best,'best20':rows[:20],'best_events':detail[best['rule_id']]}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'grid.csv').open('w',newline='',encoding='utf-8') as f0:
    fields=list(rows[0].keys());w=csv.DictWriter(f0,fieldnames=fields);w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
