#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures as cf
import json, math, statistics, time, urllib.parse, urllib.request
from collections import Counter, defaultdict, deque
from pathlib import Path

import research.codex_full_reset_20261023.nextday_o3_delayed_close_overnight as o3

ROOT=Path(__file__).resolve().parents[2]
RESET=ROOT/'research/codex_full_reset_20261023'
OUT=RESET/'nextday_o5_t86_full_model_result.json'
EVENTS=RESET/'nextday_o5_t86_full_model_events.jsonl'
PRIMARY_COST=.002
COSTS=(0.0,.002,.004,.008)
TRAIN=('2023-01-01','2023-12-31'); DEV=o3.DEV; VAL=o3.VAL; DIAG=o3.DIAG
TARGET_COUNTS=(35,45,55)
BINS=5
SMOOTH=30.0
UA='Mozilla/5.0 (compatible; HENGCE-research-o5-full/1.0)'
CHIP_FEATURES=('foreign_rank','trust_rank','dealer_rank','total_rank','foreign_rank3','trust_rank3','total_rank3','sign_breadth','sign_breadth3')
MODEL_FEATURES={
  'CHIP_ONLY':CHIP_FEATURES,
  'PRICE_PLUS_CHIP':('price_score',)+CHIP_FEATURES,
}


def ff(x):
    try:return float(str(x).replace(',','').strip())
    except:return None

def find_table(obj):
    if isinstance(obj,dict):
        f=obj.get('fields'); d=obj.get('data')
        if isinstance(f,list) and isinstance(d,list) and f and f[0]=='證券代號':return f,d
        for v in obj.values():
            z=find_table(v)
            if z:return z
    elif isinstance(obj,list):
        for v in obj:
            z=find_table(v)
            if z:return z
    return None

def fetch_t86(date):
    q=urllib.parse.urlencode({'date':date.replace('-',''),'selectType':'ALL','response':'json'})
    url='https://www.twse.com.tw/rwd/zh/fund/T86?'+q
    last=None
    for attempt in range(5):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=45) as resp:obj=json.loads(resp.read().decode('utf-8-sig'))
            if not isinstance(obj,dict) or obj.get('stat')!='OK':raise RuntimeError(f"stat:{obj.get('stat') if isinstance(obj,dict) else type(obj)}")
            z=find_table(obj)
            if not z:raise RuntimeError('table_not_found')
            fields,data=z; ix={n:i for i,n in enumerate(fields)}
            reqs={
              'foreign_net':'外陸資買賣超股數(不含外資自營商)',
              'trust_net':'投信買賣超股數','dealer_net':'自營商買賣超股數','total_net':'三大法人買賣超股數',
            }
            if any(n not in ix for n in reqs.values()):raise RuntimeError('field_schema_mismatch')
            out={}
            for row in data:
                if not isinstance(row,list) or not row:continue
                t=str(row[0]).strip()
                if not (len(t)==4 and t.isdigit()):continue
                vals={k:ff(row[ix[n]]) for k,n in reqs.items()}
                if all(v is not None for v in vals.values()):out[t]=vals
            return date,out,None
        except Exception as e:
            last=e; time.sleep(.7*(attempt+1))
    return date,{},f'{type(last).__name__}:{last}'

def pct_rank(pairs):
    a=sorted(pairs,key=lambda z:(z[1],z[0])); n=len(a)
    return {t:(i+.5)/n for i,(t,_) in enumerate(a)} if n else {}

def meanlast(q,n):
    a=list(q)[-n:]
    return statistics.mean(a) if a else None

# Only query actual trading dates needed for the historical experiment.
fetch_dates=[d for d in o3.raw.dates if TRAIN[0]<=d<=DIAG[1] and d in o3.raw.market]
t86={}; errors={}
with cf.ThreadPoolExecutor(max_workers=6) as ex:
    futs={ex.submit(fetch_t86,d):d for d in fetch_dates}
    for fut in cf.as_completed(futs):
        d,tab,err=fut.result(); t86[d]=tab
        if err:errors[d]=err

# Build daily electronics-only normalized ranks. Dollar-normalize T86 share flow with
# same-day close / turnover; all are known after signal-day close, one full session
# before the predetermined t+1-close entry.
daily_chip={}
for d in fetch_dates:
    tab=t86.get(d,{})
    xs=[]
    for t,q in tab.items():
        s=o3.raw.stock.get((d,t)); px=o3.raw.by.get(d,{}).get(t)
        if not s or not px or s['turn20']<o3.raw.TURNMIN or px['turn']<=0 or px['c']<=0:continue
        x=dict(q)
        for k in ('foreign_net','trust_net','dealer_net','total_net'):
            x[k+'_ratio']=q[k]*px['c']/px['turn']
        xs.append((t,x))
    ranks={}
    for k in ('foreign','trust','dealer','total'):
        ranks[k]=pct_rank([(t,x[k+'_net_ratio']) for t,x in xs])
    for t,x in xs:
        daily_chip[(d,t)]={
          'foreign_rank':ranks['foreign'][t],'trust_rank':ranks['trust'][t],
          'dealer_rank':ranks['dealer'][t],'total_rank':ranks['total'][t],
          'sign_breadth':sum(x[k+'_net']>0 for k in ('foreign','trust','dealer'))/3.0,
        }

