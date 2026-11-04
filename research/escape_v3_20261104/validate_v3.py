#!/usr/bin/env python3
"""Single frozen retrospective experiment. Signals and outcomes computed separately."""
from pathlib import Path
import sys,json,hashlib,platform
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import HENGCE_ESCAPE_FEATURE_DETECTOR_V1 as detector
import HENGCE_ESCAPE_STATE_ENGINE_V2 as v2
from HENGCE_ESCAPE_STATE_ENGINE_V3_RESEARCH import ResearchStateEngine
OUT=Path(__file__).parent/'results'
TARGETS={5:-.03,10:-.05,20:-.05}
GATES={k:False for k in ('freshness_pass','integrity_pass','pit_pass','universe_pass')}

def packet(x,i):
    # 66 = 60 baseline + 6 persistence observations. No label columns supplied.
    h=x.iloc[max(0,i-65):i+1]
    return {'trade_date':str(x.Date.iat[i]),'session_index':i,'phase':'EOD_FORMAL',
            'research_only':True,'source_integrity_verified':True,'data_gate':GATES,
            'metric_contract_version':detector.METRIC_CONTRACT_VERSION,
            'metric_contract_sha256':detector.METRIC_CONTRACT_SHA256,
            'metrics_history':{m:[None if pd.isna(v) else float(v) for v in h[m]] for m in detector.METRICS}}

def signals(x):
    engine=ResearchStateEngine();prev=0;rows=[];parity=[]
    for i in range(len(x)):
        p=packet(x,i);res=engine.evaluate(p)
        row={'Date':p['trade_date'],'raw':res['raw_risk_level'],'v3':res['persistent_state_level'],'v2':None,'transition':res.get('transition'),'recovery5':False}
        if res['status']=='RESEARCH_ONLY_COUNTERFACTUAL':
            synthetic=dict(p,data_gate={k:True for k in GATES},detector_output=res['detector_output'],prior_level=prev)
            old=v2.evaluate(synthetic);prev=old['escape_level'];row['v2']=prev
            row['recovery5']=old['recovery_confirmed']
            # Literal frozen V1 full-history execution parity at fixed calendar positions.
            if i % 100 == 0 or i==len(x)-1:
                full=dict(synthetic,metrics_history={m:[None if pd.isna(v) else float(v) for v in x[m].iloc[:i+1]] for m in detector.METRICS})
                d=detector.detect(full)
                assert d['events']==res['detector_output']['events']
                assert d['family_scores']==res['detector_output']['family_scores']
                parity.append(i)
        rows.append(row)
    return pd.DataFrame(rows),parity

def confusion(a,y):
    a=np.asarray(a,dtype=bool);y=np.asarray(y,dtype=bool)
    tp=int((a&y).sum());fp=int((a&~y).sum());fn=int((~a&y).sum());tn=int((~a&~y).sum())
    def ratio(n,d):return n/d if d else None
    return dict(n=len(a),alerts=int(a.sum()),events=int(y.sum()),tp=tp,fp=fp,fn=fn,tn=tn,
                precision=ratio(tp,tp+fp),false_discovery_rate=ratio(fp,tp+fp),
                false_positive_rate=ratio(fp,fp+tn),recall=ratio(tp,tp+fn),prevalence=ratio(tp+fn,len(a)))

def episode_indices(returns,h,threshold):
    # Outcome-only, greedy nonoverlapping intervals. Selection cannot see signals.
    out=[];i=0
    while i+h<len(returns):
        path=np.cumprod(1+returns[i+1:i+h+1])-1
        if np.isfinite(path).all() and path[-1]<=threshold:
            crossing=np.flatnonzero(path<=threshold)[0]+i+1
            out.append((i,i+h,int(crossing)));i+=h
        else:i+=1
    return out

