#!/usr/bin/env python3
"""Corrected all-market FinMind holding-tier historical probe.

FinMind docs: omit data_id AND end_date; provide one VALID snapshot start_date.
One-holiday-window historical query is NOT a valid marketwide capability test.
Only summary counts (no premium raw data) are saved.
"""
import json,os,urllib.request,urllib.parse,datetime
from pathlib import Path
OUT=Path('/tmp/hengce-finmind-marketwide-corrected/manifest.json')
TESTS=('2018-02-02','2024-01-05','2025-11-07')
def main():
    token=os.getenv('FINMIND_TOKEN','').strip()
    out={'schema':'HENGCE_FINMIND_TDCC_MARKETWIDE_CORRECTED_V2','research_only':True,
         'sampled_valid_weekly_dates':TESTS,'source':'TaiwanStockHoldingSharesPer',
         'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'raw_data_persisted':False,'results':[]}
    try:
        if not token: raise RuntimeError('FINMIND_TOKEN_MISSING')
        for ds in TESTS:
            url='https://api.finmindtrade.com/api/v4/data?'+urllib.parse.urlencode({
                'dataset':'TaiwanStockHoldingSharesPer','start_date':ds})
            req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=180) as resp:body=json.load(resp)
            data=body.get('data') if isinstance(body,dict) else None
            status=body.get('status') if isinstance(body,dict) else None
            if status!=200 or not isinstance(data,list):
                raise RuntimeError('MARKETWIDE_API_NOT_AVAILABLE_STATUS_'+str(status))
            dates=sorted({str(x.get('date')) for x in data})
            tickers={str(x.get('stock_id')) for x in data}
            found={'requested':ds,'status':status,'rows':len(data),'tickers':len(tickers),
                   'first_date':dates[0] if dates else None,'last_date':dates[-1] if dates else None,
                   'all_rows_requested_date':dates==[ds]}
            out['results'].append(found)
            print('HENGCE_MARKETWIDE_PROBE',json.dumps(found),flush=True)
            if not data or dates!=[ds] or len(tickers)<100:raise RuntimeError('MARKETWIDE_NOT_VALID_FOR_DATE_'+ds)
        out['state']='PASS'
    except Exception as exc:
        out['state']='BLOCKED'
        out['blocker']=str(exc).splitlines()[0][:150]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('HENGCE_MARKETWIDE_FINAL',out['state'],out.get('blocker',''),flush=True)
    return 0 if out['state']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
