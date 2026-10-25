#!/usr/bin/env python3
from __future__ import annotations

import contextlib, io, json, math, statistics
from pathlib import Path

# Independent research line. Shared component: PIT TWSE electronics raw data loader only.
# No HENGCE/V/X/HR/I1 picks, scores, weights, or event identities are predictors.
with contextlib.redirect_stdout(io.StringIO()):
    import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as data

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/codex_full_reset_20261023/I2_PRIOR_ONLY_HAZARD_RESULT_20261025.json'
EVENTS = ROOT / 'research/codex_full_reset_20261023/i2_prior_only_hazard_events.jsonl'
DATES=data.dates; BY=data.by
TURNMIN=20_000_000.0
HOLDS=(10,15,20)
BINS=6
SAMPLE_STRIDE=5
ALPHA=4.0; BETA=1.0

FEATURE_SETS={
 'CORE':('r20','r60','vol20','beta60'),
 'PATH':('r5','r20','r60','vol20','resid5'),
 'DEFENSIVE':('vol20','beta60','r20','r60','logturn'),
 'REV_TREND':('r5','r20','r60','resid5','vol20','logturn'),
 'FULL':('r1','r5','r20','r60','vol20','beta60','resid5','logturn','breadth20'),
}
ELIGIBILITY=('ALL','R20_POS','R60_POS','BOTH_POS','BETA_LE1')


def wilson(w,n,z=1.959963984540054):
    if not n:return None
    p=w/n; den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/den


def quantile(xs,q):
    ys=sorted(xs)
    if not ys:return 0.0
    if len(ys)==1:return ys[0]
    p=(len(ys)-1)*q; lo=int(math.floor(p)); hi=int(math.ceil(p))
    return ys[lo] if lo==hi else ys[lo]+(ys[hi]-ys[lo])*(p-lo)

# Precompute market breadth once. This keeps the independent model practical without changing semantics.
BREADTH={}
for d in DATES:
    eligible=[x for x in BY[d].values() if not x.bad and x.r20 is not None and x.turn20 is not None and x.turn20>=TURNMIN]
    BREADTH[d]=sum(x.r20>0 for x in eligible)/len(eligible) if eligible else .5

FCACHE={}
def feat(d,t):
    key=(d,t)
    if key in FCACHE:return FCACHE[key]
    r=BY[d].get(t)
    if not r or r.bad or r.r1 is None or r.r5 is None or r.r20 is None or r.r60 is None or r.vol20 is None or r.turn20 is None or r.turn20<TURNMIN:
        FCACHE[key]=None; return None
    beta=r.beta60 if r.beta60 is not None and math.isfinite(r.beta60) else 1.0
    resid=r.resid5 if r.resid5 is not None and math.isfinite(r.resid5) else r.r5
    f={'r1':r.r1,'r5':r.r5,'r20':r.r20,'r60':r.r60,'vol20':r.vol20,'beta60':beta,'resid5':resid,
       'logturn':math.log(max(r.turn20,1.0)),'breadth20':BREADTH[d]}
    FCACHE[key]=f
    return f


def elig(f,kind):
    if kind=='ALL':return True
    if kind=='R20_POS':return f['r20']>0
    if kind=='R60_POS':return f['r60']>0
    if kind=='BOTH_POS':return f['r20']>0 and f['r60']>0
    if kind=='BETA_LE1':return f['beta60']<=1.0
    return False


def outcome(si,t,h,end):
    ei=si+1; xi=ei+h
    if xi>=len(DATES) or DATES[xi]>end:return None
    er=BY[DATES[ei]].get(t)
    if not er or er.o is None or er.o<=0:return None
    entry=er.o
    for j in range(ei+1,xi+1):
        r=BY[DATES[j]].get(t)
        if not r or r.bad or r.c is None or r.c<=0:return None
        ret=r.c/entry-1
        if ret>0:return {'win':True,'entry_date':DATES[ei],'exit_date':DATES[j],'entry_open':entry,'exit_close':r.c,'gross_return':ret,'hold':j-ei,'exit_i':j}
    r=BY[DATES[xi]].get(t)
    if not r or r.bad or r.c is None or r.c<=0:return None
    ret=r.c/entry-1
    return {'win':ret>0,'entry_date':DATES[ei],'exit_date':DATES[xi],'entry_open':entry,'exit_close':r.c,'gross_return':ret,'hold':h,'exit_i':xi}

TRAIN_ROWS={}
def training_examples(cutoff,h):
    key=(cutoff,h)
    if key in TRAIN_ROWS:return TRAIN_ROWS[key]
    rows=[]
    for i,d in enumerate(DATES):
        if d<'2023-01-01' or d>cutoff or i % SAMPLE_STRIDE != 0:continue
        if i+1+h>=len(DATES) or DATES[i+1+h]>cutoff:continue
        for t in BY[d]:
            f=feat(d,t)
            if f is None:continue
            o=outcome(i,t,h,cutoff)
            if o is None:continue
            rows.append((f,1 if o['win'] else 0))
    TRAIN_ROWS[key]=rows
    return rows


def fit_binned(rows,features):
    model={'features':features,'parts':{}}
    base=(sum(y for _,y in rows)+ALPHA)/(len(rows)+ALPHA+BETA)
    model['base']=base
    for name in features:
        vals=[f[name] for f,_ in rows]
        cuts=[quantile(vals,j/BINS) for j in range(1,BINS)]
        wins=[0]*BINS; ns=[0]*BINS
        for f,y in rows:
            b=0
            while b<len(cuts) and f[name]>cuts[b]:b+=1
            ns[b]+=1; wins[b]+=y
        probs=[(wins[b]+ALPHA)/(ns[b]+ALPHA+BETA) if ns[b] else base for b in range(BINS)]
        model['parts'][name]={'cuts':cuts,'probs':probs,'n':ns}
    return model


