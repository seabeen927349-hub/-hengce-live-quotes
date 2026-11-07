#!/usr/bin/env python3
"""Investigate FinMind weekly holding rows with signed values; metadata-only log."""
import json,os,urllib.parse,urllib.request,datetime
from pathlib import Path
DAY='2023-04-21'
OUT=Path('/tmp/hengce-finmind-2023-anomaly/receipt.json')
def main():
    token=os.environ.get('FINMIND_TOKEN','').strip()
    q=urllib.parse.urlencode({'dataset':'TaiwanStockHoldingSharesPer','start_date':DAY})
    req=urllib.request.Request('https://api.finmindtrade.com/api/v4/data?'+q,headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=180) as f: o=json.load(f)
    data=o.get('data',[])
    cases=[];by_level={}
    for r in data:
        lev=str(r.get('HoldingSharesLevel',''))
        try:p=float(r.get('percent'));n=int(r.get('people'));u=int(r.get('unit'))
        except Exception as e:
            cases.append({'kind':'PARSE','level':lev,'ticker':r.get('stock_id'),'error_type':type(e).__name__})
            continue
        if p<0 or p>100 or n<0 or u<0:
            signature=(p<0,p>100,n<0,u<0)
            cases.append({'kind':'SIGNED_FIELD','level':lev,'ticker':r.get('stock_id'),
                          'negative_percent':signature[0],'percent_over_100':signature[1],
                          'negative_people':signature[2],'negative_shares':signature[3]})
            by_level[lev]=by_level.get(lev,0)+1
    o={'artifact':'HENGCE_FINMIND_SIGNED_TIER_DIAGNOSTIC','snapshot_date':DAY,
       'total_tier_rows':len(data),'affected_count':len(cases),
       'counts_by_level':by_level,'first_20_examples':cases[:20],
       'research_only':True,'raw_source_not_saved':True,
       'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('HENGCE_FINMIND_SIGNED_LEVEL_DIAGNOSTIC',json.dumps({'count':len(cases),'levels':by_level,'first_two':cases[:2]},ensure_ascii=False),flush=True)
if __name__=='__main__': main()
