#!/usr/bin/env python3
import csv,json,math
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';CACHE=ROOT/'chip_teacher_combo_screen_2026'/'cache';OUT=ROOT/'chip_teacher_intensity_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
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
 o=f(r['open']);c=f(r['close']);v=f(r.get('volume_shares'))
 if o is None or c is None:continue
 x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c,'vol':v or 0};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
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
# convenience maps for stock volume by date
volmap={(r['date'],t):r['vol'] for t,rs in by_t.items() for r in rs}
windows=(1,3,5,10)
def teach(d,t,w):
 i=mi[d];ds=md[max(0,i-w):i];prevds=md[max(0,i-w-1):i]
 F=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('foreign',0) for x in ds)
 T=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('trust',0) for x in ds)
 V=sum(volmap.get((x,t),0) for x in ds)
 bals=[chips.get(x,{}).get('margin',{}).get(t) for x in prevds];bals=[x for x in bals if x is not None]
 M=(bals[-1]-bals[0]) if len(bals)>=2 else None;mbase=bals[0] if bals and bals[0] not in (None,0) else None
 # normalized: net institutional shares / traded shares, margin percentage change. Positive unwind means margin fell.
 return {'F':F/V if V>0 else 0,'T':T/V if V>0 else 0,'M':(-M/mbase) if M is not None and mbase else 0,
         'Fc':sum(1 for x in ds if ((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('foreign',0)>0)),
         'Tc':sum(1 for x in ds if ((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('trust',0)>0))}
cand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:a.append({'ticker':t,'open':r['open'],'beta':b,'resid':res,'base':b*(1+K*max(-res,0))})
 cand[d]=sorted(a,key=lambda x:x['base'],reverse=True)

def teacher_score(q,formula):
 F,T,M,Fc,Tc=q['F'],q['T'],q['M'],q['Fc'],q['Tc']
 if formula=='consensus':return F+T+M
 if formula=='foreign_margin':return F+M
 if formula=='trust_margin':return T+M
 if formula=='trust_absorbs_foreign':return T-F+M
 if formula=='institution_margin':return max(F,T)+M
 if formula=='both_institution':return F+T
 if formula=='consecutive_consensus':return Fc+Tc+2*M
 return 0

def choose(d,N,w,formula,mode):
 z=[dict(x,teacher=teach(d,x['ticker'],w)) for x in cand.get(d,[])[:N]]
 if not z:return None
 if mode=='base':return z[0]
 # rank normalized teacher behavior only inside already-good baseline candidates; tie => baseline order.
 best=max(enumerate(z),key=lambda p:(teacher_score(p[1]['teacher'],formula),-p[0]))[1]
 if mode=='positive_only' and teacher_score(best['teacher'],formula)<=0:return z[0]
 return best

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
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'teacher':x['teacher'],'base':x['base']})
 return cap,curve
formulas=['consensus','foreign_margin','trust_margin','trust_absorbs_foreign','institution_margin','both_institution','consecutive_consensus']
rows=[];details={};idx=0
base={'N':1,'w':5,'formula':'consensus','mode':'base'};cap,curve=run(base);rows.append({'idx':idx,'spec':base,'final':cap,'events':len(curve),'wins':sum(x['net']>0 for x in curve)});details[str(idx)]=curve;idx+=1
for N in (3,5,10):
 for w in windows:
  for formula in formulas:
   for mode in ('teacher_first','positive_only'):
    s={'N':N,'w':w,'formula':formula,'mode':mode};cap,curve=run(s);rows.append({'idx':idx,'spec':s,'final':cap,'events':len(curve),'wins':sum(x['net']>0 for x in curve)});details[str(idx)]=curve;idx+=1
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['spec']['mode']=='base');fam=[x for x in rows if x['spec'].get('formula')==best['spec'].get('formula') and x['spec'].get('N')==best['spec'].get('N') and x['spec'].get('mode')==best['spec'].get('mode')]
out={'objective':'rank only by normalized foreign/trust/margin intensity inside baseline TopN; no other factor and no timing optimization','baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'family_count':len(fam),'family_within95pct':sum(x['final']>=.95*best['final'] for x in fam),'top30':rows[:30],'best_curve':details[str(best['idx'])]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
