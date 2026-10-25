#!/usr/bin/env python3
from __future__ import annotations

import csv, gzip, json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / 'research' / 'codex_full_reset_20261023'
HIST = RESET / 'results' / 'stage_b' / 'TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
CURR = ROOT / 'hengce' / 'q017_radar' / 'data' / 'twse_electronics_history_2026.csv'
OUT = RESET / 'nextday_o1_independent_event_hazard_result.json'
EVENTS = RESET / 'nextday_o1_independent_event_hazard_events.jsonl'

TURNMIN = 20_000_000.0
JUMP = 0.15
PRIMARY_COST = 0.002
COSTS = (0.0, 0.002, 0.004, 0.008)
TRAIN = ('2023-01-01', '2023-12-31')
DEV = ('2024-01-01', '2024-12-31')
VAL = ('2025-01-01', '2025-12-31')
DIAG = ('2026-01-01', '2026-10-22')
TARGET_COUNTS = (35, 45, 55)
FEATURES = ('r1','r5','r20','r60','vol_ratio','dist_high20','close_loc','turn_ratio','breadth20','dispersion1','rel20')


def ff(x):
    if x in (None, '', '--', '---'): return None
    try:
        v = float(str(x).replace(',', ''))
        return v if math.isfinite(v) else None
    except Exception:
        return None


def load(path):
    op = gzip.open if path.suffix == '.gz' else open
    rows = []
    with op(path, 'rt', encoding='utf-8-sig', newline='') as fh:
        for x in csv.DictReader(fh):
            d = (x.get('date') or '').strip(); t = (x.get('ticker') or '').strip()
            if not d or not (len(t) == 4 and t.isdigit()): continue
            vals = [ff(x.get(k)) for k in ('open','high','low','close','turnover_ntd')]
            if any(v is None or v <= 0 for v in vals): continue
            o,h,l,c,turn = vals
            rows.append((d,t,o,h,l,c,turn))
    return rows

if not HIST.exists():
    raise RuntimeError(f'MISSING_OFFICIAL_MOTHER:{HIST}')
if not CURR.exists():
    raise RuntimeError(f'MISSING_2026_HISTORY:{CURR}')

by = defaultdict(dict)
for d,t,o,h,l,c,turn in load(HIST) + load(CURR):
    by[d][t] = {'o':o,'h':h,'l':l,'c':c,'turn':turn}
dates = sorted(by)
di = {d:i for i,d in enumerate(dates)}

# Raw PIT stock state. No HENGCE/V/X/HR scores, factor ranks, or prior picks.
stock = {}
for i,d in enumerate(dates):
    if i < 60: continue
    for t,r in by[d].items():
        hist = []
        ok = True
        for j in range(i-60, i+1):
            z = by[dates[j]].get(t)
            if not z:
                ok = False; break
            hist.append(z)
        if not ok: continue
        closes = [z['c'] for z in hist]
        turns = [z['turn'] for z in hist]
        bad = False
        daily = []
        for j in range(1, len(closes)):
            q = closes[j] / closes[j-1] - 1
            if abs(q) > JUMP:
                bad = True; break
            daily.append(q)
        if bad: continue
        def ret(h): return closes[-1] / closes[-1-h] - 1
        r1,r3,r5,r10,r20,r60 = (ret(h) for h in (1,3,5,10,20,60))
        v20s = daily[-20:]; v5s = daily[-5:]
        if len(v20s) < 20 or statistics.pstdev(v20s) <= 1e-12: continue
        vol20 = statistics.pstdev(v20s); vol5 = statistics.pstdev(v5s)
        turn20 = statistics.mean(turns[-20:]); turn5 = statistics.mean(turns[-5:])
        if turn20 < TURNMIN: continue
        hi20 = max(z['h'] for z in hist[-20:])
        prevc = hist[-2]['c']
        gap = r['o']/prevc-1
        body = r['c']/r['o']-1
        rng = (r['h']-r['l'])/r['c'] if r['c'] else 0.0
        close_loc = (r['c']-r['l'])/(r['h']-r['l']) if r['h'] > r['l'] else 0.5
        stock[(d,t)] = {
            'r1':r1,'r3':r3,'r5':r5,'r10':r10,'r20':r20,'r60':r60,
            'vol5':vol5,'vol20':vol20,'vol_ratio':vol5/vol20,
            'turn20':turn20,'turn_ratio':turn5/turn20,
            'dist_high20':r['c']/hi20,'gap':gap,'body':body,'range_pct':rng,'close_loc':close_loc,
        }

