#!/usr/bin/env python3
import csv,json
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'factor_join_2026';OUT.mkdir(parents=True,exist_ok=True)
def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def load(p):
 a=[]
 for r in csv.DictReader(p.open(encoding='utf-8')):
  c=f(r['close'])
  if c is not None:a.append((r['date'],c))
 a.sort();return a
sox=load(ARC/'sox_2026.csv');dxy=load(ARC/'dxy_2026.csv');sd=[d for d,_ in sox];dd=[d for d,_ in dxy]
sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prev(ds,d):
 z=[u for u in ds if u<d];return z[-1] if z else None
# market dates directly from electronics archive without loading all prices into memory structures
md=[];last=None
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 d=r['date']
 if d!=last:md.append(d);last=d
md=sorted(set(md));rows=[]
for d in md:
 us=prev(sd,d);ux=prev(dd,d)
 if not us or not ux:continue
 si=sd.index(us);di=dd.index(ux)
 if si<5 or di<5:continue
 sh=sret.get(us);s5=sox[si][1]/sox[si-5][1]-1;d5=dxy[di][1]/dxy[di-5][1]-1
 if sh is not None and sh<=0 and s5<=-.03 and d5>=-.005:
  rows.append({'tw_date':d,'us_sox_date':us,'dxy_date':ux,'sox1':sh,'sox5':s5,'dxy5':d5})
(OUT/'gate_dates.json').write_text(json.dumps({'gate':'SOX1<=0, SOX5<=-3%, DXY5>=-0.5%','n':len(rows),'dates':rows},ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'gate_dates.csv').open('w',newline='',encoding='utf-8') as fh:
 w=csv.DictWriter(fh,fieldnames=list(rows[0].keys()) if rows else ['tw_date']);w.writeheader();w.writerows(rows)
print(json.dumps({'n':len(rows),'dates':rows},ensure_ascii=False,indent=2))
