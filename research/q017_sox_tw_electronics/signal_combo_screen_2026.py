#!/usr/bin/env python3
import csv,json,math
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics'); ARC=ROOT/'archive_2026'; OUT=ROOT/'signal_combo_screen_2026'; OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.; COST=.006; EXIT_SLIP=.002

def f(x):
    try:return float(str(x).replace(',','').strip())
    except:return None

sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
    c=f(r['close'])
    if c is not None:sox.append((r['date'],c))
sox.sort(); sd=[d for d,_ in sox]; sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
    z=[u for u in sd if u<d]; return z[-1] if z else None

by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
    o=f(r.get('open'));c=f(r.get('close'))
    if o is None or c is None:continue
    x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c}
    by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
mdates=sorted(by_d); mi={d:i for i,d in enumerate(mdates)}; aligned={d:sret.get(prevus(d)) for d in mdates}

beta={};prevc={};mom={}
for t,rs in by_t.items():
    obs=[];pc=None
    for i,r in enumerate(rs):
        d=r['date'];prevc[(d,t)]=pc;sh=aligned.get(d)
        for n in (5,10,20):
            if i>=n and rs[i-n]['close']>0:mom[(d,t,n)]=pc/rs[i-n]['close']-1 if pc else None
        if pc and sh is not None:
            tr=r['close']/pc-1
            if len(obs)>=30:
                z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
                beta[(d,t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
            obs.append((sh,tr))
        pc=r['close']

feat={}
for d in mdates:
    u=prevus(d);sh=aligned.get(d)
    if not u or sh is None:continue
    ui=sd.index(u); r5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None
    feat[d]={'shock':sh,'sox5':r5}

cand={}
for d in mdates:
    ft=feat.get(d);lst=[]
    if not ft:continue
    for r in by_d[d]:
        t=r['ticker']; b=beta.get((d,t));pc=prevc.get((d,t))
        if b is None or b<=0 or not pc:continue
        gap=r['open']/pc-1;res=gap-b*ft['shock']
        lst.append({'ticker':t,'open':r['open'],'beta':b,'resid':res,'gap':gap,'m5':mom.get((d,t,5)),'m10':mom.get((d,t,10)),'m20':mom.get((d,t,20))})
    cand[d]=lst

def score(x,k,trend_mode,trend_k):
    s=x['beta']*(1+k*max(-x['resid'],0))
    if trend_mode=='strong5' and x['m5'] is not None:s*=1+trend_k*max(x['m5'],0)
    elif trend_mode=='weak5' and x['m5'] is not None:s*=1+trend_k*max(-x['m5'],0)
    elif trend_mode=='strong20' and x['m20'] is not None:s*=1+trend_k*max(x['m20'],0)
    elif trend_mode=='weak20' and x['m20'] is not None:s*=1+trend_k*max(-x['m20'],0)
    return s

def passes_trend(x,flt,th):
    if flt=='none':return True
    key,side=flt[:-2],flt[-2:]
    v=x.get(key)
    if v is None:return False
    return v>=th if side=='ge' else v<=th

def run(p):
    cap=START;busy=None;curve=[]
    for d in mdates:
        if busy and d<=busy:continue
        ft=feat.get(d)
        if not ft or ft['shock']>p['shock'] or ft['sox5'] is None or ft['sox5']>p['sox5']:continue
        i=mi[d]
        if i+10>=len(mdates):continue
        d9,d10,d11=mdates[i+8],mdates[i+9],mdates[i+10]
        zz=[]
        for x in cand.get(d,[]):
            if x['resid']>p['resmax']:continue
            if not passes_trend(x,p['trend_filter'],p['trend_th']):continue
            zz.append((score(x,p['k'],p['trend_mode'],p['trend_k']),x))
        if not zz:continue
        zz.sort(key=lambda q:q[0],reverse=True);x=zz[0][1];t=x['ticker'];entry=x['open']
        mp={r['date']:r['close'] for r in by_t[t]}
        c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
        if not c9 or not c10 or not c11:continue
        extend=c10>=c9
        xd=d11 if extend else d10;raw=c11 if extend else c10
        net=(raw*(1-EXIT_SLIP))/entry-1-COST
        cap*=1+net;busy=xd
        curve.append({'entry':d,'ticker':t,'exit':xd,'extend':extend,'net':net,'capital':cap,'beta':x['beta'],'resid':x['resid'],'m5':x['m5'],'m20':x['m20']})
    return cap,curve

shock_grid=[0,-.005,-.01,-.015,-.02,-.025,-.03]
sox5_grid=[0,-.01,-.02,-.03,-.04,-.05,-.06]
res_grid=[.06,.05,.04,.03,.02,.01,0,-.01]
k_grid=[0,10,25,50]
trend_modes=[('none',0),('strong5',2),('weak5',2),('strong20',1),('weak20',1)]
trend_filters=[('none',0),('m5ge',0),('m5le',0),('m20ge',0),('m20le',0),('m5ge',.05),('m5le',-.05),('m20ge',.10),('m20le',-.10)]
rows=[]
for sh in shock_grid:
 for s5 in sox5_grid:
  for rg in res_grid:
   for k in k_grid:
    for tm,tk in trend_modes:
     p={'shock':sh,'sox5':s5,'resmax':rg,'k':k,'trend_mode':tm,'trend_k':tk,'trend_filter':'none','trend_th':0}
     final,curve=run(p);rows.append({**p,'final':final,'ret':final/START-1,'events':len(curve),'wins':sum(x['net']>0 for x in curve)})
    if k==25:
     for tf,th in trend_filters[1:]:
      p={'shock':sh,'sox5':s5,'resmax':rg,'k':25,'trend_mode':'none','trend_k':0,'trend_filter':tf,'trend_th':th}
      final,curve=run(p);rows.append({**p,'final':final,'ret':final/START-1,'events':len(curve),'wins':sum(x['net']>0 for x in curve)})
rows.sort(key=lambda x:x['final'],reverse=True)

def neigh(grid,v):
    i=grid.index(v);return grid[max(0,i-1):min(len(grid),i+2)]
def robust(r):
    vals=[]
    for sh in neigh(shock_grid,r['shock']):
     for s5 in neigh(sox5_grid,r['sox5']):
      for rg in neigh(res_grid,r['resmax']):
       for k in neigh(k_grid,r['k']):
        p={**r,'shock':sh,'sox5':s5,'resmax':rg,'k':k};p={x:p[x] for x in ('shock','sox5','resmax','k','trend_mode','trend_k','trend_filter','trend_th')}
        f0,_=run(p);vals.append(f0)
    vals.sort();return {'n':len(vals),'positive':sum(v>START for v in vals),'above90pct_anchor':sum(v>=.9*r['final'] for v in vals),'median':vals[len(vals)//2],'min':vals[0]}

top=[];seen=set()
for r in rows:
    fam=(r['trend_mode'],r['trend_filter'],r['trend_th'])
    if fam in seen:continue
    seen.add(fam);z=dict(r);z['robustness']=robust(r);top.append(z)
    if len(top)>=20:break
best=rows[0];bf,curve=run({k:best[k] for k in ('shock','sox5','resmax','k','trend_mode','trend_k','trend_filter','trend_th')})
out={'objective':'screen only signal/selection combinations; execution timing fixed and not optimized','screening_note':'daily-open screening only; winners must beat current rule materially then pass minute-level causal replay before promotion','tested':len(rows),'best':best,'best20':rows[:20],'best_families':top,'best_curve':curve}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'grid.csv').open('w',newline='',encoding='utf-8') as fh:
    w=csv.DictWriter(fh,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
print(json.dumps(out,ensure_ascii=False,indent=2))