# Three-session persistence is fixed ex ante. Use only t and earlier chip observations.
hist=defaultdict(lambda:{k:deque(maxlen=3) for k in ('foreign_rank','trust_rank','total_rank','sign_breadth')})
chip3={}
for d in fetch_dates:
    todays=[(t,x) for (dd,t),x in daily_chip.items() if dd==d]
    # update with current t first because t data is known after t close when signal forms
    for t,x in todays:
        h=hist[t]
        for k in h:h[k].append(x[k])
        chip3[(d,t)]={
          'foreign_rank3':statistics.mean(h['foreign_rank']),
          'trust_rank3':statistics.mean(h['trust_rank']),
          'total_rank3':statistics.mean(h['total_rank']),
          'sign_breadth3':statistics.mean(h['sign_breadth']),
        }

price={(r['signal_date'],r['ticker']):r for r in o3.scored}
rows=[]
for (d,t),x in daily_chip.items():
    p=price.get((d,t)); z=chip3.get((d,t))
    if not p or not z:continue
    q={
      'signal_date':d,'ticker':t,'gross_return':p['gross_return'],'net20':p['gross_return']-PRIMARY_COST,
      'entry_date':p['entry_date'],'exit_date':p['exit_date'],'entry_close':p['entry_close'],'exit_open':p['exit_open'],
      'price_score':p['o3_score'],**x,**z,
    }
    rows.append(q)

train=[r for r in rows if TRAIN[0]<=r['signal_date']<=TRAIN[1]]
if len(train)<10000:raise RuntimeError(f'INSUFFICIENT_O5_TRAIN:{len(train)}')

def qedges(vals,bins=BINS):
    a=sorted(vals); n=len(a)
    return [a[min(n-1,max(0,math.ceil(i*n/bins)-1))] for i in range(1,bins)]
def bid(v,es):
    i=0
    while i<len(es) and v>es[i]:i+=1
    return i

def logit(p):
    p=min(max(p,1e-6),1-1e-6); return math.log(p/(1-p))

global_p=sum(r['net20']>0 for r in train)/len(train)
global_mean=statistics.mean(r['net20'] for r in train)
models={}
for model,features in MODEL_FEATURES.items():
    edges={k:qedges([r[k] for r in train]) for k in features}
    cells=defaultdict(lambda:[0,0,0.0])
    for r in train:
        y=int(r['net20']>0)
        for k in features:
            z=cells[(k,bid(r[k],edges[k]))];z[0]+=1;z[1]+=y;z[2]+=r['net20']
    def scorer(r,features=features,edges=edges,cells=cells):
        lod=[]; mus=[]; ns=[]
        for k in features:
            n,w,s=cells[(k,bid(r[k],edges[k]))]
            p=(w+SMOOTH*global_p)/(n+SMOOTH); m=(s+SMOOTH*global_mean)/(n+SMOOTH)
            lod.append(logit(p)-logit(global_p));mus.append(m-global_mean);ns.append(n)
        return statistics.mean(lod)+8.0*statistics.mean(mus),min(ns)
    models[model]={'features':features,'edges':edges,'score':scorer}

scored=[]
for r in rows:
    q=dict(r)
    for model,m in models.items():
        s,n=m['score'](r);q[model+'_score']=s;q[model+'_mincell']=n
    scored.append(q)

# Daily top1 is separately defined for each locked model candidate.
daily_by_model={}
for model in MODEL_FEATURES:
    byday=defaultdict(list)
    key=model+'_score'
    for r in scored:byday[r['signal_date']].append(r)
    out=[]
    for d,a in byday.items():
        a.sort(key=lambda r:(-r[key],-r['total_rank'],-r['foreign_rank'],r['ticker']))
        out.append(a[0])
    daily_by_model[model]=sorted(out,key=lambda r:r['signal_date'])