# Cross-sectional raw market state, independently computed from eligible stocks.
market = {}
for d in dates:
    xs = [(t,stock[(d,t)]) for t in by[d] if (d,t) in stock]
    if len(xs) < 20: continue
    r1s=[x['r1'] for _,x in xs]; r20s=[x['r20'] for _,x in xs]
    med20=statistics.median(r20s)
    market[d] = {
        'breadth20': sum(x>0 for x in r20s)/len(r20s),
        'dispersion1': statistics.pstdev(r1s),
        'median_r1': statistics.median(r1s),
        'median_r20': med20,
    }
    for t,x in xs:
        x['breadth20']=market[d]['breadth20']; x['dispersion1']=market[d]['dispersion1']; x['rel20']=x['r20']-med20

# Broad, interpretable event generators. They intentionally avoid any legacy score/rank.
def families(x):
    out=[]
    if x['r20'] > .03 and x['r60'] > .05 and x['dist_high20'] >= .86 and -.025 <= x['r1'] <= .055 and x['vol20'] <= .065:
        out.append('TREND_CONT')
    if x['r20'] > .03 and x['r60'] > .05 and -.07 <= x['r5'] < .005 and x['r1'] >= -.045 and x['dist_high20'] >= .80 and x['vol20'] <= .07:
        out.append('CONTROLLED_PULLBACK')
    if x['r20'] > .02 and x['r60'] > 0 and x['vol_ratio'] <= .90 and x['range_pct'] <= .055 and x['dist_high20'] >= .80 and x['r1'] >= -.04:
        out.append('COMPRESSION_TREND')
    return out


def outcome(d,t):
    i=di[d]
    if i+2 >= len(dates): return None
    ed,xd=dates[i+1],dates[i+2]
    e=by[ed].get(t); x=by[xd].get(t)
    if not e or not x or e['o'] <= 0 or x['c'] <= 0: return None
    # Fail closed on obvious discontinuity/corporate-action-like jumps.
    p=by[d].get(t)
    if not p or abs(e['c']/p['c']-1) > JUMP or abs(x['c']/e['c']-1) > JUMP: return None
    gross=x['c']/e['o']-1
    return {'entry_date':ed,'exit_date':xd,'entry_open':e['o'],'exit_close':x['c'],'gross_return':gross,'net20':gross-PRIMARY_COST}

raw=[]
for d in dates:
    if d < TRAIN[0] or d > DIAG[1] or d not in market: continue
    for t in by[d]:
        x=stock.get((d,t))
        if not x: continue
        fs=families(x)
        if not fs: continue
        o=outcome(d,t)
        if not o: continue
        for fam in fs:
            raw.append({'signal_date':d,'ticker':t,'family':fam,**{k:x[k] for k in FEATURES},**o})

train=[r for r in raw if TRAIN[0] <= r['signal_date'] <= TRAIN[1]]
if len(train) < 100: raise RuntimeError(f'INSUFFICIENT_2023_EVENTS:{len(train)}')

# Fixed empirical-Bayes feature likelihoods from 2023 only.
def quantile_edges(vals, bins=5):
    a=sorted(vals); n=len(a)
    return [a[min(n-1, max(0, math.ceil(q*n/bins)-1))] for q in range(1,bins)]

def bin_id(v,edges):
    i=0
    while i < len(edges) and v > edges[i]: i+=1
    return i

edges={k:quantile_edges([r[k] for r in train]) for k in FEATURES}
cell=defaultdict(lambda:[0,0]); famcell=defaultdict(lambda:[0,0])
for r in train:
    y=1 if r['net20']>0 else 0
    famcell[r['family']][0]+=y; famcell[r['family']][1]+=1
    for k in FEATURES:
        z=(k,bin_id(r[k],edges[k])); cell[z][0]+=y; cell[z][1]+=1

