#!/usr/bin/env python3
"""Build an isolated HENGCE TDCC weekly Big400/Big1000 sidecar from paid FinMind archives.

Input: 8 private GH Actions artifacts, one directory per year, with validated
YYYY-MM-DD.json.gz source-tier rows and manifest.json.
Do not publish underlying licensed data in GitHub. Do not alter production.
PIT: ReferenceDate + 7 calendar days is a conservative *proxy*, not proof
of actual historical publication or FinMind data first-seen time.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,re
from collections import defaultdict
from datetime import date,timedelta,datetime,timezone
from pathlib import Path

COMMON=re.compile(r'^[1-9][0-9]{3}$')
def digest(b):return hashlib.sha256(b).hexdigest()
def bound(value):
    s=re.sub(r'[,，\s股]','',str(value)).replace('～','-').replace('~','-')
    if '差異數調整' in s or '合計' in s or '總計' in s or s.lower()=='total':return None
    en=re.match(r'^morethan([0-9]+)$',s.lower())
    if en:return int(en.group(1))
    m=re.match(r'^([0-9]+)(?:-|以上|及以上|\+)',s)
    return int(m.group(1)) if m else None

FIELDS=['SnapshotDate','Ticker','Big400Pct','Big400Shares','Big400Holders',
        'Big1000Pct','Big1000Shares','Big1000Holders','Quality',
        'HistoricalAvailableDateProxy','SourceObservedAtUTC','SourceVendor']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    root=Path(a.root);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    log={'schema':'HENGCE_FINMIND_TDCC_WEEKLY_4TH_LEG_RESEARCH_V1','years':{},
         'status':'BLOCKED','input_type':'FinMind licensed vendor historical tier rows',
         'effective_date_rule':'SnapshotDate + 7 calendar days RESEARCH PROXY ONLY',
         'historical_first_seen_proven':False,'ordinary_stock_PIT_universe_joined':False,
         'production_canonical_mutated':False,'model_authority':False,'trading_authority':False}
    seen=set();missing=[];rows_total=0;good_total=0;date_set=set()
    csv_path=out/'HENGCE_TDCC_FINMIND_2018_2025_WEEKLY_BIG400_BIG1000_RESEARCH.csv.gz'
    try:
        with gzip.open(csv_path,'wt',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS)
            w.writeheader()
            for yr in range(2018,2026):
                folder=root/str(yr)
                manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
                if manifest.get('status')!='PASS' or manifest.get('year')!=yr:
                    raise RuntimeError(f'YEAR_MANIFEST_NOT_PASS_{yr}')
                if manifest.get('snapshots_completed')!=manifest.get('verified_weekly_calendar_count'):
                    raise RuntimeError(f'YEAR_CALENDAR_INCOMPLETE_{yr}')
                ystats={'snapshots':0,'candidate_security_snapshots':0,
                        'big_tier_pass':0,'big_tier_unresolved':0,'tier_rows':0,'anomalous_metadata':0}
                for item in manifest['snapshots']:
                    ds=item['reference_date']
                    saved=(folder/item['file']).read_bytes()
                    if digest(saved)!=item['gzip_sha256']:raise RuntimeError(f'SNAPSHOT_SHA_MISMATCH_{yr}_{ds}')
                    source=json.loads(gzip.decompress(saved))
                    if len(source)!=item['tier_rows']:raise RuntimeError(f'ROW_COUNT_MISMATCH_{yr}_{ds}')
                    ystats['tier_rows']+=len(source)
                    ystats['anomalous_metadata']+=item.get('non_tier_summary_anomaly_count',0)
                    by=defaultdict(list)
                    for row in source:
                        ticker=str(row.get('stock_id','')).strip()
                        if str(row.get('date',''))!=ds:raise RuntimeError(f'SNAPSHOT_DATE_MISMATCH_{yr}_{ds}')
                        if COMMON.fullmatch(ticker):by[ticker].append(row)
                    for ticker,group in by.items():
                        key=(ds,ticker)
                        if key in seen:raise RuntimeError(f'DUPLICATE_DATE_TICKER_{ds}_{ticker}')
                        seen.add(key)
                        highs=[];tops=[]
                        for row in group:
                            low=bound(row.get('HoldingSharesLevel'))
                            if low is None:continue
                            if low>=400001:highs.append(row)
                            if low>=1000001:tops.append(row)
                        output={'SnapshotDate':ds.replace('-',''),'Ticker':ticker,
                          'HistoricalAvailableDateProxy':(date.fromisoformat(ds)+timedelta(days=7)).isoformat(),
                          'SourceObservedAtUTC':item['first_observed_utc'],
                          'SourceVendor':'FinMind',
                          'Quality':'VALID'}
                        if len(highs)==4 and len(tops)==1:
                            for k,part in [('Big400',highs),('Big1000',tops)]:
                                pp=[float(x['percent']) for x in part]
                                shares=[int(x['unit']) for x in part]
                                persons=[int(x['people']) for x in part]
                                if not all(0<=v<=100 for v in pp) or min(shares)<0 or min(persons)<0:
                                    raise RuntimeError(f'SIGNED_TRUE_HOLDING_TIER_{ds}_{ticker}')
                                output[k+'Pct']=round(sum(pp),6)
                                output[k+'Shares']=sum(shares)
                                output[k+'Holders']=sum(persons)
                            ystats['big_tier_pass']+=1;good_total+=1
                        else:
                            output['Quality']='INCOMPLETE_OR_UNKNOWN_GRADE'
                            ystats['big_tier_unresolved']+=1
                            if len(missing)<50:missing.append({'date':ds,'ticker':ticker,'high':len(highs),'top':len(tops)})
                        w.writerow(output)
                        ystats['candidate_security_snapshots']+=1;rows_total+=1
                    ystats['snapshots']+=1;date_set.add(ds)
                log['years'][str(yr)]=ystats
                print('HENGCE_FINMIND_TDCC_MERGE_YEAR',yr,json.dumps(ystats),flush=True)
        if len(log['years'])!=8 or len(date_set)<390 or good_total/rows_total<.98:
            raise RuntimeError(f'MERGE_QUALITY_FAIL year={len(log["years"])} dates={len(date_set)} valid_ratio={good_total/rows_total:.4f}')
        log.update(status='PASS_RESEARCH_CANDIDATE',snapshot_count=len(date_set),
            candidate_date_ticker_rows=rows_total,valid_big400_big1000_rows=good_total,
            unresolved_rows=rows_total-good_total,unresolved_examples=missing,
            research_gzip_sha256=digest(csv_path.read_bytes()),
            finished_utc=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        log.update(status='BLOCKED_FAIL_CLOSED',blocker=str(exc).splitlines()[0][:200])
        print('HENGCE_TDCC_MERGE_ERROR',log['blocker'],flush=True)
    finally:
        (out/'HENGCE_TDCC_FINMIND_RESEARCH_SIDECAR_MANIFEST.json').write_text(
          json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('HENGCE_TDCC_FINMIND_MERGE_STATUS',log['status'],'rows',rows_total,'good',good_total,'dates',len(date_set),flush=True)
    return 0 if log['status']=='PASS_RESEARCH_CANDIDATE' else 2

if __name__=='__main__':raise SystemExit(main())
