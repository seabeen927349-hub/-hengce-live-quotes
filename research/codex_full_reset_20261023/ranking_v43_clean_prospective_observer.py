#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import statistics
import subprocess
import tarfile
import zipfile
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HIST_DEFAULT = ROOT / 'research/codex_full_reset_20261023/results/stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
CURR_DEFAULT = ROOT / 'hengce/q017_radar/data/twse_electronics_history_2026.csv'
ARCHIVE_DEFAULT = ROOT / 'research/codex_full_reset_20261023/archive/20261024/HENGCE_FINAL_RESEARCH_ARCHIVE_20261024.tar.gz'
OUT_DEFAULT = ROOT / 'research/codex_full_reset_20261023/results/V43_CLEAN_PROSPECTIVE_OBSERVER_RESULT.json'
V43_SOURCE = ROOT / 'research/codex_full_reset_20261023/ranking_v43_expanding_regime_icir.py'

LOCK_DATE = '2026-10-24'
LOCK_COMMIT = '2e48350b8eab28c7fd81d1144e15aa3fa892b855'
EXPECTED_V43_BLOB_SHA = '60c3ce478c5f88bfce9263739a310ea5f5cf05a6'
EXPECTED_PRELOCK_EVENTS_SHA256 = 'ed5b0c4caff523525ecafb303e04dc82bc07d7d2fe706733edf4ce0180ecfd6e'
EXPECTED_PRELOCK_EVENT_COUNT = 30
EXPECTED_PRELOCK_LAST_EXIT = '2026-09-23'
BASELINE_2026_CUTOFF = '2026-10-22'

COSTS = (0.008, 0.012, 0.016)
JUMP = 0.15
H = 20
TOPN = 3
TURNMIN = 20_000_000.0
BREADTH_CUTOFF = 0.50
V6 = (0.20, 0.25, 0.30, 0.05, 0.20)
FACTORS = ('resid_rev', 'mom20', 'skip5_60', 'liquidity', 'lowvol')
SHRINK_TO_V6 = 0.90
ICIR_STABILIZER = 0.05
MIN_REGIME_ANCHORS = 3
CAP = 0.50
COV_SHRINK = 0.50
BREADTH_LO = 0.50
BREADTH_HI = 0.60
TAIL_Q = 0.75
MIN_PRIOR_SIGMA = 4
INTERIM_N = 6
PRIMARY_N = 12
GLOBAL = {
    '2024': (0.21026935533573474, 0.24955453687572232, 0.2865882760386327, 0.07358783174991028, 0.18000000000000002),
    '2025': (0.20159241998850475, 0.2512249587399482, 0.2864638040929887, 0.05990526148737986, 0.20081355569117848),
    '2026': (0.1880651272237035, 0.25859212409312254, 0.28170466457881926, 0.0745153923199833, 0.19712269178437147),
}

AUTHORITY = {
    'research_only': True,
    'capital_authority_twd': 0,
    'broker_order_execution': False,
    'production_promotion': False,
    'merge_authorized': False,
    'main_write': False,
    'q017_production_change': False,
    'e2_production_change': False,
    'm1_production_change': False,
    'pr_30_merge': False,
}


class R:
    __slots__ = ('d','t','o','c','turn','r1','r5','r20','r60','turn20','vol20','beta60','resid5','bad')
    def __init__(self, d, t, o, c, turn):
        self.d=d; self.t=t; self.o=o; self.c=c; self.turn=turn
        self.r1=self.r5=self.r20=self.r60=self.turn20=self.vol20=self.beta60=self.resid5=None
        self.bad=False


def ff(x):
    if x in (None, '', '--', '---'):
        return None
    try:
        v=float(str(x).replace(',',''))
        return v if math.isfinite(v) else None
    except Exception:
        return None


