#!/usr/bin/env python3
import csv,json,math,time,requests,re
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics'); ARC=ROOT/'archive_2026'; OUT=ROOT/'chip_teacher_combo_screen_2026'; CACHE=OUT/'cache'; OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
START=2_000_000.; COST=.006; XS=.002; RESMAX=.04; K=25.
UA={'User-Agent':'Mozilla/5.0 HENGCE-Q017-CHIP-TEACHER/1.0','Referer':'https://www.twse.com.tw/','Accept':'application/json'}
INST='https://www.twse.com.tw/rwd/zh/fund/T86'; MARGIN='https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN'

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

def getj(url,params):
 last=None
 for a in range(6):
  try:
   r=requests.get(url,params=params,headers=UA,timeout=(8,35))
   if r.status_code==200:
    j=r.json()
    if str(j.get('stat'))=='OK':return j
    last=f"STAT:{j.get('stat')}"
   else:last=f'HTTP:{r.status_code}'
  except Exception as e:last=repr(e)
  time.sleep(min(15,1.5*(2**a)))
 raise RuntimeError(f'FETCH_FAIL {url} {params} {last}')

def parse_inst(j):
 fs=j.get('fields') or []; data=j.get('data') or j.get('records') or []
 if not data:
  for t in j.get('tables') or []:
   x=t.get('fields') or []
   if '證券代號' in x and any('外陸資買賣超股數' in str(y) for y in x):fs=x;data=t.get('data') or t.get('records') or [];break
 idx={str(v):i for i,v in enumerate(fs)}
 def val(row,exact=None,contains=None):
  if exact in idx and idx[exact]<len(row):return f(row[idx[exact]]) or 0.0
  if contains:
   for k,i in idx.items():
    if contains in k and i<len(row):return f(row[i]) or 0.0
  return 0.0
 out={}
 for row in data:
  t=str(row[idx.get('證券代號',0)]).replace('=','').replace('"','').strip() if row else ''
  if re.fullmatch(r'[1-9]\d{3}',t):
   out[t]={'foreign':val(row,contains='外陸資買賣超股數(不含外資自營商)'),'trust':val(row,exact='投信買賣超股數')}
 return out

def parse_margin(j):
 cands=[]
 if isinstance(j.get('tables'),list):cands+=j['tables']
 if isinstance(j.get('fields'),list) and isinstance(j.get('data'),list):cands.append({'fields':j['fields'],'data':j['data']})
 for k,v in j.items():
  m=re.fullmatch(r'fields(\d+)',str(k))
  if m and isinstance(v,list) and isinstance(j.get('data'+m.group(1)),list):cands.append({'fields':v,'data':j['data'+m.group(1)]})
 mt=None
 for x in cands:
  fs=[str(y).replace(' ','') for y in x.get('fields') or []]; data=x.get('data') or x.get('records') or []
  if len(fs)>=15 and len(data)>=400 and any('現金償還' in y for y in fs) and any('現券償還' in y for y in fs):mt=data;break
 if mt is None:raise RuntimeError('MARGIN_TABLE_NOT_FOUND')
 out={}
 for row in mt:
  if not isinstance(row,(list,tuple)) or len(row)<7:continue
  t=str(row[0]).replace('=','').replace('"','').strip()
  if re.fullmatch(r'[1-9]\d{3}',t):out[t]=f(row[6])
 return out

def chip_day(d):
 p=CACHE/f'{d}.json'
 if p.exists():return json.loads(p.read_text(encoding='utf-8'))
 ds=d.replace('-','')
 a=parse_inst(getj(INST,{'date':ds,'selectType':'ALLBUT0999','response':'json'}));time.sleep(.12)
 b=parse_margin(getj(MARGIN,{'date':ds,'selectType':'ALL','response':'json'}));time.sleep(.12)
 obj={'date':d,'inst':a,'margin':b};p.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8');return obj

# market and stock history
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

# Only chip dates needed by current validated market gate, prior 10 Taiwan sessions + one extra for margin delta.
gates=[]
for d in md:
 x=feat.get(d)
 if x and x['shock']<=0 and x['sox5'] is not None and x['sox5']<=-.03 and x['dxy5'] is not None and x['dxy5']>=-.005:gates.append(d)
need=set()
for d in gates:
 i=mi[d]
 for j in range(max(0,i-11),i):need.add(md[j])
