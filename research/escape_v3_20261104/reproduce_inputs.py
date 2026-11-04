"""Verify immutable artifacts and rebuild reported-margin sensitivity from strict replay."""
from pathlib import Path
import hashlib,json
import numpy as np,pandas as pd

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(inputs, strict, output):
    inputs,strict,output=map(Path,(inputs,strict,output)); output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((inputs/'margin_repair_manifest.json').read_text())
    hashes={}
    for name,item in manifest['files'].items():
        p=inputs/'data'/name; hashes[name]=sha(p); assert hashes[name]==item['sha256'],name
    mother=pd.read_csv(inputs/'data/research_combined_mother_2023_2026_oct27.csv',dtype={'Ticker':str})
    e=pd.read_csv(inputs/'data/electronics_observed_membership_2023_2026_oct27.csv',dtype={'ticker':str})
    patch=pd.read_csv(inputs/'data/margin_backfill_patch_2023_2025.csv',dtype={'Ticker':str})
    assert not patch.duplicated(['Date','Ticker']).any()
    joined=patch.merge(mother,on=['Date','Ticker'],validate='one_to_one',suffixes=('_patch','_mother'))
    assert len(joined)==len(patch)==702055
    assert np.array_equal(joined.Margin_MarginBalance_patch,joined.Margin_MarginBalance_mother)
    x=pd.read_csv(strict/'historical_17_metric_research_shadow.csv').set_index('Date')
    savedstrict=pd.read_csv(inputs/'results/replay/historical_17_metric_research_shadow.csv').set_index('Date')
    pd.testing.assert_frame_equal(x,savedstrict,check_exact=False,rtol=1e-10,atol=1e-11)
    e=e[e.ticker.str.fullmatch(r'[1-9]\d{3}')]
    joined=e[['date','ticker']].merge(mother,left_on=['date','ticker'],right_on=['Date','Ticker'],validate='one_to_one')
    balance=joined.groupby('Date').Margin_MarginBalance.sum(min_count=1)
    x['vulnerability_leverage_score_raw']=balance/balance.shift(20)-1
    metrics=list(x.columns[:17])
    ready=pd.DataFrame({m:x[m].notna() & x[m].notna().shift(1,fill_value=False).rolling(60,min_periods=1).sum().ge(40) for m in metrics})
    x['complete_metric_count']=x[metrics].notna().sum(axis=1)
    x['eligible_past40_17_count']=ready.sum(axis=1);x['all17_ready_research']=ready.all(axis=1)
    saved=pd.read_csv(inputs/'results/reported_margin_sensitivity/historical_17_metric_reported_margin_research.csv').set_index('Date')
    pd.testing.assert_frame_equal(x,saved,check_exact=False,rtol=1e-10,atol=1e-11)
    assert len(x)==919 and x.complete_metric_count.eq(17).sum()==889 and x.all17_ready_research.sum()==849
    # Independently reconstruct daily E chain and broad-market breadth from price rows.
    normal=mother.Ticker.str.fullmatch(r'[1-9][0-9]{3}') & ~mother.Name.fillna('').str.contains('-DR$',case=False,regex=True)
    m=mother[normal].copy(); m['Close']=pd.to_numeric(m.Close,errors='coerce'); c=m.pivot(index='Date',columns='Ticker',values='Close').reindex(x.index).where(lambda a:a>0)
    membership=pd.crosstab(e.date,e.ticker).reindex(index=c.index,columns=c.columns,fill_value=0).gt(0)
    r=c.pct_change(fill_method=None).where(membership & membership.shift(1,fill_value=False)).mean(axis=1)
    ma=c.rolling(20,min_periods=20).mean();valid=c.notna() & ma.notna()
    breadth=((c>ma)&valid).sum(axis=1)/valid.sum(axis=1).replace(0,np.nan)
    extras=pd.DataFrame({'Date':x.index,'e_daily_return':r.to_numpy(),'broad_ma20_breadth':breadth.to_numpy()})
    for h in (5,10,20):
        f=(1+r).rolling(h).apply(np.prod,raw=True).shift(-h)-1
        assert np.allclose(f,x[f'electronics_ew_daily_chain_fwd_{h}'],equal_nan=True,rtol=1e-10,atol=1e-11)
    x.to_csv(output/'recomputed_metrics.csv',index_label='Date',float_format='%.12g');extras.to_csv(output/'independent_price_series.csv',index=False)
    report={'hashes':hashes,'sessions':len(x),'complete17':int(x.complete_metric_count.eq(17).sum()),'baseline40':int(x.all17_ready_research.sum()),'patch_rows':len(patch),'patch_matches_repaired_rows':len(patch),'strict_replay_matches':True,'reported_replay_matches':True,'labels_independently_recomputed':True,'raw_TWSE_pre_repair_sources_present':False,'restoration_provenance_limitation':'Patch membership and values verified against repaired panel; original pre-repair mother and raw TWSE source not in these archives, so original-null status and upstream official provenance are not independently re-proven.'}
    (output/'input_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('inputs');p.add_argument('strict');p.add_argument('output');a=p.parse_args();print(json.dumps(run(a.inputs,a.strict,a.output),indent=2))