def sha256_path(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha(path: Path) -> str:
    return subprocess.check_output(['git','hash-object',str(path.relative_to(ROOT))], cwd=ROOT, text=True).strip()


def load_rows(path: Path):
    op=gzip.open if path.suffix == '.gz' else open
    out=[]
    with op(path, 'rt', encoding='utf-8-sig', newline='') as fh:
        for x in csv.DictReader(fh):
            d=(x.get('date') or '').strip(); t=(x.get('ticker') or '').strip()
            if d and len(t)==4 and t.isdigit():
                out.append(R(d,t,ff(x.get('open')),ff(x.get('close')),ff(x.get('turnover_ntd'))))
    return out


def ranks(vals):
    a=sorted(vals.items(), key=lambda kv:(kv[1],kv[0])); n=len(a); out={}
    if n<=1:
        return {t:0.5 for t,v in a}
    i=0
    while i<n:
        j=i+1
        while j<n and a[j][1]==a[i][1]:
            j+=1
        pct=(((i+1)+j)/2-1)/(n-1)
        for k in range(i,j): out[a[k][0]]=pct
        i=j
    return out


def corr(x,y):
    if len(x)<10: return None
    xb=statistics.mean(x); yb=statistics.mean(y)
    dx=sum((a-xb)**2 for a in x); dy=sum((b-yb)**2 for b in y)
    if dx<=0 or dy<=0: return None
    return sum((a-xb)*(b-yb) for a,b in zip(x,y))/math.sqrt(dx*dy)


def build_state(hist_path: Path, curr_path: Path):
    by=defaultdict(dict)
    for r in load_rows(hist_path)+load_rows(curr_path):
        by[r.d][r.t]=r
    dates=sorted(by)
    for i,d in enumerate(dates):
        if i==0: continue
        pd=dates[i-1]
        for t,r in by[d].items():
            p=by[pd].get(t)
            if p and p.c and r.c and p.c>0 and r.c>0:
                z=r.c/p.c-1; r.bad=abs(z)>JUMP
                if not r.bad: r.r1=z
    mkt=defaultdict(dict)
    for i,d in enumerate(dates):
        for t,r in by[d].items():
            for h in (5,20,60):
                if i<h: continue
                q=by[dates[i-h]].get(t)
                if not q or not q.c or not r.c or q.c<=0 or r.c<=0: continue
                ok=True
                for j in range(i-h+1,i+1):
                    z=by[dates[j]].get(t)
                    if z is None or z.bad:
                        ok=False; break
                if ok: setattr(r,f'r{h}',r.c/q.c-1)
            if i>=19:
                zs=[by[dates[j]].get(t) for j in range(i-19,i+1)]
                if all(z is not None and z.turn is not None and z.turn>=0 for z in zs):
                    r.turn20=statistics.mean(z.turn for z in zs)
                if all(z is not None and z.r1 is not None for z in zs):
                    vv=[z.r1 for z in zs]
                    if len(set(vv))>1: r.vol20=statistics.stdev(vv)
        for h in (1,5):
            vals=[getattr(r,f'r{h}') for r in by[d].values() if getattr(r,f'r{h}') is not None]
            if vals: mkt[d][f'r{h}']=statistics.median(vals)
    hh=defaultdict(lambda:deque(maxlen=60))
    for d in dates:
        mr=mkt[d].get('r1')
        for t,r in by[d].items():
            hist=hh[t]
            if len(hist)>=30:
                xs=[x for x,y in hist]; ys=[y for x,y in hist]
                xb=statistics.mean(xs); yb=statistics.mean(ys); den=sum((x-xb)**2 for x in xs)
                if den>0: r.beta60=sum((x-xb)*(y-yb) for x,y in hist)/den
            if r.beta60 is not None and r.r5 is not None and mkt[d].get('r5') is not None:
                r.resid5=r.r5-r.beta60*mkt[d]['r5']
            if mr is not None and r.r1 is not None: hist.append((mr,r.r1))
    features={}; breadth={}
    for d in dates:
        elig={t:r for t,r in by[d].items() if r.resid5 is not None and r.r20 is not None and r.r60 is not None and r.r5 is not None and r.turn20 is not None and r.vol20 is not None and r.turn20>=TURNMIN}
        if len(elig)<10: continue
        breadth[d]=sum(r.r20>0 for r in elig.values())/len(elig)
        rr=ranks({t:-r.resid5 for t,r in elig.items()}); m20=ranks({t:r.r20 for t,r in elig.items()})
        sk=ranks({t:r.r60-r.r5 for t,r in elig.items()}); liq=ranks({t:r.turn20 for t,r in elig.items()}); lv=ranks({t:-r.vol20 for t,r in elig.items()})
        features[d]={t:(rr[t],m20[t],sk[t],liq[t],lv[t]) for t in elig}
    market_vol={}
    for d in dates:
        vals=[r.vol20 for r in by[d].values() if r.vol20 is not None]
        if vals: market_vol[d]=statistics.median(vals)
    vol_hist={}
    for i,d in enumerate(dates):
        prior=[market_vol[dates[j]] for j in range(max(0,i-60),i) if dates[j] in market_vol]
        vol_hist[d]=statistics.median(prior) if len(prior)>=20 else None
    return by,dates,mkt,features,breadth,market_vol,vol_hist


def outcome(t,si,by,dates):
    ei=si+1; xi=ei+H
    if xi>=len(dates): return None
    ed,xd=dates[ei],dates[xi]; e=by[ed].get(t); x=by[xd].get(t)
    if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0: return None
    path=[]
    for j in range(ei,xi+1):
        z=by[dates[j]].get(t)
        if z is None or z.c is None or z.c<=0 or z.bad: return None
        path.append((dates[j],z.c/e.o-1))
    return x.c/e.o-1,ed,xd,path


def make_v6_cache(features):
    cache={}
    for d,F in features.items():
        arr=[(sum(V6[i]*v[i] for i in range(5)),t) for t,v in F.items()]
        arr.sort(key=lambda z:(-z[0],z[1])); cache[d]=[t for s,t in arr]
    return cache


def simulate_schedule(cache,start,end,by,dates,breadth):
    ev=[]; cens=0; next_free=-1; pending=None
    for i,d in enumerate(dates):
        if d<start or d>end or i<next_free: continue
        picks=cache.get(d,[])[:TOPN]
        if len(picks)<TOPN: continue
        xi=i+1+H
        if xi>=len(dates) or dates[xi]>end:
            pending={'signal_date':d,'reason':'INSUFFICIENT_FUTURE_SESSIONS','sessions_available_after_signal':len(dates)-i-1,'sessions_required_after_signal':H+1}
            break
        outs=[(t,outcome(t,i,by,dates)) for t in picks]
        if any(o is None for t,o in outs):
            cens+=1; next_free=xi+1; continue
        gross=statistics.mean(o[0] for t,o in outs); daily=[]
        for k in range(H+1): daily.append([outs[0][1][3][k][0],statistics.mean(o[3][k][1] for t,o in outs)])
        ev.append({'signal_date':d,'entry_date':outs[0][1][1],'exit_date':outs[0][1][2],'tickers':picks,'gross_return':gross,'daily':daily,'regime':'STRONG' if breadth[d]>=BREADTH_CUTOFF else 'WEAK','breadth20':breadth[d]})
        next_free=xi+1
    return ev,cens,pending


def target_rank(d,features,by,dates,di):
    vals={}; i=di[d]
    for t in features.get(d,{}):
        o=outcome(t,i,by,dates)
        if o is not None: vals[t]=o[0]
    return ranks(vals) if vals else {}


def make_anchors(features,breadth,by,dates,di):
    anchors=[]; next_i=-1
    for i,d in enumerate(dates):
        if d<'2023-01-01' or i<next_i or d not in features: continue
        xi=i+1+H
        if xi>=len(dates): break
        exit_date=dates[xi]
        yr=target_rank(d,features,by,dates,di); common=[t for t in features[d] if t in yr]
        if len(common)>=20:
            ics={}
            for k,f in enumerate(FACTORS):
                ics[f]=corr([features[d][t][k] for t in common],[yr[t] for t in common])
            regime='STRONG' if breadth[d]>=BREADTH_CUTOFF else 'WEAK'
            anchors.append({'signal_date':d,'exit_date':exit_date,'regime':regime,'ics':ics})
        next_i=i+H+2
    return anchors


def weights_at(signal_date,regime,anchors,for_prospective=False):
    prior=[a for a in anchors if a['exit_date']<signal_date and a['regime']==regime]
    stats=[]; diag={}
    for f in FACTORS:
        z=[a['ics'][f] for a in prior if a['ics'][f] is not None]
        mu=statistics.mean(z) if z else None; sd=statistics.stdev(z) if len(z)>1 else 0.0
        stat=max(0.0,mu/(sd+ICIR_STABILIZER)) if mu is not None else 0.0
        diag[f]={'n':len(z),'mean_ic':mu,'sd_ic':sd,'icir_stat':stat}; stats.append(stat)
    valid=min((diag[f]['n'] for f in FACTORS), default=0)
    if valid<MIN_REGIME_ANCHORS or sum(stats)<=0:
        if for_prospective:
            raise RuntimeError(f'PROSPECTIVE_FALLBACK_NOT_AUTHORIZED:{signal_date}:{regime}:valid={valid}')
        y=signal_date[:4]
        if y not in GLOBAL: raise RuntimeError(f'NO_FROZEN_GLOBAL_FALLBACK:{signal_date}')
        return list(GLOBAL[y]),diag,prior,True
    s=sum(stats); raw=[x/s for x in stats]
    w=[SHRINK_TO_V6*V6[i]+(1-SHRINK_TO_V6)*raw[i] for i in range(5)]; z=sum(w)
    return [x/z for x in w],diag,prior,False


def state_for_event(e,dates,di,breadth,mkt,market_vol,vol_hist):
    d=e['signal_date']; i=di[d]; prev_b=None
    for j in range(i-20,max(-1,i-61),-1):
        if j>=0 and dates[j] in breadth:
            prev_b=breadth[dates[j]]; break
    b=breadth.get(d,e['breadth20']); slope=(b-prev_b) if prev_b is not None else 0.0
    mv=market_vol.get(d); vh=vol_hist.get(d)
    return {'breadth20':b,'breadth_slope20':slope,'mkt5':mkt[d].get('r5'),'lowvol':(mv is not None and vh is not None and mv<=vh),'median_vol20':mv,'prior60_median_vol20':vh}


def vol_ratio(e,dates,di,breadth,mkt,market_vol,vol_hist):
    s=state_for_event(e,dates,di,breadth,mkt,market_vol,vol_hist); a=s.get('median_vol20'); b=s.get('prior60_median_vol20')
    return a/b if a is not None and b not in (None,0) else 1.0


def clip(x,lo,hi): return max(lo,min(hi,x))


def exposure(e,dates,di,breadth,mkt,market_vol,vol_hist):
    r=vol_ratio(e,dates,di,breadth,mkt,market_vol,vol_hist)
    if e['regime']=='STRONG': return 0.95 if r>1.10 else 1.0
    return clip(0.60/r,0.25,1.0)


def invert3(a):
    m=[list(map(float,row))+[1.0 if i==j else 0.0 for j in range(3)] for i,row in enumerate(a)]
    for c in range(3):
        piv=max(range(c,3),key=lambda r:abs(m[r][c]))
        if abs(m[piv][c])<1e-14: return None
        m[c],m[piv]=m[piv],m[c]; q=m[c][c]; m[c]=[x/q for x in m[c]]
        for r in range(3):
            if r==c: continue
            f=m[r][c]; m[r]=[x-f*y for x,y in zip(m[r],m[c])]
    return [row[3:] for row in m]


def uncapped_cov_weights(d,picks,dates,di,by):
    i=di[d]; series=[]
    for t in picks:
        vals=[]
        for j in range(i-19,i+1):
            if j<0: return None
            r=by[dates[j]].get(t)
            if r is None or r.r1 is None: return None
            vals.append(r.r1)
        series.append(vals)
    means=[statistics.mean(x) for x in series]
    cov=[[sum((series[a][k]-means[a])*(series[b][k]-means[b]) for k in range(20))/19 for b in range(3)] for a in range(3)]
    shr=[[cov[a][b]*((1-COV_SHRINK) if a!=b else 1.0) for b in range(3)] for a in range(3)]
    inv=invert3(shr)
    if inv is None: return None
    raw=[max(0.0,sum(inv[i][j] for j in range(3))) for i in range(3)]
    if sum(raw)<=1e-14: return None
    s=sum(raw); return [x/s for x in raw],cov,shr


def cap_weights(w,cap=CAP):
    w=[max(0.0,float(x)) for x in w]; s=sum(w)
    if s<=0: return None
    w=[x/s for x in w]
    for _ in range(12):
        over=[i for i,x in enumerate(w) if x>cap+1e-14]
        if not over: break
        excess=sum(w[i]-cap for i in over)
        for i in over: w[i]=cap
        free=[i for i,x in enumerate(w) if i not in over and x<cap-1e-14]
        if not free: return None
        base=sum(w[i] for i in free)
        if base<=1e-14:
            add=excess/len(free)
            for i in free: w[i]+=add
        else:
            for i in free: w[i]+=excess*w[i]/base
    s=sum(w)
    if s<=0: return None
    w=[x/s for x in w]
    if max(w)>cap+1e-10: return None
    return w


def predicted_sigma(e):
    w=e['weights']; s=e['shrunk_covariance']
    return math.sqrt(max(0.0,sum(w[i]*s[i][j]*w[j] for i in range(3) for j in range(3))))


def quantile(xs,q):
    a=sorted(xs)
    if not a: return None
    if len(a)==1: return a[0]
    z=(len(a)-1)*q; i=int(math.floor(z)); j=int(math.ceil(z))
    if i==j: return a[i]
    return a[i]*(j-z)+a[j]*(z-i)


def build_v43(schedule,features,anchors,by,dates,di,breadth,mkt,market_vol,vol_hist):
    out=[]; invalid=[]; prior_sigma=[]; weight_log=[]
    for b in sorted(schedule,key=lambda e:e['signal_date']):
        d=b['signal_date']; regime=b['regime']; prospective=d>LOCK_DATE
        try:
            w,diag,prior,fallback=weights_at(d,regime,anchors,for_prospective=prospective)
        except RuntimeError as exc:
            invalid.append([d,str(exc)]); continue
        F=features.get(d,{})
        arr=[(sum(w[i]*vals[i] for i in range(5)),t) for t,vals in F.items()]; arr.sort(key=lambda z:(-z[0],z[1])); picks=[t for s,t in arr[:TOPN]]
        weight_log.append({'signal_date':d,'regime':regime,'weights':dict(zip(FACTORS,w)),'prior_regime_anchors':len(prior),'fallback':fallback,'factor_icir':diag})
        if len(picks)<TOPN: invalid.append([d,'NOT_ENOUGH_PICKS']); continue
        cw=uncapped_cov_weights(d,picks,dates,di,by)
        if cw is None: invalid.append([d,'COVARIANCE_UNAVAILABLE']); continue
        uncapped,cov,shr=cw; weights=cap_weights(uncapped,CAP)
        if weights is None: invalid.append([d,'CAP_PROJECTION_FAILED']); continue
        si=di[d]; outs=[]; ok=True
        for t in picks:
            o=outcome(t,si,by,dates)
            if o is None: ok=False; break
            outs.append(o)
        if not ok: invalid.append([d,'INVALID_OUTCOME']); continue
        gross=sum(wi*o[0] for wi,o in zip(weights,outs)); daily=[]
        for k in range(H+1): daily.append([outs[0][3][k][0],sum(wi*o[3][k][1] for wi,o in zip(weights,outs))])
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':d[:4],'factor_weights':dict(zip(FACTORS,w)),'prior_regime_anchors':len(prior),'ranking_rule':'SIGNAL_TIME_EXPANDING_REGIME_PRIOR_ICIR_SHRINK_0.90'}
        e['exposure']=exposure(e,dates,di,breadth,mkt,market_vol,vol_hist); e['vol_ratio']=vol_ratio(e,dates,di,breadth,mkt,market_vol,vol_hist)
        sig=predicted_sigma(e); q75=quantile(prior_sigma,TAIL_Q) if len(prior_sigma)>=MIN_PRIOR_SIGMA else None; br=e.get('breadth20')
        fragile=(regime=='STRONG' and br is not None and BREADTH_LO<=br<BREADTH_HI); tail=(q75 is not None and sig>q75 and sig>0); mult=(q75/sig) if fragile and tail else 1.0
        e['predicted_daily_sigma']=sig; e['prior_sigma_q75']=q75; e['fragile_strong']=fragile; e['tail_vol']=tail; e['risk_multiplier']=mult; e['base_exposure']=e['exposure']; e['exposure']=e['base_exposure']*mult
        out.append(e); prior_sigma.append(sig)
    return out,invalid,weight_log


def event_bytes(events):
    return ''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events).encode('utf-8')


