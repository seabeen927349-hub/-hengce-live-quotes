#!/usr/bin/env python3
"""HENGCE marketwide FinMind vs frozen OFFICIAL TDCC overlap QA (research only).

Compare Big400/Big1000 pct, shares, holders for every overlapping
security in one identical official 2025 weekly snapshot.
Do not store or print raw premium API rows.
"""
import csv,json,os,sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from hengce_finmind_tdcc_marketwide_year import get_full_market
from hengce_finmind_tdcc_crosscheck import normalized_lower_bound

DAY='2025-11-07'
OFFICIAL=ROOT/'ownership/tdcc/backfill_candidate/full_market_2025_tail/20251107/tdcc_ownership_4d.csv'
OUT=Path('/tmp/hengce-finmind-fullmarket-official-qa/receipt.json')
FIELDS=['Big400','Big1000']
def main():
    report={'artifact':'HENGCE_FINMIND_OFFICIAL_MARKETWIDE_CROSSCHECK_V1',
            'refdate':DAY,'research_only':True,
            'observed_utc':datetime.now(timezone.utc).isoformat(),
            'raw_finmind_rows_persisted':False,'original_official_rows_modified':False,
            'status':'BLOCKED'}
    try:
        token=os.getenv('FINMIND_TOKEN','').strip()
        if not token:raise RuntimeError('TOKEN_MISSING')
        rows,meta=get_full_market(token,DAY)
        by=defaultdict(list)
        for x in rows:by[str(x['stock_id'])].append(x)
        with OFFICIAL.open('r',encoding='utf-8',newline='') as f:
            auth={r['Ticker']:r for r in csv.DictReader(f) if r['SnapshotDate']=='20251107'}
        if len(auth)<2500:raise RuntimeError('OFFICIAL_SOURCE_UNEXPECTEDLY_SMALL')
        result={'official':len(auth),'finmind_codes':len(by),'matched':0,'missing_finmind':[],
                'schema_fail':[],'value_fail':[],'exact_both':0,'pct_within_01_and_shares_exact':0}
        max_abs_pct=0
        for ticker,official in auth.items():
            data=by.get(ticker)
            if not data:
                result['missing_finmind'].append(ticker)
                continue
            high=[];top=[]
            for row in data:
                low=normalized_lower_bound(str(row['HoldingSharesLevel']))
                if low is None:continue
                if low>=400001:high.append(row)
                if low>=1000001:top.append(row)
            if len(high)!=4 or len(top)!=1:
                result['schema_fail'].append({'ticker':ticker,'high_tier_count':len(high),'top_tier_count':len(top)})
                continue
            result['matched']+=1
            diffs={}
            for typ,subset in [('Big400',high),('Big1000',top)]:
                expected={
                    'pct':float(official[typ+'Pct']),
                    'shares':int(official[typ+'Shares']),
                    'holders':int(official[typ+'Holders'])}
                actual={'pct':sum(float(r['percent']) for r in subset),
                        'shares':sum(int(r['unit']) for r in subset),
                        'holders':sum(int(r['people']) for r in subset)}
                diffs[typ]={field:actual[field]-expected[field] for field in actual}
                max_abs_pct=max(max_abs_pct,abs(diffs[typ]['pct']))
            exact=all(abs(v['pct'])<1e-8 and v['shares']==0 and v['holders']==0 for v in diffs.values())
            within=all(abs(v['pct'])<=.1 and v['shares']==0 and v['holders']==0 for v in diffs.values())
            if exact: result['exact_both']+=1
            if within: result['pct_within_01_and_shares_exact']+=1
            else:result['value_fail'].append({'ticker':ticker,'deltas':diffs})
        report.update(result)
        report['max_pct_difference']=max_abs_pct
        report['matched_coverage']=round(result['matched']/len(auth),6)
        report['status']='PASS_FULLMARKET' if result['matched']==len(auth) and not result['schema_fail'] and not result['value_fail'] else 'RESEARCH_PARTIAL_DIAGNOSTIC'
    except Exception as e:
        report['status']='BLOCKED'
        report['error']=str(e).splitlines()[0][:200]
    finally:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        # Fail examples are capped in the printed log only, not the receipt.
        OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('HENGCE_FINMIND_OFFICIAL_MARKET_QA',report['status'],
              'official',report.get('official'),'matched',report.get('matched'),
              'exact',report.get('exact_both'),'within',report.get('pct_within_01_and_shares_exact'),
              'missing',len(report.get('missing_finmind',[])),
              'schema_fail',len(report.get('schema_fail',[])),
              'value_fail',len(report.get('value_fail',[])),
              'error',report.get('error',''),flush=True)
    return 0 if report['status']=='PASS_FULLMARKET' else 2
if __name__=='__main__':raise SystemExit(main())