def events_eval(panel,valid,signal,h):
    r=panel.e_daily_return.to_numpy();events=[]
    for start,end,cross in episode_indices(r,h,TARGETS[h]):
        if not valid[start]:continue
        hits=np.flatnonzero(panel[signal].iloc[start:cross].to_numpy(bool))
        events.append({'anchor':panel.Date.iat[start],'end':panel.Date.iat[end],
                       'crossing':panel.Date.iat[cross],'detected':bool(len(hits)),
                       'lead_sessions':int(cross-start-hits[0]) if len(hits) else None})
    leads=[e['lead_sessions'] for e in events if e['detected']]
    return {'episodes':len(events),'detected':len(leads),'recall':len(leads)/len(events) if events else None,
            'median_lead_sessions':float(np.median(leads)) if leads else None,'events':events}

def bootstrap(panel,valid,a,b,h):
    d=panel.loc[valid];rng=np.random.default_rng(20261104);samples=[]
    y=d[f'fwd{h}'].le(TARGETS[h]).to_numpy();aa=d[a].to_numpy(bool);bb=d[b].to_numpy(bool)
    groups=[np.flatnonzero(d.Date.str[:4].eq(year).to_numpy()) for year in sorted(d.Date.str[:4].unique())]
    for _ in range(2500):
        picks=[]
        for ix in groups:
            n=len(ix); block=min(h,n);starts=rng.integers(0,n-block+1,size=int(np.ceil(n/block)))
            picks.extend(np.concatenate([ix[s:s+block] for s in starts])[:n])
        z=np.asarray(picks);ap=aa[z];bp=bb[z];yp=y[z]
        if ap.any() and bp.any(): samples.append(float(yp[ap].mean()-yp[bp].mean()))
    # Familywise 5%, six preregistered comparisons; descriptive ordinary CI also retained.
    return {'replicates':2500,'valid':len(samples),'block':h,'seed':20261104,
            'ci95':np.quantile(samples,[.025,.975]).tolist() if samples else None,
            'ci_familywise95':np.quantile(samples,[.05/12,1-.05/12]).tolist() if samples else None}

