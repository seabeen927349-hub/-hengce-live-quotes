#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';SRC=ROOT/'fixed_clock_selection_2026'/'summary.json';OUT=ROOT/'d10_runner_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.006

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
by_t=defaultdict(dict);dates=set()
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 c=f(r['close']);d=r['date'];t=r['ticker'];dates.add(d)
 if c is not None:by_t[t][d]=c
md=sorted(dates);di={d:i for i,d in enumerate(md)}
s=json.loads(SRC.read_text(encoding='utf-8'))
events=[x for x in s['best_curve'] if x.get('ticker')]
base=[]
for e in events:
 d=e['entry'];t=e['ticker'];i=di[d];d9=md[i+8];d10=md[i+9];d12=md[i+11]
 avg=float(e['avg_entry']);deploy=float(e['spent'])/float(e['capital_before']);c9=by_t[t][d9];c10=by_t[t][d10];c12=by_t[t][d12]
 n10=c10/avg-1-COST;n12=c12/avg-1-COST
 base.append({'entry':d,'ticker':t,'avg_entry':avg,'deploy_ratio':deploy,'d9':d9,'d10':d10,'d12':d12,'c9':c9,'c10':c10,'c12':c12,'net10':n10,'net12':n12,'profit10':c10/avg-1,'mom1':c10/c9-1})

def run(name,pred):
 cap=START;curve=[]
 for e in base:
  extend=pred(e);net=e['net12'] if extend else e['net10'];before=cap;cap+=before*e['deploy_ratio']*net
  curve.append({'entry':e['entry'],'ticker':e['ticker'],'extend_to_d12':extend,'net':net,'capital':cap,'profit10':e['profit10'],'mom1':e['mom1']})
 return {'name':name,'final':cap,'ret':cap/START-1,'extended':sum(x['extend_to_d12'] for x in curve),'curve':curve}
rules=[]
rules.append(('BASE_D10',lambda e:False));rules.append(('ALL_D12',lambda e:True));rules.append(('D10_UP_DAY',lambda e:e['mom1']>0));rules.append(('D10_DOWN_DAY',lambda e:e['mom1']<=0))
for th in (0,.03,.05,.08,.10,.15,.20,.25,.30):rules.append((f'PROFIT_GE_{th:.2f}',lambda e,th=th:e['profit10']>=th))
for th in (.03,.05,.08,.10,.15,.20,.25):rules.append((f'PROFIT_LT_{th:.2f}',lambda e,th=th:e['profit10']<th))
rows=[];details={}
for name,p in rules:
 r=run(name,p);details[name]=r['curve'];rows.append({k:v for k,v in r.items() if k!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];baseline=next(x for x in rows if x['name']=='BASE_D10')
out={'objective':'cheap triage only: test whether D10-known state can justify a D12 runner before building full sequence','baseline':baseline,'best':best,'improvement':best['final']-baseline['final'],'grid':rows,'best_curve':details[best['name']],'event_inputs':base}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
