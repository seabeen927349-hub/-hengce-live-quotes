#!/usr/bin/env python3
from __future__ import annotations

import csv, gzip, json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / 'research' / 'codex_full_reset_20261023'
HIST = RESET / 'results' / 'stage_b' / 'TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
CURR = ROOT / 'hengce' / 'q017_radar' / 'data' / 'twse_electronics_history_2026.csv'
OUT = RESET / 'nextday_o2_reversal_analog_tailrisk_result.json'
EVENTS = RESET / 'nextday_o2_reversal_analog_tailrisk_events.jsonl'

TURNMIN = 20_000_000.0
JUMP = 0.15
PRIMARY_COST = 0.002
COSTS = (0.0, 0.002, 0.004, 0.008)
TRAIN = ('2023-01-01', '2023-12-31')
DEV = ('2024-01-01', '2024-12-31')
VAL = ('2025-01-01', '2025-12-31')
DIAG = ('2026-01-01', '2026-10-22')
TARGET_COUNTS = (35, 45, 55)
DIST_FEATURES = ('r1','r3','r5','r20','r60','gap','body','close_loc','vol_ratio','turn_ratio','breadth20','dispersion1','rel20')


def ff(x):
    if x in (None, '', '--', '---'): return None
    try:
        v = float(str(x).replace(',', ''))
        return v if math.isfinite(v) else None
    except Exception:
        return None


def load(path):
    op = gzip.open if path.suffix == '.gz' else open
    rows=[]
    with op(path,'rt',encoding='utf-8-sig',newline='') as fh:
        for x in csv.DictReader(fh):
            d=(x.get('date') or '').strip(); t=(x.get('ticker') or '').strip()
            if not d or not (len(t)==4 and t.isdigit()): continue
            vals=[ff(x.get(k)) for k in ('open','high','low','close','turnover_ntd')]
            if any(v is None or v <= 0 for v in vals): continue
            o,h,l,c,turn=vals
            rows.append((d,t,o,h,l,c,turn))
    return rows

if not HIST.exists(): raise RuntimeError(f'MISSING_OFFICIAL_MOTHER:{HIST}')
if not CURR.exists(): raise RuntimeError(f'MISSING_2026_HISTORY:{CURR}')

by=defaultdict(dict)
for d,t,o,h,l,c,turn in load(HIST)+load(CURR):
    by[d][t]={'o':o,'h':h,'l':l,'c':c,'turn':turn}
dates=sorted(by); di={d:i for i,d in enumerate(dates)}

stock={}
for i,d in enumerate(dates):
    if i < 60: continue
    for t,r in by[d].items():
        hist=[]; ok=True
        for j in range(i-60,i+1):
            z=by[dates[j]].get(t)
            if not z: ok=False; break
            hist.append(z)
        if not ok: continue
        closes=[z['c'] for z in hist]; turns=[z['turn'] for z in hist]
        daily=[]; bad=False
        for j in range(1,len(closes)):
            q=closes[j]/closes[j-1]-1
            if abs(q)>JUMP: bad=True; break
            daily.append(q)
        if bad: continue
        def ret(h): return closes[-1]/closes[-1-h]-1
        r1,r3,r5,r10,r20,r60=(ret(h) for h in (1,3,5,10,20,60))
        v20=daily[-20:]; v5=daily[-5:]
        vol20=statistics.pstdev(v20)
        if vol20 <= 1e-12: continue
        vol5=statistics.pstdev(v5)
        turn20=statistics.mean(turns[-20:]); turn5=statistics.mean(turns[-5:])
        if turn20 < TURNMIN: continue
        prevc=hist[-2]['c']; gap=r['o']/prevc-1; body=r['c']/r['o']-1
        rng=(r['h']-r['l'])/r['c'] if r['c'] else 0.0
        close_loc=(r['c']-r['l'])/(r['h']-r['l']) if r['h']>r['l'] else .5
        hi20=max(z['h'] for z in hist[-20:]); lo20=min(z['l'] for z in hist[-20:])
        stock[(d,t)]={
            'r1':r1,'r3':r3,'r5':r5,'r10':r10,'r20':r20,'r60':r60,
            'vol5':vol5,'vol20':vol20,'vol_ratio':vol5/vol20,
            'turn20':turn20,'turn_ratio':turn5/turn20,
            'gap':gap,'body':body,'range_pct':rng,'close_loc':close_loc,
            'dist_high20':r['c']/hi20,'dist_low20':r['c']/lo20,
        }

