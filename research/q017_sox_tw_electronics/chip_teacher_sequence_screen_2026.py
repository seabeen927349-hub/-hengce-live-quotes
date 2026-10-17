#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';CACHE=ROOT/'chip_teacher_combo_screen_2026'/'cache';OUT=ROOT/'chip_teacher_sequence_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.006;XS=.002;RESMAX=.04;K=25.

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def load(path):
 a=[]
 for r in csv.DictReader(path.open(encoding='utf-8')):
  c=f(r['close'])
  if c is not None:a.append((r['date'],c))
 a.sort();return a
def prev(ds,d):
 z=[u for u in ds if u<d];return z[-1] if z else None
sox=load(ARC/'sox_2026.csv');dxy=load(ARC/'dxy_2026.csv');sd=[d for d,_ in sox];dd=[d for d,_ in dxy]
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
chips={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in CACHE.glob('*.json')}

def dayvals(d,t):
 a=(chips.get(d,{}).get('inst',{}).get(t,{}) or {});m=chips.get(d,{}).get('margin',{}).get(t)
 return a.get('foreign',0),a.get('trust',0),m

def seqfeat(d,t):
 i=mi[d];ds=md[max(0,i-11):i]
 F=[];T=[];M=[]
 for x in ds:
  ff,tt,mm=dayvals(x,t);F.append(ff);T.append(tt);M.append(mm)
 def countpos(a,n):return sum(v>0 for v in a[-n:])
 def countneg(a,n):return sum(v<0 for v in a[-n:])
 def net(a,n):return sum(a[-n:])
 def mdiff(n):
  z=[x for x in M[-(n+1):] if x is not None]
  return (z[-1]-z[0]) if len(z)>=2 else None
 return {'F1':net(F,1),'F3':net(F,3),'F5':net(F,5),'F10':net(F,10),'T1':net(T,1),'T3':net(T,3),'T5':net(T,5),'T10':net(T,10),
         'Fp3':countpos(F,3),'Fn3':countneg(F,3),'Fp5':countpos(F,5),'Fn5':countneg(F,5),'Tp3':countpos(T,3),'Tn3':countneg(T,3),'Tp5':countpos(T,5),'Tn5':countneg(T,5),
         'M1':mdiff(1),'M3':mdiff(3),'M5':mdiff(5),'M10':mdiff(10)}
cand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:a.append({'ticker':t,'open':r['open'],'base':b*(1+K*max(-res,0)),'seq':seqfeat(d,t)})
 cand[d]=sorted(a,key=lambda x:x['base'],reverse=True)

def hit(q,kind):
 s=q['seq']
 if kind=='trust2of3_foreign3sell_margin5down':return s['Tp3']>=2 and s['F3']<0 and s['M5'] is not None and s['M5']<0
 if kind=='trust3of5_foreign5sell_margin5down':return s['Tp5']>=3 and s['F5']<0 and s['M5'] is not None and s['M5']<0
 if kind=='trust3of5_foreign5sell_margin3down':return s['Tp5']>=3 and s['F5']<0 and s['M3'] is not None and s['M3']<0
 if kind=='trust_flip1_foreign5sell_margin5down':return s['T1']>0 and s['T5']<=0 and s['F5']<0 and s['M5'] is not None and s['M5']<0
 if kind=='foreign2of3_trust3sell_margin5down':return s['Fp3']>=2 and s['T3']<0 and s['M5'] is not None and s['M5']<0
 if kind=='both2of3_margin5down':return s['Fp3']>=2 and s['Tp3']>=2 and s['M5'] is not None and s['M5']<0
 if kind=='trust5buy_foreign5sell_margin5down':return s['T5']>0 and s['F5']<0 and s['M5'] is not None and s['M5']<0
 return False

def choose(d,N,kind):
 z=cand.get(d,[])[:N]
 if not z:return None
 if kind=='baseline':return z[0]
 g=[x for x in z if hit(x,kind)]
 return g[0] if g else z[0]
def run(N,kind):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  x=choose(d,N,kind)
  if not x:continue
  t=x['ticker'];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp={r['date']:r['close'] for r in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/x['open']-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'seq':x['seq']})
 return cap,curve
kinds=['baseline','trust2of3_foreign3sell_margin5down','trust3of5_foreign5sell_margin5down','trust3of5_foreign5sell_margin3down','trust_flip1_foreign5sell_margin5down','foreign2of3_trust3sell_margin5down','both2of3_margin5down','trust5buy_foreign5sell_margin5down']
rows=[];details={}
for N in (1,3,5):
 for kind in kinds:
  if kind=='baseline' and N!=1:continue
  cap,curve=run(N,kind);key=f'{N}_{kind}';details[key]=curve;rows.append({'N':N,'kind':kind,'final':cap,'events':len(curve),'wins':sum(x['net']>0 for x in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['kind']=='baseline')
out={'objective':'test only teacher sequence/turnaround patterns: foreign, trust, margin; timing unchanged','baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'grid':rows,'best_curve':details[f"{best['N']}_{best['kind']}"]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