def main():
    x=pd.read_csv(OUT/'recomputed_metrics.csv');price=pd.read_csv(OUT/'independent_price_series.csv')
    # Deliberately discard all forward-return columns before computing any signals.
    safe=x[['Date']+list(detector.METRICS)].copy()
    s,parity=signals(safe)
    legacy=pd.read_csv(Path(sys.argv[1])/'results/daily_provisional_reconstruction.csv')
    assert s.Date.equals(legacy.Date)
    assert np.allclose(s.raw,legacy.research_raw_level,equal_nan=True)
    assert np.allclose(s.v2,legacy.research_stateful_level,equal_nan=True)
    prefix,_=signals(safe.iloc[:800].copy());pd.testing.assert_frame_equal(prefix,s.iloc[:800].reset_index(drop=True))
    panel=s.merge(price,on='Date',validate='one_to_one')
    r=panel.e_daily_return
    panel['momentum']=(1+r).rolling(20).apply(np.prod,raw=True).sub(1).lt(0)
    panel['market_breadth']=panel.broad_ma20_breadth.lt(.5)
    panel['always']=True
    for name in ('raw','v2','v3'):
        panel[name+'_ge2']=panel[name].ge(2)
        for level in range(1,7):
            panel[f'{name}_eq{level}']=panel[name].eq(level)
            panel[f'{name}_ge{level}']=panel[name].ge(level)
    cols=['raw_ge2','v2_ge2','v3_ge2','momentum','market_breadth','always']
    levelcols=[f'{s}_{kind}{l}' for s in ('raw','v2','v3') for kind in ('eq','ge') for l in range(1,7)]
    results=[];episodes={};boots={};checks=[]
    for h,threshold in TARGETS.items():
        panel[f'fwd{h}']=(1+r).rolling(h).apply(np.prod,raw=True).shift(-h)-1
        end=panel.Date.shift(-h)
        base=panel.raw.notna() & panel[f'fwd{h}'].notna() & panel.Date.lt('2026-10-08')
        # Purge labels across year boundaries and ALL outcomes touching unreconciled interval.
        strict=base & end.lt('2026-10-08') & panel.Date.str[:4].eq(end.str[:4])
        for year in ('2023','2024','2025','2026','2025_2026'):
            period=panel.Date.str[:4].isin(['2025','2026']) if year=='2025_2026' else panel.Date.str.startswith(year)
            v=(strict&period).to_numpy()
            for sig in list(dict.fromkeys(cols+levelcols)):
                row=confusion(panel.loc[v,sig],panel.loc[v,f'fwd{h}'].le(threshold))
                row.update(period=year,horizon=h,signal=sig,sample='purged_daily');results.append(row)
                # Fixed anchor on full 919-session calendar, identical observations for all signals.
                nv=v & (np.arange(len(panel))%h==0)
                row=confusion(panel.loc[nv,sig],panel.loc[nv,f'fwd{h}'].le(threshold))
                row.update(period=year,horizon=h,signal=sig,sample='nonoverlap_calendar');results.append(row)
            for sig in cols:
                episodes[f'{year}/{h}/{sig}']=events_eval(panel,v,sig,h)
        pooled=(strict&panel.Date.ge('2025-01-01')).to_numpy()
        for comparator in ('momentum','market_breadth'):
            boots[f'{h}/{comparator}']=bootstrap(panel,pooled,'v3_ge2',comparator,h)
            ci=boots[f'{h}/{comparator}']['ci_familywise95'];checks.append(bool(ci and ci[0]>0))
            for year in ('2025','2026'):
                def row(sig):return next(z for z in results if z['period']==year and z['horizon']==h and z['signal']==sig and z['sample']=='purged_daily')
                a,b=row('v3_ge2'),row(comparator)
                checks.append(all(a[k] is not None and b[k] is not None for k in ('precision','false_positive_rate','recall')) and a['precision']>b['precision'] and a['false_positive_rate']<=b['false_positive_rate'])
                ae,be=episodes[f'{year}/{h}/v3_ge2'],episodes[f'{year}/{h}/{comparator}']
                checks.append(ae['recall'] is not None and be['recall'] is not None and ae['recall']>=be['recall'])
        # Legacy reproduction retains old split/cutoff to explain changed denominator.
        lv=(base&panel.Date.ge('2025-01-01')).to_numpy()
        for sig in cols:
            row=confusion(panel.loc[lv,sig],panel.loc[lv,f'fwd{h}'].le(threshold));row.update(period='2025_2026',horizon=h,signal=sig,sample='legacy_unpurged');results.append(row)
    report={'decision':'GO_RESEARCH_ONLY' if all(checks) else 'NO-GO','formal_decision':'NO-GO',
            'trading_authority':'NONE','prospective_oos':False,'optimization_runs':0,'candidate_specs_tested':1,
            'predictive_gates_passed':sum(checks),'predictive_gates_total':len(checks),
            'legacy_raw_and_v2_exact_parity':True,'full_prefix_detector_parity_indices':parity,
            'prefix_800_signal_invariance':True,'v2_first_L6':panel.loc[panel.v2.eq(6),'Date'].min(),
            'v2_2025_2026_L6':int((panel.Date.ge('2025-01-01')&panel.v2.eq(6)).sum()),
            'v3_2025_2026_L6':int((panel.Date.ge('2025-01-01')&panel.v3.eq(6)).sum()),
            'recovery5_days':int(panel.recovery5.sum()),
            'state_counts':{s:{str(k):int(v) for k,v in panel.loc[panel.Date.ge('2025-01-01'),s].value_counts().sort_index().items()} for s in ('raw','v2','v3')},
            'limitations':['Historical temporal splits only; all data predate design freeze','PIT U and margin eligibility not independently certified','Source revisions excluded, not resolved','Unadjusted close-price returns may include corporate-action distortions; no verified total-return series','Original pre-repair raw sources absent from supplied archives','Few independent adverse episodes','No claim of live V2 latching'],
            'runtime':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__}}
    pd.DataFrame(results).to_csv(OUT/'comparison_metrics.csv',index=False)
    panel.to_csv(OUT/'daily_v2_v3.csv',index=False)
    for file,obj in [('decision.json',report),('event_recall_lead_times.json',episodes),('paired_block_bootstrap.json',boots)]:
        (OUT/file).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