market={}
for d in dates:
    xs=[(t,stock[(d,t)]) for t in by[d] if (d,t) in stock]
    if len(xs)<20: continue
    r1s=[x['r1'] for _,x in xs]; r20s=[x['r20'] for _,x in xs]
    med1=statistics.median(r1s); med20=statistics.median(r20s)
    market[d]={
        'breadth20':sum(x>0 for x in r20s)/len(r20s),
        'dispersion1':statistics.pstdev(r1s),'median_r1':med1,'median_r20':med20,
    }
    for t,x in xs:
        x['breadth20']=market[d]['breadth20']; x['dispersion1']=market[d]['dispersion1']
        x['rel1']=x['r1']-med1; x['rel20']=x['r20']-med20

# O2 is deliberately the inverse hypothesis of O1's 2024 development failure:
# long only after short-term weakness that shows same-day reclaim / stabilization.
def families(x):
    out=[]
    if x['r60']>.02 and x['r20']>-.10 and -.085<=x['r5']<=-.005 and -.065<=x['r1']<=.012 and x['close_loc']>=.58 and x['body']>=-.012:
        out.append('PULLBACK_RECLAIM')
    if -.065<=x['gap']<=-.006 and x['body']>=.002 and x['close_loc']>=.62 and x['r20']>-.12 and x['r60']>-.08:
        out.append('GAP_DOWN_RECLAIM')
    if -.08<=x['r1']<=-.012 and x['r3']<=-.018 and x['close_loc']>=.70 and x['body']>=-.015 and x['turn_ratio']>=.70 and x['r20']>-.16:
        out.append('SELLOFF_RECLAIM')
    if x['r60']>.04 and x['r20']>.015 and -.055<=x['r1']<=-.004 and x['r5']<.015 and x['vol_ratio']<=1.10 and x['close_loc']>=.48:
        out.append('TREND_DIP')
    return out


def outcome(d,t):
    i=di[d]
    if i+2>=len(dates): return None
    ed,xd=dates[i+1],dates[i+2]; e=by[ed].get(t); z=by[xd].get(t); p=by[d].get(t)
    if not e or not z or not p or e['o']<=0 or z['c']<=0: return None
    if abs(e['c']/p['c']-1)>JUMP or abs(z['c']/e['c']-1)>JUMP: return None
    gross=z['c']/e['o']-1
    return {'entry_date':ed,'exit_date':xd,'entry_open':e['o'],'exit_close':z['c'],'gross_return':gross,'net20':gross-PRIMARY_COST}

raw=[]
for d in dates:
    if d<TRAIN[0] or d>DIAG[1] or d not in market: continue
    for t in by[d]:
        x=stock.get((d,t))
        if not x: continue
        fs=families(x)
        if not fs: continue
        o=outcome(d,t)
        if not o: continue
        # fixed, outcome-free reclaim geometry only for picking one representative per family/day
        neg1=min(max(-x['r1'],0.0),.06); neggap=min(max(-x['gap'],0.0),.05); posbody=min(max(x['body'],0.0),.05)
        geometry=x['close_loc'] + 3.0*posbody + 1.2*neg1 + .8*neggap - .6*max(x['vol_ratio']-1.0,0.0)
        for fam in fs:
            raw.append({'signal_date':d,'ticker':t,'family':fam,'geometry':geometry,**{k:x[k] for k in DIST_FEATURES},**o})

train=[r for r in raw if TRAIN[0]<=r['signal_date']<=TRAIN[1]]
if len(train)<100: raise RuntimeError(f'INSUFFICIENT_2023_EVENTS:{len(train)}')

# Robust 2023-only distance scales. No outcome information enters geometry selection.
scales={}
for k in DIST_FEATURES:
    vals=sorted(r[k] for r in train); med=statistics.median(vals)
    ad=sorted(abs(v-med) for v in vals); mad=statistics.median(ad)
    scales[k]=max(mad*1.4826,1e-4)