def wilson(w,n,z=1.959963984540054):
    if not n:return None
    p=w/n;z2=z*z;den=1+z2/n
    return (p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den

def metrics(rs,cost):
    xs=[r['gross_return']-cost for r in rs];n=len(xs);w=sum(x>0 for x in xs)
    nav=1.;peak=1.;mdd=0.;cur=mx=0
    for x in xs:
        nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
        if x<=0:cur+=1;mx=max(mx,cur)
        else:cur=0
    c=Counter(r['ticker'] for r in rs)
    return {'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson(w,n),
      'mean_return':statistics.mean(xs) if xs else None,'median_return':statistics.median(xs) if xs else None,
      'worst_return':min(xs) if xs else None,'best_return':max(xs) if xs else None,'compounded_return':nav-1 if n else 0.0,
      'max_drawdown':mdd,'max_consecutive_losses':mx,'top_ticker_share':max(c.values())/n if n and c else None}
def split(rs,p):return [r for r in rs if p[0]<=r['signal_date']<=p[1]]
def stress(rs):return {str(c):metrics(rs,c) for c in COSTS}

configs=[]
for model,daily in daily_by_model.items():
    devall=split(daily,DEV);key=model+'_score'
    if len(devall)<max(TARGET_COUNTS):continue
    ranked=sorted(devall,key=lambda r:(-r[key],r['signal_date']))
    for target in TARGET_COUNTS:
        th=ranked[target-1][key];sel=[r for r in devall if r[key]>=th];m=metrics(sel,PRIMARY_COST)
        configs.append({'model':model,'target_count':target,'threshold':th,'actual_dev_count':len(sel),'dev_net20':m})
if not configs:raise RuntimeError('NO_O5_CONFIGS')
configs.sort(key=lambda c:((c['dev_net20']['wilson95_lower'] or -1),c['dev_net20']['mean_return'] or -9,-abs(c['actual_dev_count']-45)),reverse=True)
champ=configs[0];model=champ['model'];key=model+'_score';th=champ['threshold']
selected=[r for r in daily_by_model[model] if r['signal_date']>=DEV[0] and r[key]>=th]
dev=split(selected,DEV);val=split(selected,VAL);diag=split(selected,DIAG);pre=dev+val
val20=metrics(val,PRIMARY_COST);diag20=metrics(diag,PRIMARY_COST)
coverage_ok=30<=val20['trades']<=75
positive=val20['mean_return'] is not None and val20['mean_return']>0 and val20['median_return'] is not None and val20['median_return']>0
if coverage_ok and positive and val20['win_rate'] is not None and val20['win_rate']>=.75 and diag20['win_rate'] is not None and diag20['win_rate']>=.60:
    status='O5_T86_RESEARCH_FRONTIER'
elif coverage_ok and positive and val20['win_rate'] is not None and val20['win_rate']>=.60:
    status='O5_T86_PROMISING_REUSED_VALIDATION'
else:status='O5_T86_REJECTED'

with EVENTS.open('w',encoding='utf-8') as fh:
    for label,rs in [('DEV_2024',dev),('REUSED_2025',val),('DIAGNOSTIC_2026',diag)]:
        for r in rs:fh.write(json.dumps({'split':label,'model':model,**r},ensure_ascii=False)+'\n')

res={
 'status':status,'model':'O5 full-history T86 cross-sectional institutional-flow overnight model',
 'timing':'signal after t close; T86(t)+price(t or earlier); predetermined t+1 close entry; t+2 open exit',
 'target':'gross overnight return minus 20bp > 0',
 'hypothesis_lock':'This O5 script and its two-model/three-coverage finite search were committed before the O5 T86 signal-audit output was inspected.',
 'data':{'t86_endpoint':'TWSE rwd/zh/fund/T86 historical JSON','requested_trading_dates':len(fetch_dates),'successful_dates':len(fetch_dates)-len(errors),'failed_dates':len(errors),'failed_date_examples':dict(list(sorted(errors.items()))[:20])},
 'features':{'chip':CHIP_FEATURES,'candidates':MODEL_FEATURES,'normalization':'same-day electronics cross-sectional percentile ranks of T86 net-share notional / turnover; plus 3-session persistence'},
 'protocol':{'fit':'2023 only','candidate_and_threshold_selection':'2024 only; finite 2 model families x 3 target counts','2025':'reused validation, not globally pristine','2026':'diagnostic only and excluded from selection','primary_cost':PRIMARY_COST,'cost_stress':COSTS,'bins':BINS,'smoothing':SMOOTH},
 'train_rows_2023':len(train),'global_train_win_rate':global_p,'global_train_mean_net20':global_mean,
 'development_configs':configs,'selected_model':model,'selected_target_count':champ['target_count'],'selected_threshold':th,
 'development_2024':stress(dev),'reused_validation_2025':stress(val),'pre2026':stress(pre),'historical_diagnostic_2026':stress(diag),
 'acceptance_checks':{'validation_coverage_30_to_75':coverage_ok,'validation_positive_mean_and_median_net20':positive,'frontier_requires_validation_win_gte_75_and_2026_diag_win_gte_60':True},
 'events_file':str(EVENTS.relative_to(ROOT)),
 'research_boundary':'Historical research only. 2025/2026 have already been exposed in the broader project; this does not restore pristine OOS status. No O5 formula or threshold is allowed to use 2026.',
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'No historical result guarantees future gains; T86 publication timing and market-at-close execution/slippage require operational validation before any live use.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('O5_FULL='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