def post(w,n,a=8,b=8): return (w+a)/(n+a+b)
def base_prob(r):
    fp=post(*famcell[r['family']],a=12,b=12)
    ps=[]
    for k in FEATURES:
        ps.append(post(*cell[(k,bin_id(r[k],edges[k]))]))
    return .35*fp + .65*statistics.mean(ps)
for r in raw: r['base_p']=base_prob(r)

# One representative per family/day by 2023-frozen base probability.
reps_by_day=defaultdict(list)
for d in dates:
    rows=[r for r in raw if r['signal_date']==d]
    byfam=defaultdict(list)
    for r in rows: byfam[r['family']].append(r)
    for fam,arr in byfam.items():
        arr.sort(key=lambda z:(-z['base_p'],-z['turn_ratio'],z['ticker']))
        reps_by_day[d].append(arr[0])

# Prior-only analog hazard. At signal t, only events whose exit date is <= t are mature.
history=defaultdict(list)
day_picks=[]
for d in dates:
    if d < TRAIN[0] or d > DIAG[1]: continue
    current=[]
    for r in reps_by_day.get(d,[]):
        mature=[h for h in history[r['family']] if h['exit_date'] <= d]
        recent=mature[-96:]
        if recent:
            def dist(h):
                return abs(h['base_p']-r['base_p'])/.03 + abs(h['breadth20']-r['breadth20'])/.15 + abs(h['vol_ratio']-r['vol_ratio'])/.5 + abs(h['dist_high20']-r['dist_high20'])/.12
            near=sorted(recent,key=dist)[:min(32,len(recent))]
            w=sum(h['net20']>0 for h in near); n=len(near)
            analog_p=(w+6)/(n+12)
            analog_mean=statistics.mean(h['net20'] for h in near)
        else:
            analog_p=.5; analog_mean=0.0; n=0
        q=dict(r)
        q['analog_n']=n; q['analog_p']=analog_p; q['analog_mean_net20']=analog_mean
        q['hazard_p']=.55*r['base_p']+.45*analog_p
        current.append(q)
    # Add today's family reps only after scoring; maturity condition prevents leakage later.
    for r in reps_by_day.get(d,[]): history[r['family']].append(r)
    if current:
        current.sort(key=lambda z:(-z['hazard_p'],-z['analog_mean_net20'],-z['base_p'],z['ticker']))
        day_picks.append(current[0])


