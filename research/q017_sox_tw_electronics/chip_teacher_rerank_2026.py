#!/usr/bin/env python3
import csv,json,re
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics'); ARC=ROOT/'archive_2026'; SRC=ROOT/'chip_teacher_combo_screen_2026'; CACHE=SRC/'cache'; OUT=ROOT/'chip_teacher_rerank_2026'; OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.; COST=.006; XS=.002; RESMAX=.04; K=25.

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None

def load_series(path):
 a=[]
 for r in csv.DictReader(path.open(encoding='utf-8')):
  c=f(r['close'])
  if c is not None:a.append((r['date'],c))
 a.sort();return a

def prev(ds,d):
 z=[u for u in ds if u<d];return z[-1] if z else None

sox=load_series(ARC/'sox_2026.csv');dxy=load_series(ARC/'dxy_2026.csv');sd=[d for d,_ in sox];dd=[d for d,_ in dxy]
sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 o=f(r['open']);c=f(r['close'])
 if o is None or c is None:continue
 x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sret.get(prev(sd,d)) for d in md};beta={};prevc={}
for t,rs in by_t.items():
 obs=[];pc=None
 for r in rs:
  d=r['date'];prevc[(d,t)]=pc;sh=aligned.get(d)
  if pc and sh is not None:
   tr=r['close']/pc-1
   if len(obs)>=30:
    z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
    beta[(d,t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in md:
 us=prev(sd,d);ux=prev(dd,d);sh=sret.get(us)
 if not us or sh is None or not ux:continue
 si=sd.index(us);di=dd.index(ux);s5=sox[si][1]/sox[si-5][1]-1 if si>=5 else None;dx5=dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None
 feat[d]={'shock':sh,'sox5':s5,'dxy5':dx5}

def chip_day(d):
 p=CACHE/f'{d}.json'
 if not p.exists():return {'inst':{},'margin':{}}
 return json.loads(p.read_text(encoding='utf-8'))
chips={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in CACHE.glob('*.json')}
windows=(1,3,5,10)
def chip_features(d,t):
 i=mi[d];prior=md[max(0,i-11):i];out={}
 for w in windows:
  ds=prior[-w:]
  out[f'f{w}']=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('foreign',0) for x in ds)
  out[f't{w}']=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('trust',0) for x in ds)
  bals=[chips.get(x,{}).get('margin',{}).get(t) for x in prior[-(w+1):]];bals=[x for x in bals if x is not None]
  out[f'm{w}']=(bals[-1]-bals[0]) if len(bals)>=2 else None
 return out

def sign(v):return 1 if v is not None and v>0 else -1 if v is not None and v<0 else 0
cand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:a.append({'ticker':t,'open':r['open'],'beta':b,'resid':res,'base':b*(1+K*max(-res,0)),'chip':chip_features(d,t)})
 cand[d]=sorted(a,key=lambda x:x['base'],reverse=True)

def teacher_tuple(c,fw,tw,mw,pattern):
 ch=c['chip'];F=sign(ch.get(f'f{fw}'));T=sign(ch.get(f't{tw}'));M=sign(ch.get(f'm{mw}'))
 # Higher is better. Patterns are simple, interpretable teacher lessons.
 if pattern=='both_buy_margin_down':return (F==1 and T==1 and M==-1, F+T-M)
 if pattern=='trust_buy_foreign_sell_margin_down':return (T==1 and F==-1 and M==-1, T-F-M)
 if pattern=='foreign_buy_trust_sell_margin_down':return (F==1 and T==-1 and M==-1, F-T-M)
 if pattern=='both_buy':return (F==1 and T==1, F+T)
 if pattern=='institution_buy_margin_down':return ((F==1 or T==1) and M==-1, F+T-M)
 if pattern=='consensus_score':return (True, F+T-M)
 return (True,0)

def choose(d,N,fw,tw,mw,pattern,mode):
 z=cand.get(d,[])[:N]
 if not z:return None
 if mode=='fallback_pattern':
  good=[x for x in z if teacher_tuple(x,fw,tw,mw,pattern)[0]]
  return good[0] if good else z[0]
 if mode=='teacher_first':
  return max(z,key=lambda x:(teacher_tuple(x,fw,tw,mw,pattern)[1],x['base']))
 return z[0]

def run(spec):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  x=choose(d,**spec)
  if not x:continue
  t=x['ticker'];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp={r['date']:r['close'] for r in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/x['open']-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'base_rank':next(i+1 for i,q in enumerate(cand[d]) if q['ticker']==t),'chip':x['chip']})
 return cap,curve

patterns=['both_buy_margin_down','trust_buy_foreign_sell_margin_down','foreign_buy_trust_sell_margin_down','both_buy','institution_buy_margin_down','consensus_score']
rows=[];details={};idx=0
base_spec={'N':1,'fw':5,'tw':5,'mw':5,'pattern':'consensus_score','mode':'base'}
cap,curve=run(base_spec);rows.append({'idx':idx,'spec':base_spec,'final':cap,'events':len(curve),'wins':sum(x['net']>0 for x in curve)});details[str(idx)]=curve;idx+=1
for N in (3,5,10):
 for fw in windows:
  for tw in windows:
   for mw in windows:
    for p in patterns:
     for mode in ('fallback_pattern','teacher_first'):
      s={'N':N,'fw':fw,'tw':tw,'mw':mw,'pattern':p,'mode':mode};cap,curve=run(s);rows.append({'idx':idx,'spec':s,'final':cap,'events':len(curve),'wins':sum(x['net']>0 for x in curve)});details[str(idx)]=curve;idx+=1
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['spec']['mode']=='base');fam=[x for x in rows if x['spec'].get('pattern')==best['spec'].get('pattern') and x['spec'].get('mode')==best['spec'].get('mode') and x['spec'].get('N')==best['spec'].get('N')]
out={'objective':'use foreign/trust/margin only to choose within baseline TopN, never as market gate; timing unchanged','baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'best_family_count':len(fam),'best_family_within95pct':sum(x['final']>=.95*best['final'] for x in fam),'top30':rows[:30],'best_curve':details[str(best['idx'])]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