def extract_frozen_events(archive_path: Path):
    with tarfile.open(archive_path,'r:gz') as tf:
        member=next(m for m in tf.getmembers() if m.name.endswith('/artifacts/hengce-ranking-v43-expanding-regime-icir.zip'))
        artifact=tf.extractfile(member).read()
    with zipfile.ZipFile(io.BytesIO(artifact)) as zf:
        raw=zf.read('ranking_v43_events.jsonl')
    if hashlib.sha256(raw).hexdigest()!=EXPECTED_PRELOCK_EVENTS_SHA256:
        raise RuntimeError('ARCHIVED_PRELOCK_EVENTS_HASH_DRIFT')
    return [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]


def product(xs):
    n=1.0
    for x in xs: n*=1+x
    return n-1


def summarize(events,cost):
    nets=[]; nav=1.0; peak=1.0; mdd=0.0
    for e in events:
        ex=e['exposure']; net=ex*(e['gross_return']-cost); nets.append(net); base=nav
        for j,(d,r) in enumerate(e['daily']):
            temp=base*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0)); peak=max(peak,temp); mdd=min(mdd,temp/peak-1)
        nav=base*(1+net)
    bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'max_single_name_weight':max((max(e['weights']) for e in events),default=None),'mean_exposure':statistics.mean([e['exposure'] for e in events]) if events else None}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--historical-gz',type=Path,default=HIST_DEFAULT)
    ap.add_argument('--current-csv',type=Path,default=CURR_DEFAULT)
    ap.add_argument('--archive',type=Path,default=ARCHIVE_DEFAULT)
    ap.add_argument('--output',type=Path,default=OUT_DEFAULT)
    args=ap.parse_args()

    result={'protocol':'V43_CLEAN_PROSPECTIVE_OBSERVER_V2','lock_date':LOCK_DATE,'lock_commit':LOCK_COMMIT,'authority':AUTHORITY}
    actual_blob=git_blob_sha(V43_SOURCE)
    result['frozen_v43_source']={'expected_blob_sha':EXPECTED_V43_BLOB_SHA,'actual_blob_sha':actual_blob,'verified':actual_blob==EXPECTED_V43_BLOB_SHA}
    if actual_blob!=EXPECTED_V43_BLOB_SHA:
        result['status']='FROZEN_MODEL_DRIFT'; args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(2)

    frozen=extract_frozen_events(args.archive); frozen_dates={e['signal_date'] for e in frozen}
    by,dates,mkt,features,breadth,market_vol,vol_hist=build_state(args.historical_gz,args.current_csv); di={d:i for i,d in enumerate(dates)}
    if not dates:
        raise SystemExit('NO_DATES')
    data_max=dates[-1]
    result['data_snapshot']={'current_csv_sha256':sha256_path(args.current_csv),'data_max_date':data_max}
    cache=make_v6_cache(features); anchors=make_anchors(features,breadth,by,dates,di)

    s24,_,_=simulate_schedule(cache,'2024-01-01','2024-12-31',by,dates,breadth)
    s25,_,_=simulate_schedule(cache,'2025-01-01','2025-12-31',by,dates,breadth)
    s26f,_,_=simulate_schedule(cache,'2026-01-01',BASELINE_2026_CUTOFF,by,dates,breadth)
    frozen_schedule=s24+s25+s26f
    frozen_rebuilt,frozen_invalid,_=build_v43(frozen_schedule,features,anchors,by,dates,di,breadth,mkt,market_vol,vol_hist)
    rebuilt_hash=hashlib.sha256(event_bytes(frozen_rebuilt)).hexdigest()
    parity=(len(frozen_rebuilt)==EXPECTED_PRELOCK_EVENT_COUNT and rebuilt_hash==EXPECTED_PRELOCK_EVENTS_SHA256 and max((e['exit_date'] for e in frozen_rebuilt),default=None)==EXPECTED_PRELOCK_LAST_EXIT and not frozen_invalid)
    result['parity_gate']={'verified':parity,'rebuilt_event_count':len(frozen_rebuilt),'rebuilt_events_sha256':rebuilt_hash,'expected_event_count':EXPECTED_PRELOCK_EVENT_COUNT,'expected_events_sha256':EXPECTED_PRELOCK_EVENTS_SHA256,'invalid':frozen_invalid,'last_exit':max((e['exit_date'] for e in frozen_rebuilt),default=None)}
    if not parity:
        result['status']='HISTORICAL_PARITY_FAILURE'; args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(3)

    dynamic_end=data_max
    s26,_,pending=simulate_schedule(cache,'2026-01-01',dynamic_end,by,dates,breadth)
    dynamic_schedule=s24+s25+s26
    dynamic_events,dynamic_invalid,weight_log=build_v43(dynamic_schedule,features,anchors,by,dates,di,breadth,mkt,market_vol,vol_hist)
    frozen_subset=[e for e in dynamic_events if e['signal_date'] in frozen_dates]
    frozen_subset_hash=hashlib.sha256(event_bytes(frozen_subset)).hexdigest()
    if frozen_subset_hash!=EXPECTED_PRELOCK_EVENTS_SHA256:
        result['status']='DYNAMIC_HISTORY_DRIFT'; result['dynamic_frozen_subset_sha256']=frozen_subset_hash; args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(4)

    bridge=[e for e in dynamic_events if e['signal_date']<=LOCK_DATE and e['signal_date'] not in frozen_dates]
    post=[e for e in dynamic_events if e['signal_date']>LOCK_DATE]
    post_invalid=[x for x in dynamic_invalid if x[0]>LOCK_DATE]
    if post_invalid:
        result['status']='POSTLOCK_RULE_EXECUTION_FAILURE'; result['postlock_invalid']=post_invalid; args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(5)

    n=len(post)
    if n==0:
        if pending and pending['signal_date']>LOCK_DATE: status='WAITING_FOR_COMPLETE_POST_LOCK_OUTCOME'
        else: status='WAITING_FOR_POST_LOCK_DATA'
    elif n<INTERIM_N: status='ACCUMULATING_POST_LOCK_BASKETS'
    elif n<PRIMARY_N: status='INTERIM_REVIEW_ELIGIBLE'
    else: status='PRIMARY_REVIEW_ELIGIBLE'

    monitoring={str(c):summarize(post,c) for c in COSTS} if post else None
    interim=post[:INTERIM_N]; primary=post[:PRIMARY_N]
    interim_metrics={str(c):summarize(interim,c) for c in COSTS} if len(interim)==INTERIM_N else None
    primary_metrics={str(c):summarize(primary,c) for c in COSTS} if len(primary)==PRIMARY_N else None
    gate=None
    if primary_metrics is not None:
        c12=primary_metrics['0.012']; c16=primary_metrics['0.016']
        gate=bool(c12['compounded_return']>0 and c12['remove_best_basket_return']>0 and c12['max_drawdown']>=-0.30 and c16['compounded_return']>0)
    regime={}
    for g in ('STRONG','WEAK'):
        xs=[e for e in post if e['regime']==g]
        regime[g]={str(c):summarize(xs,c) for c in COSTS} if xs else None

    result.update({
        'status':status,
        'new_model_evaluations':0,
        'parameters_searched':0,
        'historical_selection_rerun':False,
        'frozen_baseline_event_count':len(frozen),
        'dynamic_frozen_subset_sha256':frozen_subset_hash,
        'bridge_prelock_completed_baskets':[{'signal_date':e['signal_date'],'entry_date':e['entry_date'],'exit_date':e['exit_date']} for e in bridge],
        'pending_schedule_candidate':pending,
        'postlock_complete_baskets':n,
        'postlock_signal_dates':[e['signal_date'] for e in post],
        'monitoring_all_postlock':monitoring,
        'regime_monitoring':regime,
        'registered_interim_first_6':interim_metrics,
        'registered_primary_first_12':primary_metrics,
        'registered_primary_gate_pass':gate,
        'registered_primary_gate':{'window':'first 12 complete post-lock baskets only','cost_0.012_compounded_return_gt':0,'cost_0.012_remove_best_basket_return_gt':0,'cost_0.012_max_drawdown_gte':-0.30,'cost_0.016_compounded_return_gt':0},
        'daily_path_preserved':True,
        'postlock_events':post,
        'postlock_weight_log':[x for x in weight_log if x['signal_date']>LOCK_DATE],
        'caveat':'Validation-only. A pass never authorizes capital, broker orders, production promotion, Q017/E2/M1 changes, main writes, PR #30 merge, local retuning, or V45.',
    })
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