print(f'gate_dates={len(gates)} chip_dates={len(need)}',flush=True)
chips={}
for n,d in enumerate(sorted(need),1):
 chips[d]=chip_day(d)
 if n%10==0:print(f'chip_download {n}/{len(need)}',flush=True)

# strict prior features ending d-1
windows=(1,3,5,10)
def chip_features(d,t):
 i=mi[d]; prior=md[max(0,i-11):i]; out={}
 for w in windows:
  ds=prior[-w:]
  out[f'f{w}']=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('foreign',0) for x in ds)
  out[f't{w}']=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('trust',0) for x in ds)
  bals=[chips.get(x,{}).get('margin',{}).get(t) for x in prior[-(w+1):]]
  bals=[x for x in bals if x is not None]
  out[f'm{w}']=(bals[-1]-bals[0]) if len(bals)>=2 else None
 return out

cand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:a.append({'ticker':t,'open':r['open'],'beta':b,'resid':res,'score':b*(1+K*max(-res,0)),'chip':chip_features(d,t) if d in gates else {}})
 cand[d]=sorted(a,key=lambda x:x['score'],reverse=True)

def signok(v,s):
 if v is None:return False
 return v>0 if s=='pos' else v<0 if s=='neg' else v>=0 if s=='nonneg' else v<=0

def passes(x,spec):
 if spec['kind']=='none':return True
 c=x['chip'];fw=spec['fw'];tw=spec['tw'];mw=spec['mw'];fs=spec['fs'];ts=spec['ts'];ms=spec['ms']
 return signok(c.get(f'f{fw}'),fs) and signok(c.get(f't{tw}'),ts) and signok(c.get(f'm{mw}'),ms)

def run(spec):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  z=[x for x in cand.get(d,[]) if passes(x,spec)]
  if not z:continue
  x=z[0];t=x['ticker'];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp={r['date']:r['close'] for r in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/x['open']-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'chip':x['chip'],'beta':x['beta'],'resid':x['resid']})
 return cap,curve

specs=[{'kind':'none'}]
# Core teacher relationships only: institutions buy/sell + margin opposite/same, across 1/3/5/10d windows.
for fw in windows:
 for tw in windows:
  for mw in windows:
   for fs,ts,ms,label in [
    ('pos','pos','neg','foreign+trust buy / margin down'),
    ('pos','pos','pos','foreign+trust buy / margin up'),
    ('pos','neg','neg','foreign buy / trust sell / margin down'),
    ('neg','pos','neg','trust buy / foreign sell / margin down'),
    ('pos','neg','pos','foreign buy / trust sell / margin up'),
    ('neg','pos','pos','trust buy / foreign sell / margin up')]:
     specs.append({'kind':'triple','fw':fw,'tw':tw,'mw':mw,'fs':fs,'ts':ts,'ms':ms,'label':label})
# Turnaround teachers: most recent day buying after 5d net selling; margin falling.
for who in ('foreign','trust'):
 specs.append({'kind':'turn','who':who})

def passes_turn(x,spec):
 c=x['chip'];who=spec['who'];p='f' if who=='foreign' else 't'
 return c.get(p+'1',0)>0 and c.get(p+'5',0)<=0 and c.get('m5') is not None and c['m5']<0
# override
oldpasses=passes
def passes(x,spec):
 if spec['kind']=='turn':return passes_turn(x,spec)
 return oldpasses(x,spec)

rows=[];details={}
for idx,s in enumerate(specs):
 cap,curve=run(s);key=str(idx);details[key]=curve;rows.append({'idx':idx,'spec':s,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(e['net']>0 for e in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['spec']['kind']=='none')
# robust family summary: same sign relationship, neighboring windows that land within 95% of family best
family=best['spec'].get('label',best['spec'].get('kind'))
fam=[x for x in rows if x['spec'].get('label',x['spec'].get('kind'))==family]
out={'objective':'learn only from foreign, investment trust, and margin relationships; no timing optimization','market_gate':'SOX1<=0, SOX5<=-3%, DXY5>=-0.5%','baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'best_family':family,'family_count':len(fam),'family_within95pct_best':sum(x['final']>=.95*best['final'] for x in fam),'top30':rows[:30],'best_curve':details[str(best['idx'])],'data':{'gate_dates':gates,'downloaded_chip_dates':len(need),'source_inst':INST,'source_margin':MARGIN}}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