reps=[]
bydf=defaultdict(list)
for r in raw: bydf[(r['signal_date'],r['family'])].append(r)
for (d,fam),arr in bydf.items():
    arr.sort(key=lambda z:(-z['geometry'],-z['turn_ratio'],z['ticker']))
    reps.append(arr[0])
reps.sort(key=lambda z:(z['signal_date'],z['family']))

# Prior-only nearest analogs. Current event can only use historical outcomes matured by signal date.
hist=defaultdict(list); scored=[]
for d in dates:
    today=[r for r in reps if r['signal_date']==d]
    cur=[]
    for r in today:
        mature=[h for h in hist[r['family']] if h['exit_date']<=d]
        # Keep a broad rolling history but prioritize state similarity.
        pool=mature[-180:]
        if len(pool)>=24:
            def dist(h):
                s=0.0
                for k in DIST_FEATURES:
                    # cap each dimension so one noisy feature cannot dominate
                    s += min(abs(h[k]-r[k])/scales[k],4.0)
                return s/len(DIST_FEATURES)
            near=sorted(pool,key=dist)[:min(48,len(pool))]
            rs=[h['net20'] for h in near]; n=len(rs); w=sum(x>0 for x in rs)
            p=w/n
            z=1.6448536269514722 # one-sided 95% lower bound; fixed before holdout
            z2=z*z; den=1+z2/n
            lower=(p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den
            mean=statistics.mean(rs); med=statistics.median(rs)
            neg=[x for x in rs if x<0]
            downside=math.sqrt(statistics.mean(x*x for x in neg)) if neg else 0.0
            q25=sorted(rs)[max(0,math.ceil(.25*n)-1)]
            # Composite rewards robust hit probability and positive economics, penalizes loss-tail severity.
            score=lower + 4.0*max(-.025,min(.025,mean)) + 1.5*max(-.025,min(.025,med)) - 1.5*downside
            q=dict(r); q.update({'analog_n':n,'analog_win_rate':p,'analog_wilson1s95_lower':lower,
                                  'analog_mean_net20':mean,'analog_median_net20':med,'analog_q25_net20':q25,
                                  'analog_downside_rms':downside,'tailrisk_score':score})
            cur.append(q)
    # score today first, then add today to history (still not mature for subsequent days until exit_date<=future signal date)
    for r in today: hist[r['family']].append(r)
    if cur:
        cur.sort(key=lambda z:(-z['tailrisk_score'],-z['analog_wilson1s95_lower'],-z['analog_mean_net20'],-z['geometry'],z['ticker']))
        scored.append(cur[0])


def wilson(w,n,z=1.959963984540054):
    if not n:return None
    p=w/n; z2=z*z; den=1+z2/n
    return (p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den

def metrics(rows,cost):
    rs=[r['gross_return']-cost for r in rows]; n=len(rs); w=sum(x>0 for x in rs)
    nav=1.; peak=1.; mdd=0.; streak=mx=0
    for x in rs:
        nav*=1+x; peak=max(peak,nav); mdd=min(mdd,nav/peak-1)
        if x<=0: streak+=1; mx=max(mx,streak)
        else: streak=0
    c=Counter(r['ticker'] for r in rows); f=Counter(r['family'] for r in rows)
    return {'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson(w,n),
            'mean_return':statistics.mean(rs) if rs else None,'median_return':statistics.median(rs) if rs else None,
            'worst_return':min(rs) if rs else None,'best_return':max(rs) if rs else None,'compounded_return':nav-1 if n else 0.0,
            'max_drawdown':mdd,'max_consecutive_losses':mx,'top_ticker_share':max(c.values())/n if n and c else None,'family_counts':dict(f)}
def split(rows,p): return [r for r in rows if p[0]<=r['signal_date']<=p[1]]
def stress(rows): return {str(c):metrics(rows,c) for c in COSTS}

dev_all=split(scored,DEV)
if len(dev_all)<max(TARGET_COUNTS): raise RuntimeError(f'INSUFFICIENT_2024_SCORED:{len(dev_all)}')
configs=[]
for target in TARGET_COUNTS:
    ranked=sorted(dev_all,key=lambda r:(-r['tailrisk_score'],r['signal_date']))
    th=ranked[target-1]['tailrisk_score']
    sel=[r for r in dev_all if r['tailrisk_score']>=th]
    m=metrics(sel,PRIMARY_COST)
    configs.append({'target_count':target,'threshold':th,'actual_dev_count':len(sel),'dev_net20':m})
configs.sort(key=lambda c:((c['dev_net20']['wilson95_lower'] or -1),c['dev_net20']['mean_return'] or -9,-abs(c['actual_dev_count']-45)),reverse=True)
champ=configs[0]; threshold=champ['threshold']
selected=[r for r in scored if r['signal_date']>=DEV[0] and r['tailrisk_score']>=threshold]
dev=split(selected,DEV); val=split(selected,VAL); diag=split(selected,DIAG); pre=dev+val

dev20=metrics(dev,PRIMARY_COST); val20=metrics(val,PRIMARY_COST); pre20=metrics(pre,PRIMARY_COST); diag20=metrics(diag,PRIMARY_COST)
coverage_ok=30<=val20['trades']<=70
positive_econ=(val20['mean_return'] is not None and val20['mean_return']>0 and val20['median_return'] is not None and val20['median_return']>0)
if coverage_ok and positive_econ and val20['win_rate'] is not None and val20['win_rate']>=.75:
    status='O2_STRICT_NEXTDAY_TARGET_GRADE'
elif coverage_ok and val20['mean_return'] is not None and val20['mean_return']>0 and val20['win_rate'] is not None and val20['win_rate']>=.60:
    status='O2_STRICT_NEXTDAY_PROMISING_NOT_TARGET'
else:
    status='O2_STRICT_NEXTDAY_REJECTED'

with EVENTS.open('w',encoding='utf-8') as fh:
    for label,rows in [('DEV_2024',dev),('FROZEN_RELATIVE_TO_O2_2025',val),('DIAGNOSTIC_2026',diag)]:
        for r in rows:
            fh.write(json.dumps({'split':label,**r},ensure_ascii=False)+'\n')

res={
    'status':status,
    'model':'O2 strict-nextday long reversal + prior-only analog downside-tail control',
    'timing':'signal after t close; enter t+1 open; exit t+2 close',
    'primary_label':'gross_return - 0.002 > 0',
    'independence':'Direct raw TWSE electronics OHLC/turnover only; no HENGCE/V/X/HR/ranking score or legacy pick identity.',
    'protocol':{'train_distance_scale':'2023 only','development_threshold':'2024 only','validation':'2025 frozen relative to O2 code, but not globally untouched because 2025 has been exposed by prior project experiments','diagnostic':'2026-01-01..2026-10-22 only','target_counts_2024':TARGET_COUNTS,'primary_cost':PRIMARY_COST,'cost_stress':COSTS,'2026_used_for_selection':False},
    'hypothesis_lock':'O2 reverses O1 because O1 development-year 2024 trend/continuation families were strongly negative. O2 family definitions and score formula are fixed before inspecting O2 validation output.',
    'event_families':['PULLBACK_RECLAIM','GAP_DOWN_RECLAIM','SELLOFF_RECLAIM','TREND_DIP'],
    'distance_features':DIST_FEATURES,
    'train_candidate_events':len(train),'family_day_representatives':len(reps),'daily_scored_picks':len(scored),
    'development_configs':configs,'selected_threshold':threshold,'selected_target_count':champ['target_count'],
    'development_2024':stress(dev),'frozen_relative_validation_2025':stress(val),'pre2026':stress(pre),'historical_diagnostic_2026':stress(diag),
    'acceptance_checks':{'validation_coverage_30_to_70':coverage_ok,'validation_positive_mean_and_median_net20':positive_econ,'target_grade_requires_validation_net20_win_rate_gte_0_75':True,'promising_requires_validation_net20_win_rate_gte_0_60_and_positive_mean':True},
    'events_file':str(EVENTS.relative_to(ROOT)),
    'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
    'caveat':'Historical research only; no historical result guarantees future gains.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('O2_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