def logit(p):
    p=min(max(p,1e-5),1-1e-5);return math.log(p/(1-p))


def score(model,f):
    vals=[]; base_logit=logit(model['base'])
    for name in model['features']:
        part=model['parts'][name]; b=0
        while b<len(part['cuts']) and f[name]>part['cuts'][b]:b+=1
        vals.append(logit(part['probs'][b]))
    return base_logit + sum(v-base_logit for v in vals)/max(len(vals),1)

MODEL_CACHE={}
def yearly_model(eval_year,h,features):
    cutoff=f'{eval_year-1}-12-31'
    key=(cutoff,h,features)
    if key not in MODEL_CACHE:
        MODEL_CACHE[key]=fit_binned(training_examples(cutoff,h),features)
    return MODEL_CACHE[key]

PICK_CACHE={}
def choose(d,year,spec):
    key=(d,year,spec['features'],spec['eligibility'],spec['hold'])
    if key in PICK_CACHE:return PICK_CACHE[key]
    m=yearly_model(year,spec['hold'],FEATURE_SETS[spec['features']])
    best=None
    for t in BY[d]:
        f=feat(d,t)
        if f is None or not elig(f,spec['eligibility']):continue
        z=(score(m,f),t,f)
        if best is None or z[0]>best[0] or (z[0]==best[0] and z[1]<best[1]):best=z
    PICK_CACHE[key]=best
    return best


def simulate(spec,start,end,include=False):
    year=int(start[:4]); ev=[]; next_free=-1
    for i,d in enumerate(DATES):
        if d<start or d>end or i<next_free:continue
        p=choose(d,year,spec)
        if p is None:continue
        s,t,f=p; o=outcome(i,t,spec['hold'],end)
        if o is None:continue
        ev.append({'signal_date':d,'ticker':t,'hazard_score':s,'features':f,**o}); next_free=o['exit_i']
    n=len(ev);w=sum(e['win'] for e in ev);rets=[e['gross_return'] for e in ev]
    out={'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson(w,n),
         'mean_gross_return':statistics.mean(rets) if rets else None,'median_gross_return':statistics.median(rets) if rets else None,
         'mean_hold':statistics.mean(e['hold'] for e in ev) if ev else None,
         'unique_tickers':len(set(e['ticker'] for e in ev)),
         'dominant_ticker_trades':max((sum(x['ticker']==t for x in ev) for t in set(x['ticker'] for x in ev)),default=0)}
    if include:out['events']=ev
    return out

SPECS=[{'features':fs,'eligibility':el,'hold':h} for fs in FEATURE_SETS for el in ELIGIBILITY for h in HOLDS]
rows=[]
for spec in SPECS:
    m=simulate(spec,'2024-01-01','2024-12-31')
    if 30<=m['trades']<=60:rows.append({'spec':spec,'development_2024':m})
if not rows:raise RuntimeError('no I2 development candidates')
rows.sort(key=lambda x:(x['development_2024']['wilson95_lower'],x['development_2024']['win_rate'],-abs(x['development_2024']['trades']-45)),reverse=True)
champ=rows[0]
# Spec is frozen from 2024. Parameters update annually using only prior matured years.
champ['validation_2025']=simulate(champ['spec'],'2025-01-01','2025-12-31')
champ['historical_diagnostic_2026']=simulate(champ['spec'],'2026-01-01','2026-10-22')

EVENTS.write_text('',encoding='utf-8')
for label,period in [('DEV2024',('2024-01-01','2024-12-31')),('VAL2025',('2025-01-01','2025-12-31')),('DIAG2026',('2026-01-01','2026-10-22'))]:
    m=simulate(champ['spec'],*period,include=True)
    with EVENTS.open('a',encoding='utf-8') as fh:
        for e in m['events']:fh.write(json.dumps({'split':label,**e},ensure_ascii=False)+'\n')

v25=champ['validation_2025']; d26=champ['historical_diagnostic_2026']
status='I2_DOES_NOT_VALIDATE'
if v25['trades']>=30 and v25['win_rate']>=.80:
    status='I2_VALIDATES_ABOVE_80_PERCENT'
if v25['trades']>=30 and v25['win_rate']>=.85 and d26['trades']>=20 and d26['win_rate']>=.80:
    status='I2_PROMISING_PRIOR_ONLY_INDEPENDENT_RANKER'

res={'model':'I2_PRIOR_ONLY_HAZARD_RANKER','status':status,
 'objective':'independently learn which raw PIT market/stock states have high probability of any positive close after next-open entry, without using HENGCE or prior model picks',
 'independence':{'shared_only':'PIT raw TWSE-listed-electronics price/turnover loader','does_not_use':['HENGCE/V/X/HR/I1 picks','HENGCE scores or weights','97-event identities']},
 'protocol':{'training':'expanding annual; 2024 model uses matured 2023 labels, 2025 uses matured data through 2024, 2026 through 2025','development_selection':'spec chosen on 2024 only; frozen before 2025','validation':'2025','historical_diagnostic':'2026-01-01..2026-10-22','candidate_specs':len(SPECS),'binned_empirical_bayes':{'bins':BINS,'alpha':ALPHA,'beta':BETA,'sample_stride_days':SAMPLE_STRIDE}},
 'champion':champ,'top10_development':rows[:10],
 'comparators':{'97_reference_pre2026_win_rate':78/97,'97_reference_2026_win_rate':.80,'I1_pre2026_win_rate':78/90,'I1_2026_win_rate':22/26},
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'2026 has been exposed in the broader project; diagnostic only, not untouched future OOS.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('I2_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