def wilson(w,n,z=1.959963984540054):
    if not n:return None
    p=w/n; z2=z*z; den=1+z2/n
    return (p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den

def metrics(rows,cost):
    rs=[r['gross_return']-cost for r in rows]; n=len(rs); w=sum(x>0 for x in rs)
    nav=1.; peak=1.; mdd=0.; max_losing=cur=0
    for x in rs:
        nav*=1+x; peak=max(peak,nav); mdd=min(mdd,nav/peak-1)
        if x<=0: cur+=1; max_losing=max(max_losing,cur)
        else: cur=0
    counts=Counter(r['ticker'] for r in rows); fam=Counter(r['family'] for r in rows)
    return {'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson(w,n),
            'mean_return':statistics.mean(rs) if rs else None,'median_return':statistics.median(rs) if rs else None,
            'worst_return':min(rs) if rs else None,'best_return':max(rs) if rs else None,
            'compounded_return':nav-1 if n else 0.0,'max_drawdown':mdd,'max_consecutive_losses':max_losing,
            'top_ticker_share':max(counts.values())/n if n and counts else None,'family_counts':dict(fam)}
def split(rows,period): return [r for r in rows if period[0] <= r['signal_date'] <= period[1]]
def stress(rows): return {str(c):metrics(rows,c) for c in COSTS}

dev_all=split(day_picks,DEV)
if len(dev_all) < max(TARGET_COUNTS): raise RuntimeError(f'INSUFFICIENT_2024_DAY_PICKS:{len(dev_all)}')
configs=[]
for target in TARGET_COUNTS:
    ranked=sorted(dev_all,key=lambda r:(-r['hazard_p'],r['signal_date']))
    threshold=ranked[target-1]['hazard_p']
    sel=[r for r in dev_all if r['hazard_p']>=threshold]
    m=metrics(sel,PRIMARY_COST)
    configs.append({'target_count':target,'threshold':threshold,'actual_dev_count':len(sel),'dev_net20':m})
# Selection criterion uses 2024 only: downside-safe hit rate first, then economics, then closeness to 45.
configs.sort(key=lambda c:((c['dev_net20']['wilson95_lower'] or -1),c['dev_net20']['mean_return'] or -9,-abs(c['actual_dev_count']-45)),reverse=True)
champ=configs[0]; threshold=champ['threshold']
selected=[r for r in day_picks if r['signal_date']>=DEV[0] and r['hazard_p']>=threshold]
dev=split(selected,DEV); val=split(selected,VAL); diag=split(selected,DIAG); pre=[*dev,*val]

dev20=metrics(dev,PRIMARY_COST); val20=metrics(val,PRIMARY_COST); pre20=metrics(pre,PRIMARY_COST); diag20=metrics(diag,PRIMARY_COST)
coverage_ok=30 <= val20['trades'] <= 65
positive_econ=(val20['mean_return'] is not None and val20['mean_return']>0 and val20['median_return'] is not None and val20['median_return']>0)
if coverage_ok and positive_econ and val20['win_rate'] is not None and val20['win_rate']>=.75:
    status='O1_STRICT_NEXTDAY_TARGET_GRADE'
elif coverage_ok and val20['mean_return'] is not None and val20['mean_return']>0 and val20['win_rate'] is not None and val20['win_rate']>=.60:
    status='O1_STRICT_NEXTDAY_PROMISING_NOT_TARGET'
else:
    status='O1_STRICT_NEXTDAY_REJECTED'

with EVENTS.open('w',encoding='utf-8') as fh:
    for label,rows in [('DEV_2024',dev),('FROZEN_VAL_2025',val),('DIAGNOSTIC_2026',diag)]:
        for r in rows:
            keep={k:v for k,v in r.items() if k not in FEATURES}
            fh.write(json.dumps({'split':label,**keep},ensure_ascii=False)+'\n')

res={
    'status':status,
    'model':'O1 independent raw-event empirical-Bayes + prior-only analog hazard',
    'timing':'signal after t close; enter t+1 open; exit t+2 close',
    'primary_label':'gross_return - 0.002 > 0',
    'independence':'Directly loads official TWSE electronics OHLC/turnover mother and 2026 history; no HENGCE/V/X/HR score, factor rank, ranking_v*, or legacy event identity is used.',
    'data':{'historical':str(HIST.relative_to(ROOT)),'current_2026':str(CURR.relative_to(ROOT)),'turnover20_min_ntd':TURNMIN,'jump_fail_closed':JUMP},
    'protocol':{'train_prior':'2023 only','development_threshold':'2024 only','frozen_validation':'2025','historical_diagnostic_only':'2026-01-01..2026-10-22','target_counts_2024':TARGET_COUNTS,'primary_cost':PRIMARY_COST,'cost_stress':COSTS,'2026_used_for_selection':False},
    'event_families':['TREND_CONT','CONTROLLED_PULLBACK','COMPRESSION_TREND'],
    'feature_order':FEATURES,
    'train_candidate_events':len(train),'daily_representative_picks':len(day_picks),
    'development_configs':configs,'selected_threshold':threshold,'selected_target_count':champ['target_count'],
    'development_2024':stress(dev),'frozen_validation_2025':stress(val),'pre2026':stress(pre),'historical_diagnostic_2026':stress(diag),
    'acceptance_checks':{'validation_coverage_30_to_65':coverage_ok,'validation_positive_mean_and_median_net20':positive_econ,'target_grade_requires_validation_net20_win_rate_gte_0_75':True,'promising_requires_validation_net20_win_rate_gte_0_60_and_positive_mean':True},
    'events_file':str(EVENTS.relative_to(ROOT)),
    'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
    'caveat':'Historical research only. 2026 has been exposed elsewhere in the project and is diagnostic, not untouched future OOS. No historical hit rate guarantees future gains.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('O1_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
